"""Keyword-based domain classifier for DVA-C02 questions.

Mirrors scripts/_classify_clf_questions.py but with DVA-C02's four official
exam-guide domains:
  - Development with AWS Services       (32%) -- catch-all for app-building
  - Security                            (26%) -- IAM/KMS/Cognito/secrets
  - Deployment                          (24%) -- CI/CD + IaC
  - Troubleshooting and Optimization    (18%) -- CloudWatch/X-Ray/perf tuning

DVA-C02 has heavier service overlap than CLF-C02 (Lambda appears in all four
domains; what matters is what's being asked OF the service). So the keyword
weights below favour the more-specific domain in tiebreaks (Security beats
Deployment beats Troubleshooting beats Development).

One-shot script. SUPABASE_DB_URL required. --apply to write.
"""
from __future__ import annotations

import os
import re
import sys
from collections import Counter
from pathlib import Path

import psycopg

DEV = "dev-with-aws-services"
SEC = "security"
DEP = "deployment"
TRB = "troubleshoot-optimization"

KEYWORDS: dict[str, list[tuple[str, int]]] = {
    # ----------------------------------------------------------------------
    # Security (26%) -- specific identity/auth/crypto terms. Wins ties.
    # ----------------------------------------------------------------------
    SEC: [
        ("identity and access management", 3), ("\\biam\\b", 2),
        ("iam role", 3), ("iam policy", 3), ("iam user", 3),
        ("iam group", 2), ("instance profile", 3),
        ("assume role", 3), ("\\bsts\\b", 3), ("security token service", 3),
        ("temporary credential", 3), ("session token", 2),
        ("access key", 2), ("secret access key", 2), ("rotate access key", 3),
        ("least privilege", 3), ("principle of least privilege", 3),
        ("resource-based policy", 3), ("resource based policy", 3),
        ("identity-based policy", 3), ("trust policy", 3),
        ("permission boundary", 3), ("service control policy", 3),
        ("policy variable", 2), ("policy condition", 2),
        # Federation / external identities
        ("amazon cognito", 3), ("\\bcognito\\b", 3),
        ("user pool", 3), ("identity pool", 3),
        ("federated identity", 3), ("federation", 2),
        ("\\boidc\\b", 2), ("\\bsaml\\b", 2),
        ("openid connect", 3),
        ("\\bjwt\\b", 2), ("json web token", 3),
        ("\\boauth\\b", 2),
        # Crypto / data protection
        ("aws kms", 3), ("\\bkms\\b", 2), ("key management service", 3),
        ("customer master key", 3), ("\\bcmk\\b", 2),
        ("customer managed key", 3), ("aws managed key", 3),
        ("envelope encryption", 3), ("key policy", 3), ("key rotation", 2),
        ("aws cloudhsm", 3),
        ("encryption at rest", 3), ("encryption in transit", 3),
        ("server-side encryption", 3), ("client-side encryption", 3),
        ("\\bsse-kms\\b", 3), ("\\bsse-s3\\b", 3), ("\\bsse-c\\b", 3),
        # Secrets
        ("aws secrets manager", 3), ("secrets manager", 3),
        ("rotation of secret", 3), ("rotate secret", 3),
        ("parameter store securestring", 3), ("securestring", 3),
        ("systems manager parameter store", 2),
        # Signed URLs / requests
        ("pre-signed url", 3), ("presigned url", 3),
        ("signature version 4", 3), ("\\bsigv4\\b", 3),
        ("signing requests", 3),
        # Certificates / TLS
        ("aws certificate manager", 3), ("\\bacm\\b", 2),
        ("\\bssl\\b certificate", 3), ("\\btls\\b certificate", 3),
        # Network security
        ("security group", 2), ("network acl", 2),
        ("bucket policy", 3),
        ("aws waf", 3), ("web application firewall", 3),
        # Audit / detective
        ("aws config", 2), ("aws cloudtrail", 1),  # CT also in Troubleshoot
        # Generic
        ("authentication", 1), ("authorization", 1),
        ("authenticate", 1), ("authorize", 1),
    ],
    # ----------------------------------------------------------------------
    # Deployment (24%) -- CI/CD, IaC, environment promotion.
    # ----------------------------------------------------------------------
    DEP: [
        # CodeSuite
        ("aws codepipeline", 3), ("codepipeline", 3),
        ("aws codebuild", 3), ("codebuild", 3),
        ("aws codedeploy", 3), ("codedeploy", 3),
        ("aws codecommit", 3), ("codecommit", 3),
        ("aws codeartifact", 3), ("codeartifact", 3),
        ("aws codestar", 3),
        ("buildspec", 3), ("buildspec.yml", 3),
        ("appspec", 3), ("appspec.yml", 3),
        # IaC
        ("aws cloudformation", 3), ("cloudformation", 2),
        ("cfn template", 3), ("cloudformation stack", 3),
        ("cloudformation parameter", 3), ("cloudformation output", 3),
        ("change set", 3), ("drift detection", 3),
        ("nested stack", 3), ("stackset", 3),
        ("transform: aws::serverless", 3),
        # SAM
        ("aws sam", 3), ("aws serverless application model", 3),
        ("sam template", 3), ("sam build", 3), ("sam deploy", 3),
        ("sam local", 3), ("sam invoke", 3),
        # CDK
        ("aws cdk", 3), ("cloud development kit", 3),
        ("cdk deploy", 3), ("cdk synth", 3),
        # Elastic Beanstalk
        ("elastic beanstalk", 3), ("\\bebextensions\\b", 3),
        ("\\.ebextensions", 3),
        # Deployment strategies
        ("blue/green deployment", 3), ("blue-green deployment", 3),
        ("blue green deployment", 3),
        ("canary deployment", 3), ("canary release", 3),
        ("rolling deployment", 3), ("all-at-once deployment", 3),
        ("immutable deployment", 3), ("immutable infrastructure", 2),
        ("rolling with additional batch", 3),
        ("traffic shifting", 2), ("weighted alias", 3),
        # Lambda deployment specifics
        ("lambda alias", 2), ("lambda version", 2), ("lambda layer", 2),
        ("alias routing", 3), ("provisioned concurrency", 2),  # also perf
        ("lambda deployment package", 3),
        # Containers / ECR
        ("amazon ecr", 3), ("\\becr\\b", 2),
        ("container image", 2), ("docker image", 2),
        # General CI/CD
        ("ci/cd", 3), ("\\bcicd\\b", 3), ("continuous integration", 3),
        ("continuous delivery", 3), ("continuous deployment", 3),
        ("deployment group", 3), ("deployment configuration", 3),
        ("rollback", 2), ("automated rollback", 3),
        ("environment promotion", 3), ("staging environment", 2),
        ("infrastructure as code", 3),
        ("aws amplify", 2),
    ],
    # ----------------------------------------------------------------------
    # Troubleshooting and Optimization (18%) -- observability + perf tuning.
    # ----------------------------------------------------------------------
    TRB: [
        # CloudWatch family
        ("amazon cloudwatch", 3), ("cloudwatch", 2),
        ("cloudwatch logs", 3), ("log group", 3), ("log stream", 3),
        ("cloudwatch metric", 3), ("custom metric", 3),
        ("cloudwatch alarm", 3), ("metric filter", 3),
        ("cloudwatch dashboard", 3),
        ("cloudwatch logs insights", 3), ("logs insights", 3),
        ("cloudwatch synthetics", 3), ("canaries", 2),
        ("contributor insights", 3),
        ("lambda insights", 3), ("container insights", 3),
        ("rum (real user monitoring)", 3),
        # X-Ray
        ("aws x-ray", 3), ("\\bx-ray\\b", 3),
        ("x-ray trace", 3), ("x-ray segment", 3), ("x-ray subsegment", 3),
        ("service map", 3), ("trace id", 2), ("annotations", 1),
        ("instrumented", 1), ("instrumentation", 2),
        # CloudTrail (when used for forensics/troubleshooting)
        ("aws cloudtrail", 2), ("cloudtrail event", 3),
        ("cloudtrail trail", 3),
        # Performance / optimization
        ("performance tuning", 3), ("optimi[sz]e performance", 3),
        ("reduce latency", 3), ("lower latency", 3),
        ("memory allocation", 2), ("memory configuration", 3),
        ("cold start", 3), ("\\bcoldstart\\b", 3),
        ("provisioned concurrency", 2),
        ("execution context", 2), ("warm start", 2),
        ("connection pool", 3), ("connection reuse", 3),
        ("exponential backoff", 3), ("retry strategy", 3),
        ("retry with backoff", 3),
        ("throttling exception", 3), ("throttled", 2),
        ("service quota", 3), ("service limit", 2), ("rate limit", 3),
        # Caching
        ("amazon elasticache", 2), ("elasticache", 2),
        ("amazon cloudfront cache", 3), ("cache invalidation", 3),
        ("dynamodb accelerator", 3), ("\\bdax\\b", 3),
        ("api gateway cache", 3), ("cache hit", 3), ("cache miss", 3),
        # Errors
        ("error code", 1), ("status code 5", 2), ("status code 4", 1),
        ("\\b429\\b", 2),  # too many requests
        ("dlq", 2), ("dead letter queue", 3),
    ],
    # ----------------------------------------------------------------------
    # Development with AWS Services (32%) -- the catch-all. Lower weights
    # since most DVA questions mention these services; we want specifics
    # to dominate when present.
    # ----------------------------------------------------------------------
    DEV: [
        # Lambda (core dev surface)
        ("aws lambda", 2), ("\\blambda\\b function", 2),
        ("event source mapping", 3), ("invocation type", 2),
        ("event-driven", 2), ("event driven", 2),
        ("async invocation", 3), ("synchronous invocation", 3),
        ("invokeasync", 2), ("invokefunction", 2),
        # DynamoDB
        ("amazon dynamodb", 3), ("dynamodb", 2),
        ("partition key", 3), ("sort key", 3),
        ("global secondary index", 3), ("\\bgsi\\b", 2),
        ("local secondary index", 3), ("\\blsi\\b", 2),
        ("dynamodb streams", 3), ("dynamodb scan", 2), ("dynamodb query", 2),
        ("batchgetitem", 3), ("batchwriteitem", 3),
        ("conditional write", 3), ("optimistic locking", 3),
        ("expression attribute", 3),
        ("dynamodb transactions", 3), ("transactwrite", 3),
        # API Gateway
        ("amazon api gateway", 3), ("api gateway", 2),
        ("rest api", 1), ("http api", 2), ("websocket api", 3),
        ("api gateway stage", 3), ("api gateway method", 3),
        ("api gateway authorizer", 3),
        ("lambda authorizer", 3), ("lambda proxy integration", 3),
        ("mapping template", 3), ("usage plan", 3), ("api key", 2),
        # Messaging
        ("amazon sqs", 3), ("\\bsqs\\b", 2),
        ("visibility timeout", 3), ("long polling", 3), ("short polling", 3),
        ("fifo queue", 3), ("standard queue", 3),
        ("message group id", 3), ("deduplication", 2),
        ("amazon sns", 3), ("\\bsns\\b", 2), ("fanout", 3),
        ("amazon eventbridge", 3), ("eventbridge", 2),
        ("event bus", 3), ("event pattern", 3),
        ("amazon mq", 2),
        # Step Functions / orchestration
        ("aws step functions", 3), ("step functions", 2),
        ("state machine", 3), ("standard workflow", 3),
        ("express workflow", 3),
        # AppSync / GraphQL
        ("aws appsync", 3), ("appsync", 2), ("graphql", 2),
        # Kinesis (data ingestion in apps)
        ("amazon kinesis", 3), ("kinesis data streams", 3),
        ("kinesis firehose", 3),
        ("shard iterator", 3), ("\\bshard\\b", 1),
        # S3 (app storage operations)
        ("amazon s3", 2), ("\\bs3 bucket", 1),
        ("s3 object", 1), ("s3 lifecycle", 2),
        ("multipart upload", 3), ("s3 transfer acceleration", 3),
        ("event notification", 2),
        # SDKs / CLI
        ("aws sdk", 3), ("aws cli", 2),
        ("boto3", 3), ("aws-sdk", 3), ("software development kit", 2),
        ("command line interface", 2),
        ("aws cloud9", 2), ("cloud9", 2),
        # Storage for app
        ("amazon efs", 1), ("\\befs\\b", 1),
        ("amazon rds", 2), ("\\brds\\b", 1),
        ("amazon aurora", 2),
        # Misc dev
        ("environment variable", 2),
        ("idempotency", 3), ("idempotent", 3),
        ("schema validation", 2),
        ("aws app runner", 3), ("app runner", 3),
        ("aws appflow", 2),
        ("amazon mq", 2),
        # Containers (dev side)
        ("amazon ecs", 2), ("amazon eks", 2),
        ("aws fargate", 2),
    ],
}

# Precompile regexes
COMPILED: dict[str, list[tuple[re.Pattern, int]]] = {
    domain: [(re.compile(rf"\b{pat}\b", re.IGNORECASE), weight) for pat, weight in items]
    for domain, items in KEYWORDS.items()
}

# Tiebreak priority: most specific wins (Development is the catch-all)
TIEBREAK = {SEC: 4, DEP: 3, TRB: 2, DEV: 1}


def score_question(text: str) -> dict[str, int]:
    scores: dict[str, int] = {}
    for domain, patterns in COMPILED.items():
        s = 0
        for rgx, weight in patterns:
            if rgx.search(text):
                s += weight
        scores[domain] = s
    return scores


def classify(text: str) -> tuple[str | None, str, dict[str, int]]:
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
                       array_agg(o.text ORDER BY o.label),
                       array_agg(coalesce(o.explanation_detailed, '') ORDER BY o.label)
                FROM public.questions q
                JOIN public.certifications c ON c.id = q.certification_id
                LEFT JOIN public.options o ON o.question_id = q.id
                WHERE c.code = 'DVA-C02' AND q.is_active = true
                GROUP BY q.id, q.external_id, q.stem
                ORDER BY (q.external_id::int)
                """
            )
            rows = cur.fetchall()
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT d.code, d.id FROM public.domains d
                JOIN public.certifications c ON c.id = d.certification_id
                WHERE c.code = 'DVA-C02'
                """
            )
            domain_id_by_code = dict(cur.fetchall())

        confidence_counter: Counter[str] = Counter()
        domain_counter: Counter[str] = Counter()
        manual_list: list[dict] = []
        updates: list[tuple[str, str]] = []
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
                manual_list.append({
                    "external_id": ext_id,
                    "question_id": str(qid),
                    "stem": stem[:140].replace("\n", " "),
                    "suggestion": domain,
                    "scores": scores,
                    "confidence": confidence,
                })

        print("CONFIDENCE BUCKETS:")
        for k, v in sorted(confidence_counter.items()):
            print(f"  {k:8s} {v}")
        total_auto = sum(domain_counter.values())
        if total_auto:
            print("\nAUTO-CLASSIFIED DISTRIBUTION:")
            for k, v in sorted(domain_counter.items(), key=lambda kv: -kv[1]):
                print(f"  {k:32s} {v}  ({100*v/total_auto:.1f}%)")
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
            out = Path("scripts/_dva_manual_review.json")
            import json
            out.write_text(json.dumps(manual_list, indent=2), encoding="utf-8")
            print(f"\nManual-review list written to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
