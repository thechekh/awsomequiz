"""Scan the question banks for AWS service / term mentions and emit a
deduplicated candidate list, sorted by frequency.

Output is a JSON list of {term, count, first_letter} sorted descending by
count. Use this as the starting point for data/glossary.json -- write
definitions for the high-count terms first, then work down.
"""
from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

import psycopg

# Patterns that capture AWS terminology in question text.
# "Amazon X" / "AWS X" / "X Beanstalk" / known abbreviations.
PATTERNS = [
    # Amazon <Capitalized>(<Capitalized>)*
    re.compile(r"\bAmazon\s+([A-Z][\w]+(?:\s+[A-Z\d][\w]+){0,4})"),
    # AWS <Capitalized>(<Capitalized>)*
    re.compile(r"\bAWS\s+([A-Z][\w]+(?:\s+[A-Z\d][\w]+){0,4})"),
    # Specific compound names that don't fit the Amazon/AWS prefix
    re.compile(r"\b(Elastic\s+Beanstalk|Elastic\s+Load\s+Balanc(?:ing|er))\b"),
    re.compile(r"\b(CloudFormation|CloudWatch|CloudTrail|CloudFront|CloudShell)\b"),
    re.compile(r"\b(DynamoDB|ElastiCache|GuardDuty|SageMaker|QuickSight|Athena|Aurora)\b"),
    re.compile(r"\b(Macie|Rekognition|Polly|Lex|Textract|Comprehend|Transcribe|Translate)\b"),
    re.compile(r"\b(API\s+Gateway|Step\s+Functions|App(?:Sync|Config|Runner|Stream|Mesh|Flow))\b"),
    re.compile(r"\b(Direct\s+Connect|Transit\s+Gateway|Route\s+53|Global\s+Accelerator)\b"),
    re.compile(r"\b(Systems?\s+Manager|Service\s+Catalog|Control\s+Tower|Secrets?\s+Manager)\b"),
    re.compile(r"\b(Identity\s+Center|Certificate\s+Manager|Key\s+Management\s+Service|Security\s+Hub)\b"),
    re.compile(r"\b(Trusted\s+Advisor|Health\s+Dashboard|Cost\s+Explorer|Budgets|Marketplace|Organizations)\b"),
    re.compile(r"\b(CodeCommit|CodeBuild|CodeDeploy|CodePipeline|CodeArtifact|CodeStar|CodeGuru)\b"),
    re.compile(r"\b(Lambda|EC2|S3|VPC|EBS|EFS|FSx|RDS|ECS|EKS|ECR|Fargate|SAM|SDK|SNS|SQS|MQ|EventBridge|Kinesis|Glue|Redshift|Neptune|Aurora|DocumentDB|Keyspaces|MemoryDB|Timestream)\b"),
    re.compile(r"\b(IAM|KMS|MFA|STS|ACM|WAF|SSO|OIDC|SAML|SCP|VPN|NAT|ALB|NLB|ELB|GSI|LSI|DAX|TAM|TCO|CMK|CDK|RAM|EMR)\b"),
    re.compile(r"\b(Shield\b|Inspector\b|Detective\b|Cognito\b|Outposts|Snowball|Snowcone|DataSync|Transfer\s+Family|Storage\s+Gateway)\b"),
    re.compile(r"\b(WorkSpaces|AppStream|WorkDocs|WorkMail|Chime|Connect|Cloud9|Amplify|Backup|Glacier)\b"),
    # Architecture / framework terms
    re.compile(r"\b(Well-Architected(?:\s+Framework)?|Cloud\s+Adoption\s+Framework|Availability\s+Zone|Edge\s+Location|Region)\b"),
    re.compile(r"\b(Shared\s+Responsibility(?:\s+Model)?|Pre-?signed\s+URL|Provisioned\s+Concurrency|Reserved\s+Concurrency)\b"),
]

# Normalisation: map alias -> canonical name (so "EC2", "Amazon EC2",
# "Elastic Compute Cloud" all collapse to one entry).
CANONICAL = {
    "EC2": "Amazon EC2",
    "Amazon EC2": "Amazon EC2",
    "S3": "Amazon S3",
    "Amazon S3": "Amazon S3",
    "Lambda": "AWS Lambda",
    "AWS Lambda": "AWS Lambda",
    "VPC": "Amazon VPC",
    "Amazon VPC": "Amazon VPC",
    "IAM": "AWS Identity and Access Management (IAM)",
    "Identity and Access Management": "AWS Identity and Access Management (IAM)",
    "KMS": "AWS Key Management Service (KMS)",
    "Key Management Service": "AWS Key Management Service (KMS)",
    "ACM": "AWS Certificate Manager (ACM)",
    "Certificate Manager": "AWS Certificate Manager (ACM)",
    "Cognito": "Amazon Cognito",
    "Amazon Cognito": "Amazon Cognito",
    "DynamoDB": "Amazon DynamoDB",
    "Amazon DynamoDB": "Amazon DynamoDB",
    "RDS": "Amazon RDS",
    "Amazon RDS": "Amazon RDS",
    "CloudFront": "Amazon CloudFront",
    "Amazon CloudFront": "Amazon CloudFront",
    "Route 53": "Amazon Route 53",
    "Amazon Route 53": "Amazon Route 53",
    "API Gateway": "Amazon API Gateway",
    "Amazon API Gateway": "Amazon API Gateway",
    "SQS": "Amazon SQS",
    "Amazon SQS": "Amazon SQS",
    "SNS": "Amazon SNS",
    "Amazon SNS": "Amazon SNS",
    "CloudWatch": "Amazon CloudWatch",
    "Amazon CloudWatch": "Amazon CloudWatch",
    "CloudFormation": "AWS CloudFormation",
    "AWS CloudFormation": "AWS CloudFormation",
    "CloudTrail": "AWS CloudTrail",
    "AWS CloudTrail": "AWS CloudTrail",
    "SAM": "AWS Serverless Application Model (SAM)",
    "Serverless Application Model": "AWS Serverless Application Model (SAM)",
    "Elastic Beanstalk": "AWS Elastic Beanstalk",
    "AWS Elastic Beanstalk": "AWS Elastic Beanstalk",
    "Step Functions": "AWS Step Functions",
    "AWS Step Functions": "AWS Step Functions",
    "EventBridge": "Amazon EventBridge",
    "Amazon EventBridge": "Amazon EventBridge",
    "X-Ray": "AWS X-Ray",
    "AWS X-Ray": "AWS X-Ray",
}


def main() -> int:
    db_url = os.environ.get("SUPABASE_DB_URL")
    if not db_url:
        print("set SUPABASE_DB_URL", file=sys.stderr)
        return 1

    counter: Counter[str] = Counter()

    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT q.stem,
                       array_agg(o.text)                              AS option_texts,
                       array_agg(coalesce(o.explanation_detailed,''))  AS exps
                FROM public.questions q
                LEFT JOIN public.options o ON o.question_id = q.id
                WHERE q.is_active = true
                GROUP BY q.id, q.stem
                """
            )
            for stem, opts, exps in cur.fetchall():
                full = " ".join(filter(None, [stem] + (opts or []) + (exps or [])))
                for pat in PATTERNS:
                    for m in pat.finditer(full):
                        raw = m.group(1) if m.lastindex else m.group(0)
                        raw = re.sub(r"\s+", " ", raw).strip()
                        # If the raw match started without Amazon/AWS prefix, prepend it
                        # when the pattern came from the Amazon/AWS prefixed regex (matched
                        # via group(1)).
                        if pat.pattern.startswith(r"\bAmazon"):
                            term = f"Amazon {raw}"
                        elif pat.pattern.startswith(r"\bAWS"):
                            term = f"AWS {raw}"
                        else:
                            term = raw
                        # Trim trailing non-word characters
                        term = term.rstrip(".,);:")
                        # Collapse to canonical if known
                        term = CANONICAL.get(term, term)
                        counter[term] += 1

    sorted_terms = counter.most_common()
    print(f"Extracted {len(sorted_terms)} unique candidate terms\n")
    print(f"{'TERM':50s} COUNT")
    for term, n in sorted_terms[:80]:
        print(f"  {term:50s} {n}")
    out = Path("scripts/_glossary_candidates.json")
    out.write_text(
        json.dumps(
            [{"term": t, "count": n, "first_letter": t.lstrip("Amazon ").lstrip("AWS ").strip()[:1].upper() or "?"} for t, n in sorted_terms],
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    print(f"\nFull list written to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
