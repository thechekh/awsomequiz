"""Keyword-based domain classifier for CLF-C02 questions.

Pulls every active CLF-C02 question + its option texts + per-option explanations
from prod, scores each against the four official CLF-C02 domains via curated
keyword dictionaries (verbatim AWS service names + concept phrases), and writes
the winning domain_id back to public.questions.

Output categories:
  HIGH confidence (score gap >= 3 or only one domain matched): written to DB
  MEDIUM confidence (score gap 1-2):                            written to DB
  LOW confidence (no clear winner, no matches, tied):           printed for manual review

One-shot script. SUPABASE_DB_URL env var required.
"""
from __future__ import annotations

import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import psycopg

# Domain codes match supabase/seed.sql.
CC = "cloud-concepts"
SC = "security-and-compliance"
CT = "cloud-technology-services"
BP = "billing-pricing-support"

# Keyword dictionaries. Order: longest phrase first inside each list so the
# tokenizer prefers specific matches ("AWS Trusted Advisor" before "advisor").
# Words are matched as case-insensitive whole-word regexes.
KEYWORDS: dict[str, list[tuple[str, int]]] = {
    # ----------------------------------------------------------------------
    # Billing, Pricing, and Support (12%) -- relatively narrow vocabulary,
    # so a single strong match should beat a generic service mention.
    # ----------------------------------------------------------------------
    BP: [
        # Pricing models
        ("pricing model", 3), ("on-demand pricing", 3), ("pay-as-you-go", 3),
        ("pay as you go", 3), ("savings plan", 3), ("reserved instance", 3),
        ("spot instance pricing", 3), ("free tier", 3), ("volume discount", 2),
        ("tco calculator", 3), ("pricing calculator", 3),
        ("total cost of ownership", 3), ("predict cost", 2), ("forecast cost", 2),
        ("predicting cost", 2), ("estimate cost", 2), ("estimating cost", 2),
        ("data transfer cost", 2), ("monthly cost", 2), ("monthly bill", 2),
        ("capex", 2), ("opex", 2),
        # Billing-specific services
        ("aws budgets", 3), ("cost explorer", 3), ("cost and usage report", 3),
        ("cost allocation tag", 3), ("consolidated billing", 3),
        ("aws marketplace", 2),
        # Support
        ("support plan", 3), ("basic support", 3), ("developer support", 3),
        ("business support", 3), ("enterprise support", 3),
        ("enterprise on-ramp", 3),
        ("technical account manager", 3), ("aws concierge", 3),
        ("aws support", 2), ("infrastructure event management", 2),
        # AWS Organizations is dual-use; biased here because its CLF questions
        # are usually about consolidated billing / SCP-cost stuff.
        ("aws organizations", 1),
        ("organizational unit", 1), ("master account", 1), ("payer account", 2),
        # Generic but high-signal
        ("billing", 2), ("invoice", 2),
    ],
    # ----------------------------------------------------------------------
    # Security and Compliance (30%)
    # ----------------------------------------------------------------------
    SC: [
        # Shared responsibility lives here per AWS official guide
        ("shared responsibility model", 3), ("shared responsibility", 2),
        # IAM core
        ("identity and access management", 3), ("\\biam\\b", 2),
        ("iam user", 3), ("iam role", 3), ("iam policy", 3),
        ("iam group", 3), ("iam access analyzer", 3),
        ("principle of least privilege", 3), ("least privilege", 2),
        ("multi-factor authentication", 3), ("\\bmfa\\b", 2),
        ("federated identity", 2), ("federation", 1),
        ("single sign-on", 2), ("\\bsso\\b", 1), ("aws sso", 3),
        ("identity center", 3), ("\\bsaml\\b", 2), ("\\boidc\\b", 2),
        # Security services
        ("aws shield", 3), ("\\bshield\\b advanced", 3),
        ("aws waf", 3), ("web application firewall", 3),
        ("aws guardduty", 3), ("guardduty", 3),
        ("amazon inspector", 3), ("aws inspector", 3),
        ("amazon macie", 3), ("\\bmacie\\b", 3),
        ("aws detective", 3), ("aws audit manager", 3),
        ("aws security hub", 3), ("security hub", 3),
        ("aws config", 2), ("aws artifact", 3),
        ("aws firewall manager", 3), ("firewall manager", 3),
        ("aws key management service", 3), ("\\bkms\\b", 2),
        ("customer master key", 2), ("\\bcmk\\b", 2),
        ("aws cloudhsm", 3), ("cloudhsm", 3),
        ("aws certificate manager", 3), ("\\bacm\\b", 2),
        ("aws secrets manager", 3), ("secrets manager", 3),
        ("amazon cognito", 3), ("\\bcognito\\b", 3),
        ("user pool", 2), ("identity pool", 2),
        ("aws trusted advisor", 2),  # cross-domain, weaker
        # Crypto / data protection
        ("encryption at rest", 3), ("encryption in transit", 3),
        ("encrypt", 1), ("encryption", 2), ("decryption", 2),
        ("\\bssl\\b", 1), ("\\btls\\b", 1),
        ("server-side encryption", 3), ("client-side encryption", 3),
        # Compliance frameworks
        ("compliance", 2), ("\\bhipaa\\b", 3), ("\\bpci\\b", 2),
        ("\\bsoc 1\\b", 3), ("\\bsoc 2\\b", 3), ("\\bgdpr\\b", 3),
        ("\\biso 27001\\b", 3), ("\\bfedramp\\b", 3),
        ("audit", 2), ("auditing", 2), ("penetration test", 2),
        # Network security
        ("security group", 3), ("network acl", 3), ("\\bnacl\\b", 2),
        ("bastion host", 2),
        # Other
        ("ddos", 2), ("denial of service", 2),
        ("threat detection", 2), ("vulnerability", 2),
        ("data classification", 2),
    ],
    # ----------------------------------------------------------------------
    # Cloud Concepts (24%) -- value props, principles, frameworks. Avoid
    # matching mere service mentions.
    # ----------------------------------------------------------------------
    CC: [
        # Value / benefits
        ("value proposition", 3), ("benefits of (the )?cloud", 3),
        ("advantages of (the )?cloud", 3), ("cloud computing", 1),
        ("cloud value", 3),
        ("trade fixed expense for variable", 3),
        ("benefit from massive economies of scale", 3),
        ("stop guessing", 3), ("increase speed and agility", 3),
        ("stop spending money", 3), ("go global in minutes", 3),
        # Cloud economics terms (most CC questions)
        ("cloud economics", 3), ("economies of scale", 3),
        ("capital expense", 2), ("operational expense", 2),
        # Pillars
        ("elasticity", 2), ("scalability", 2),
        ("agility", 2), ("durability", 2),
        ("high availability", 2), ("fault tolerance", 2),
        ("reliability", 1),
        # Frameworks
        ("well-architected", 3), ("well architected", 3),
        ("six pillars", 3), ("five pillars", 3),
        ("operational excellence pillar", 3),
        ("cost optimization pillar", 3),
        ("performance efficiency pillar", 3),
        ("sustainability pillar", 3),
        ("aws cloud adoption framework", 3),
        ("cloud adoption framework", 3), ("\\bcaf\\b", 2),
        ("design principle", 2), ("design principles", 2),
        # Migration strategies (the 6/7 R's)
        ("rehost", 3), ("replatform", 3), ("refactor", 3), ("repurchase", 3),
        ("retain", 2), ("retire", 2), ("relocate", 3),
        ("six r's", 3), ("seven r's", 3),
        ("migration strateg", 2),
        # Global infra concepts (NOT region selection per se)
        ("availability zone", 1),  # weak -- often technical
        ("edge location", 1),
        ("aws global infrastructure", 3),
        # Operating models
        ("public cloud", 2), ("private cloud", 2), ("hybrid cloud", 2),
        ("hybrid deployment", 2), ("on-premises", 1),
        ("infrastructure as a service", 3), ("\\biaas\\b", 2),
        ("platform as a service", 3), ("\\bpaas\\b", 2),
        ("software as a service", 3), ("\\bsaas\\b", 2),
    ],
    # ----------------------------------------------------------------------
    # Cloud Technology and Services (34%) -- concrete services. This is the
    # catch-all for anything that mentions specific AWS services without
    # billing/security/concept overrides.
    # ----------------------------------------------------------------------
    CT: [
        # Compute
        ("amazon ec2", 3), ("\\bec2\\b", 2), ("ec2 instance", 3),
        ("aws lambda", 3), ("lambda function", 3),
        ("amazon ecs", 3), ("\\becs\\b", 2),
        ("amazon eks", 3), ("\\beks\\b", 2),
        ("aws fargate", 3), ("\\bfargate\\b", 2),
        ("aws lightsail", 3), ("lightsail", 2),
        ("elastic beanstalk", 3), ("aws batch", 3),
        ("aws outposts", 3), ("outposts", 2),
        ("auto scaling", 2), ("auto scaling group", 3),
        # Storage
        ("amazon s3", 3), ("simple storage service", 3),
        ("\\bs3 bucket", 3), ("s3 glacier", 3), ("glacier deep archive", 3),
        ("amazon ebs", 3), ("\\bebs\\b", 2), ("ebs volume", 3),
        ("amazon efs", 3), ("\\befs\\b", 2),
        ("amazon fsx", 3), ("\\bfsx\\b", 2),
        ("storage gateway", 3), ("aws backup", 3),
        ("aws snowball", 3), ("aws snowcone", 3), ("snow family", 3),
        ("aws datasync", 3), ("aws transfer family", 3),
        # Database
        ("amazon rds", 3), ("\\brds\\b", 2),
        ("amazon aurora", 3), ("\\baurora\\b", 2),
        ("amazon dynamodb", 3), ("dynamodb", 2),
        ("amazon redshift", 3), ("redshift", 2),
        ("amazon elasticache", 3), ("elasticache", 2),
        ("amazon documentdb", 3), ("amazon neptune", 3),
        ("amazon timestream", 3), ("\\bqldb\\b", 3),
        ("amazon keyspaces", 3), ("amazon memorydb", 3),
        # Networking
        ("amazon vpc", 3), ("\\bvpc\\b", 2),
        ("amazon route 53", 3), ("\\broute 53\\b", 3),
        ("amazon cloudfront", 3), ("cloudfront", 2),
        ("aws direct connect", 3), ("direct connect", 2),
        ("amazon api gateway", 3), ("api gateway", 2),
        ("\\bvpn\\b", 2), ("site-to-site vpn", 3),
        ("transit gateway", 3),
        ("elastic load balancing", 3), ("elastic load balancer", 3),
        ("application load balancer", 3), ("network load balancer", 3),
        ("\\belb\\b", 2),
        ("internet gateway", 2), ("nat gateway", 2),
        ("aws global accelerator", 3), ("global accelerator", 2),
        # Management & monitoring
        ("amazon cloudwatch", 3), ("cloudwatch", 2),
        ("aws cloudtrail", 3), ("cloudtrail", 2),
        ("aws cloudformation", 3), ("cloudformation", 2),
        ("aws systems manager", 3), ("systems manager", 2),
        ("aws service catalog", 3), ("service catalog", 2),
        ("aws control tower", 3), ("control tower", 2),
        ("aws license manager", 3),
        ("aws resource access manager", 3),
        ("aws health dashboard", 3),
        ("personal health dashboard", 3),
        # Messaging / streaming
        ("amazon sqs", 3), ("\\bsqs\\b", 2),
        ("amazon sns", 3), ("\\bsns\\b", 2),
        ("amazon eventbridge", 3), ("eventbridge", 2),
        ("amazon kinesis", 3), ("kinesis", 2),
        ("amazon mq", 3), ("\\bmsk\\b", 2),
        # Analytics
        ("amazon athena", 3), ("athena", 2),
        ("aws glue", 3), ("amazon emr", 3), ("amazon quicksight", 3),
        ("aws lake formation", 3),
        # AI / ML
        ("amazon sagemaker", 3), ("sagemaker", 2),
        ("amazon comprehend", 3), ("comprehend", 2),
        ("amazon rekognition", 3), ("rekognition", 2),
        ("amazon polly", 3), ("amazon lex", 3),
        ("amazon transcribe", 3), ("amazon translate", 3),
        ("amazon forecast", 3), ("amazon personalize", 3),
        ("amazon textract", 3),
        # Developer tools
        ("aws codecommit", 3), ("aws codebuild", 3),
        ("aws codedeploy", 3), ("aws codepipeline", 3),
        ("aws cloud9", 3), ("aws x-ray", 3), ("aws cdk", 3),
        ("aws codeguru", 3), ("aws codestar", 3),
        # Migration / hybrid
        ("aws migration hub", 3),
        ("application migration service", 3),
        ("database migration service", 3),
        ("\\bdms\\b", 2), ("\\bsms\\b", 1),
        # End user
        ("amazon workspaces", 3), ("amazon appstream", 3),
        ("amazon workdocs", 3), ("amazon workmail", 3),
        ("amazon chime", 3), ("amazon connect", 3),
        # Misc
        ("aws step functions", 3), ("step functions", 2),
        ("aws appflow", 3), ("aws app runner", 3),
        ("aws amplify", 3), ("aws appsync", 3),
        # Concept-y but technical
        ("serverless", 2), ("managed service", 1),
        ("containerization", 2), ("microservice", 2),
        # General tech
        ("region selection", 1),
    ],
}

# Words that, when found, downweight matches in other domains. Mostly
# unused for now -- the score-gap based confidence handles ambiguity.

# Precompile regexes.
COMPILED: dict[str, list[tuple[re.Pattern, int]]] = {
    domain: [(re.compile(rf"\b{pat}\b", re.IGNORECASE), weight) for pat, weight in items]
    for domain, items in KEYWORDS.items()
}

# Domain priority for tie-breaking (highest = most-specific): Billing wins
# ties because it's narrow; Cloud Tech loses ties because it's the catch-all.
TIEBREAK = {BP: 4, SC: 3, CC: 2, CT: 1}


def score_question(text: str) -> dict[str, int]:
    """Return {domain -> aggregate weight from matched keywords}."""
    scores: dict[str, int] = {}
    for domain, patterns in COMPILED.items():
        s = 0
        for rgx, weight in patterns:
            # Each pattern contributes its weight once if it matches
            # at all (avoid runaway scores for questions that say "S3"
            # 10 times). Cheap and predictable.
            if rgx.search(text):
                s += weight
        scores[domain] = s
    return scores


def classify(text: str) -> tuple[str | None, str, dict[str, int]]:
    """Return (domain_code, confidence, raw_scores).

    confidence in {'high', 'medium', 'low', 'none'}.
    """
    scores = score_question(text)
    ranked = sorted(scores.items(), key=lambda kv: (kv[1], TIEBREAK[kv[0]]), reverse=True)
    top_domain, top_score = ranked[0]
    second_score = ranked[1][1] if len(ranked) > 1 else 0
    if top_score == 0:
        return (None, "none", scores)
    gap = top_score - second_score
    if top_score >= 6 and gap >= 3:
        return (top_domain, "high", scores)
    if top_score >= 3 and gap >= 1:
        return (top_domain, "medium", scores)
    return (top_domain, "low", scores)


def main() -> int:
    db_url = os.environ.get("SUPABASE_DB_URL")
    if not db_url:
        print("set SUPABASE_DB_URL", file=sys.stderr)
        return 1
    apply_writes = "--apply" in sys.argv
    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT q.id, q.external_id, q.stem,
                       array_agg(o.text ORDER BY o.label)              AS option_texts,
                       array_agg(coalesce(o.explanation_detailed, '') ORDER BY o.label) AS explanations
                FROM public.questions q
                JOIN public.certifications c ON c.id = q.certification_id
                LEFT JOIN public.options o ON o.question_id = q.id
                WHERE c.code = 'CLF-C02' AND q.is_active = true
                GROUP BY q.id, q.external_id, q.stem
                ORDER BY (q.external_id::int)
                """
            )
            rows = cur.fetchall()
        # Look up domain UUIDs by code
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT d.code, d.id FROM public.domains d
                JOIN public.certifications c ON c.id = d.certification_id
                WHERE c.code = 'CLF-C02'
                """
            )
            domain_id_by_code = dict(cur.fetchall())

        confidence_counter: Counter[str] = Counter()
        domain_counter: Counter[str] = Counter()
        manual_list: list[dict] = []
        updates: list[tuple[str, str]] = []  # (domain_id, question_id)
        for qid, ext_id, stem, option_texts, explanations in rows:
            full_text = " ".join(
                filter(None, [stem] + (option_texts or []) + (explanations or []))
            )
            domain, confidence, scores = classify(full_text)
            confidence_counter[confidence] += 1
            if confidence in ("high", "medium"):
                updates.append((domain_id_by_code[domain], qid))
                domain_counter[domain] += 1
            else:
                manual_list.append(
                    {
                        "external_id": ext_id,
                        "question_id": str(qid),
                        "stem": stem[:140].replace("\n", " "),
                        "suggestion": domain,
                        "scores": scores,
                        "confidence": confidence,
                    }
                )

        print("CONFIDENCE BUCKETS:")
        for k, v in confidence_counter.items():
            print(f"  {k:8s} {v}")
        print("\nAUTO-CLASSIFIED DISTRIBUTION:")
        for k, v in domain_counter.items():
            print(f"  {k:30s} {v}  ({100*v/sum(domain_counter.values()):.1f}%)")
        print(f"\nQuestions needing manual review: {len(manual_list)}")

        if apply_writes and updates:
            print(f"\nWriting {len(updates)} domain_id updates ...")
            with conn.cursor() as cur:
                cur.executemany(
                    "UPDATE public.questions SET domain_id = %s WHERE id = %s",
                    updates,
                )
            conn.commit()
            print("Done.")
        elif updates:
            print(f"\n(dry run -- pass --apply to write {len(updates)} updates)")

        if manual_list:
            out = Path("scripts/_clf_manual_review.json")
            import json
            out.write_text(json.dumps(manual_list, indent=2), encoding="utf-8")
            print(f"\nManual-review list written to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
