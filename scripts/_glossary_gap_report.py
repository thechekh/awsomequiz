"""Produce a deduped, normalised list of AWS terms missing from data/glossary.json.

Strategy: rescan the active question banks (CLF-C02 + DVA-C02), expand the
canonical-name table to fold aliases together, filter junk fragments, then
diff against the curated glossary.

Output: scripts/_glossary_gap_report.txt -- a frequency-sorted table that I
use as a checklist while writing batched definitions.
"""
from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

import psycopg

# Match Amazon/AWS-prefixed service names plus a long set of bare names that
# AWS docs use without the prefix in normal prose.
PATTERNS = [
    re.compile(r"\bAmazon\s+([A-Z][\w]+(?:\s+[A-Z\d][\w]+){0,4})"),
    re.compile(r"\bAWS\s+([A-Z][\w]+(?:\s+[A-Z\d][\w]+){0,4})"),
]

# Aliases -> canonical glossary term (matches the keys in data/glossary.json)
CANONICAL: dict[str, str] = {}

def _canon(*aliases: str, canonical: str) -> None:
    for a in aliases:
        CANONICAL[a.lower()] = canonical

# Compute / containers
_canon("EC2", "Amazon EC2", "Elastic Compute Cloud", canonical="Amazon EC2")
_canon("Lambda", "AWS Lambda", canonical="AWS Lambda")
_canon("ECS", "Amazon ECS", "Elastic Container Service", canonical="Amazon ECS")
_canon("EKS", "Amazon EKS", "Elastic Kubernetes Service", canonical="Amazon EKS")
_canon("ECR", "Amazon ECR", "Elastic Container Registry", canonical="Amazon ECR")
_canon("Fargate", "AWS Fargate", canonical="AWS Fargate")
_canon("Lightsail", "Amazon Lightsail", canonical="Amazon Lightsail")
_canon("Beanstalk", "Elastic Beanstalk", "AWS Elastic Beanstalk", canonical="AWS Elastic Beanstalk")
_canon("Outposts", "AWS Outposts", canonical="AWS Outposts")
_canon("App Runner", "AWS App Runner", canonical="AWS App Runner")
_canon("Amplify", "AWS Amplify", canonical="AWS Amplify")
_canon("Batch", "AWS Batch", canonical="AWS Batch")
# Storage
_canon("S3", "Amazon S3", "Simple Storage Service", canonical="Amazon S3")
_canon("EBS", "Amazon EBS", "Elastic Block Store", canonical="Amazon EBS")
_canon("EFS", "Amazon EFS", "Elastic File System", canonical="Amazon EFS")
_canon("FSx", "Amazon FSx", canonical="Amazon FSx")
_canon("Backup", "AWS Backup", canonical="AWS Backup")
_canon("Storage Gateway", "AWS Storage Gateway", canonical="AWS Storage Gateway")
_canon("DataSync", "AWS DataSync", canonical="AWS DataSync")
_canon("Transfer Family", "AWS Transfer Family", canonical="AWS Transfer Family")
_canon("Snow Family", "AWS Snow Family", "Snowball", "Snowcone", "Snowmobile", canonical="AWS Snow Family")
# Database
_canon("RDS", "Amazon RDS", "Relational Database Service", canonical="Amazon RDS")
_canon("Aurora", "Amazon Aurora", canonical="Amazon Aurora")
_canon("DynamoDB", "Amazon DynamoDB", canonical="Amazon DynamoDB")
_canon("ElastiCache", "Amazon ElastiCache", canonical="Amazon ElastiCache")
_canon("DAX", "DynamoDB Accelerator", canonical="DAX")
_canon("Redshift", "Amazon Redshift", canonical="Amazon Redshift")
_canon("Neptune", "Amazon Neptune", canonical="Amazon Neptune")
_canon("DocumentDB", "Amazon DocumentDB", canonical="Amazon DocumentDB")
_canon("Memory DB", "MemoryDB", "Amazon MemoryDB", canonical="Amazon MemoryDB")
_canon("Keyspaces", "Amazon Keyspaces", canonical="Amazon Keyspaces")
_canon("Timestream", "Amazon Timestream", canonical="Amazon Timestream")
_canon("QLDB", "Amazon QLDB", canonical="Amazon QLDB")
# Networking / CDN
_canon("VPC", "Amazon VPC", "Virtual Private Cloud", canonical="Amazon VPC")
_canon("Route 53", "Amazon Route 53", canonical="Amazon Route 53")
_canon("CloudFront", "Amazon CloudFront", canonical="Amazon CloudFront")
_canon("Direct Connect", "AWS Direct Connect", canonical="AWS Direct Connect")
_canon("API Gateway", "Amazon API Gateway", canonical="Amazon API Gateway")
_canon("Transit Gateway", "AWS Transit Gateway", canonical="Transit Gateway")
_canon("Global Accelerator", "AWS Global Accelerator", canonical="AWS Global Accelerator")
_canon("Network Firewall", "AWS Network Firewall", canonical="AWS Network Firewall")
_canon("Elastic Load Balancing", "ELB", "Application Load Balancer", "Network Load Balancer", "Gateway Load Balancer", "ALB", "NLB", "GWLB", canonical="Elastic Load Balancing (ELB)")
_canon("Site-to-Site VPN", "AWS Site-to-Site VPN", "Client VPN", "AWS VPN", canonical="VPN")
_canon("NAT Gateway", canonical="NAT Gateway")
_canon("Internet Gateway", "IGW", canonical="Internet Gateway")
_canon("CIDR", "CIDR block", canonical="CIDR block")
# Security / identity
_canon("IAM", "AWS IAM", "Identity and Access Management", "AWS Identity and Access Management", canonical="AWS Identity and Access Management (IAM)")
_canon("KMS", "AWS KMS", "Key Management Service", "AWS Key Management Service", canonical="AWS Key Management Service (KMS)")
_canon("ACM", "AWS Certificate Manager", "Certificate Manager", canonical="AWS Certificate Manager (ACM)")
_canon("Secrets Manager", "AWS Secrets Manager", canonical="AWS Secrets Manager")
_canon("Cognito", "Amazon Cognito", canonical="Amazon Cognito")
_canon("STS", "Security Token Service", "AWS STS", canonical="STS")
_canon("WAF", "AWS WAF", "Web Application Firewall", canonical="AWS WAF")
_canon("Shield", "AWS Shield", "Shield Advanced", canonical="AWS Shield")
_canon("GuardDuty", "Amazon GuardDuty", canonical="Amazon GuardDuty")
_canon("Inspector", "Amazon Inspector", canonical="Amazon Inspector")
_canon("Macie", "Amazon Macie", canonical="Amazon Macie")
_canon("Detective", "Amazon Detective", canonical="Amazon Detective")
_canon("Audit Manager", "AWS Audit Manager", canonical="AWS Audit Manager")
_canon("Security Hub", "AWS Security Hub", canonical="AWS Security Hub")
_canon("Identity Center", "AWS IAM Identity Center", "AWS SSO", "Single Sign-On", "AWS Single Sign-On", canonical="AWS IAM Identity Center")
_canon("Firewall Manager", "AWS Firewall Manager", canonical="AWS Firewall Manager")
_canon("Network Manager", "AWS Network Manager", canonical="AWS Network Manager")
_canon("RAM", "AWS Resource Access Manager", "Resource Access Manager", canonical="AWS Resource Access Manager (RAM)")
_canon("CloudHSM", "AWS CloudHSM", canonical="AWS CloudHSM")
_canon("Artifact", "AWS Artifact", canonical="AWS Artifact")
_canon("MFA", "Multi-Factor Authentication", canonical="MFA")
_canon("SCP", "Service Control Policy", canonical="Service Control Policy (SCP)")
# Dev tools
_canon("CodeCommit", "AWS CodeCommit", canonical="AWS CodeCommit")
_canon("CodeBuild", "AWS CodeBuild", canonical="AWS CodeBuild")
_canon("CodeDeploy", "AWS CodeDeploy", canonical="AWS CodeDeploy")
_canon("CodePipeline", "AWS CodePipeline", canonical="AWS CodePipeline")
_canon("CodeArtifact", "AWS CodeArtifact", canonical="AWS CodeArtifact")
_canon("CodeStar", "AWS CodeStar", canonical="AWS CodeStar")
_canon("CodeGuru", "AWS CodeGuru", canonical="AWS CodeGuru")
_canon("Cloud9", "AWS Cloud9", canonical="AWS Cloud9")
_canon("CloudShell", "AWS CloudShell", canonical="AWS CloudShell")
_canon("X-Ray", "AWS X-Ray", canonical="AWS X-Ray")
_canon("CDK", "AWS CDK", "Cloud Development Kit", canonical="AWS CDK")
_canon("SAM", "AWS SAM", "Serverless Application Model", canonical="AWS Serverless Application Model (SAM)")
_canon("AWS CLI", "CLI", "Command Line Interface", canonical="AWS CLI")
_canon("AWS SDK", "SDK", canonical="SDK")
# Management / monitoring
_canon("CloudWatch", "Amazon CloudWatch", canonical="Amazon CloudWatch")
_canon("CloudTrail", "AWS CloudTrail", canonical="AWS CloudTrail")
_canon("CloudFormation", "AWS CloudFormation", canonical="AWS CloudFormation")
_canon("Systems Manager", "AWS Systems Manager", "SSM", canonical="AWS Systems Manager")
_canon("Service Catalog", "AWS Service Catalog", canonical="AWS Service Catalog")
_canon("Control Tower", "AWS Control Tower", canonical="AWS Control Tower")
_canon("Config", "AWS Config", canonical="AWS Config")
_canon("Trusted Advisor", "AWS Trusted Advisor", canonical="AWS Trusted Advisor")
_canon("Health Dashboard", "AWS Health Dashboard", "Personal Health Dashboard", canonical="AWS Health Dashboard")
_canon("Organizations", "AWS Organizations", canonical="AWS Organizations")
_canon("License Manager", "AWS License Manager", canonical="AWS License Manager")
_canon("AppConfig", "AWS AppConfig", canonical="AWS AppConfig")
_canon("Compute Optimizer", "AWS Compute Optimizer", canonical="AWS Compute Optimizer")
_canon("OpsCenter", "AWS Systems Manager OpsCenter", canonical="AWS Systems Manager")
# App integration / messaging
_canon("SQS", "Amazon SQS", "Simple Queue Service", canonical="Amazon SQS")
_canon("SNS", "Amazon SNS", "Simple Notification Service", canonical="Amazon SNS")
_canon("EventBridge", "Amazon EventBridge", "CloudWatch Events", canonical="Amazon EventBridge")
_canon("Step Functions", "AWS Step Functions", canonical="AWS Step Functions")
_canon("AppSync", "AWS AppSync", canonical="AWS AppSync")
_canon("AppFlow", "Amazon AppFlow", canonical="Amazon AppFlow")
_canon("MQ", "Amazon MQ", canonical="Amazon MQ")
_canon("MSK", "Amazon MSK", "Managed Streaming for Kafka", canonical="Amazon MSK")
_canon("SES", "Amazon SES", "Simple Email Service", canonical="Amazon SES")
# Analytics / ML
_canon("Athena", "Amazon Athena", canonical="Amazon Athena")
_canon("Glue", "AWS Glue", canonical="AWS Glue")
_canon("EMR", "Amazon EMR", "Elastic MapReduce", canonical="Amazon EMR")
_canon("QuickSight", "Amazon QuickSight", canonical="Amazon QuickSight")
_canon("OpenSearch", "Amazon OpenSearch", "OpenSearch Service", "Elasticsearch Service", canonical="Amazon OpenSearch Service")
_canon("Kinesis", "Amazon Kinesis", "Kinesis Data Streams", "Kinesis Firehose", "Kinesis Data Firehose", "Kinesis Data Analytics", canonical="Amazon Kinesis")
_canon("Lake Formation", "AWS Lake Formation", canonical="AWS Lake Formation")
_canon("DataZone", "Amazon DataZone", canonical="Amazon DataZone")
_canon("SageMaker", "Amazon SageMaker", canonical="Amazon SageMaker")
_canon("Comprehend", "Amazon Comprehend", canonical="Amazon Comprehend")
_canon("Rekognition", "Amazon Rekognition", canonical="Amazon Rekognition")
_canon("Polly", "Amazon Polly", canonical="Amazon Polly")
_canon("Lex", "Amazon Lex", canonical="Amazon Lex")
_canon("Textract", "Amazon Textract", canonical="Amazon Textract")
_canon("Transcribe", "Amazon Transcribe", canonical="Amazon Transcribe")
_canon("Translate", "Amazon Translate", canonical="Amazon Translate")
_canon("Forecast", "Amazon Forecast", canonical="Amazon Forecast")
_canon("Personalize", "Amazon Personalize", canonical="Amazon Personalize")
_canon("Bedrock", "Amazon Bedrock", canonical="Amazon Bedrock")
_canon("Q Developer", "Amazon Q Developer", "Amazon Q", canonical="Amazon Q")
# Billing / pricing
_canon("Cost Explorer", "AWS Cost Explorer", canonical="AWS Cost Explorer")
_canon("Budgets", "AWS Budgets", canonical="AWS Budgets")
_canon("Pricing Calculator", "AWS Pricing Calculator", "TCO Calculator", canonical="AWS Pricing Calculator")
_canon("Cost and Usage Report", "AWS CUR", "CUR", canonical="AWS Cost and Usage Report")
_canon("Marketplace", "AWS Marketplace", canonical="AWS Marketplace")
_canon("Billing Conductor", "AWS Billing Conductor", canonical="AWS Billing Conductor")
_canon("Savings Plans", canonical="Savings Plans")
_canon("Reserved Instance", "RI", "Reserved Instances", canonical="Reserved Instance (RI)")
_canon("Spot Instance", "Spot Instances", canonical="Spot Instance")
_canon("Support plans", "Basic Support", "Developer Support", "Business Support", "Enterprise Support", "AWS Support", canonical="AWS Support plans")
# Migration / hybrid / end-user
_canon("Migration Hub", "AWS Migration Hub", canonical="AWS Migration Hub")
_canon("Application Migration Service", "AWS MGN", "MGN", canonical="AWS Application Migration Service")
_canon("Database Migration Service", "AWS DMS", "DMS", canonical="AWS Database Migration Service (DMS)")
_canon("Schema Conversion Tool", "AWS SCT", "SCT", canonical="AWS Schema Conversion Tool")
_canon("WorkSpaces", "Amazon WorkSpaces", canonical="Amazon WorkSpaces")
_canon("AppStream", "Amazon AppStream", canonical="Amazon AppStream")
_canon("WorkDocs", "Amazon WorkDocs", canonical="Amazon WorkDocs")
_canon("WorkMail", "Amazon WorkMail", canonical="Amazon WorkMail")
_canon("Chime", "Amazon Chime", canonical="Amazon Chime")
_canon("Connect", "Amazon Connect", canonical="Amazon Connect")
_canon("Local Zones", "AWS Local Zones", canonical="AWS Local Zones")
_canon("Wavelength", "AWS Wavelength", canonical="AWS Wavelength")
_canon("Ground Station", "AWS Ground Station", canonical="AWS Ground Station")
# Concepts
_canon("Region", "AWS Region", "Regions", "AWS Regions", canonical="Region")
_canon("Availability Zone", "AZ", "Availability Zones", canonical="Availability Zone (AZ)")
_canon("Edge Location", "Edge Locations", canonical="Edge location")
_canon("Shared Responsibility", "Shared Responsibility Model", canonical="Shared Responsibility Model")
_canon("Well-Architected", "Well-Architected Framework", canonical="Well-Architected Framework")
_canon("CAF", "Cloud Adoption Framework", canonical="AWS Cloud Adoption Framework (CAF)")
_canon("IaC", "Infrastructure as Code", canonical="Infrastructure as Code (IaC)")
_canon("ARN", "Amazon Resource Name", canonical="ARN")
_canon("Tag", "Tags", "Tagging", canonical="Tags")
_canon("Pre-signed URL", "Presigned URL", canonical="Pre-signed URL")
_canon("Cold start", canonical="Cold start")
_canon("Idempotency", "Idempotent", canonical="Idempotency")
_canon("GSI", "Global Secondary Index", canonical="GSI")
_canon("LSI", "Local Secondary Index", canonical="LSI")
_canon("Envelope encryption", canonical="Envelope encryption")
_canon("Encryption at rest", canonical="Encryption at rest")
_canon("Encryption in transit", canonical="Encryption in transit")
_canon("Security Group", "Security Groups", canonical="Security Group")
_canon("API key", canonical="API key")
_canon("JWT", "JSON Web Token", canonical="JWT")
_canon("Blue/green deployment", "Blue-green deployment", canonical="Blue/green deployment")
_canon("Canary deployment", "Canary release", canonical="Canary deployment")
_canon("Provisioned concurrency", canonical="Provisioned concurrency")
_canon("Reserved concurrency", canonical="Reserved concurrency")

# Add bare service names that should match without the Amazon/AWS prefix
EXTRA_BARE_PATTERNS = [
    "EC2", "S3", "Lambda", "VPC", "EBS", "EFS", "FSx", "RDS", "ECS", "EKS", "ECR",
    "Fargate", "Aurora", "DynamoDB", "ElastiCache", "Redshift", "Neptune", "DocumentDB",
    "Keyspaces", "MemoryDB", "Timestream", "QLDB", "CloudFront", "Route 53", "CloudWatch",
    "CloudTrail", "CloudFormation", "CloudShell", "CloudHSM", "Cloud9", "Athena", "Glue",
    "EMR", "QuickSight", "Kinesis", "OpenSearch", "Macie", "GuardDuty", "Inspector",
    "Detective", "Cognito", "SageMaker", "Comprehend", "Rekognition", "Polly", "Lex",
    "Textract", "Transcribe", "Translate", "Forecast", "Personalize", "Bedrock",
    "Beanstalk", "Outposts", "Snowball", "Snowcone", "DataSync", "AppConfig", "AppSync",
    "AppFlow", "AppStream", "Lightsail", "Marketplace", "Organizations", "Budgets",
    "GreenGrass", "IoT Core", "IoT Analytics",
]

for term in EXTRA_BARE_PATTERNS:
    PATTERNS.append(re.compile(rf"\b{re.escape(term)}\b"))

# Junk fragments to skip (Amazon/AWS-prefixed but meaningless)
JUNK = {
    "AWS Cloud", "AWS account", "AWS Regions", "AWS Region", "AWS Documentation",
    "AWS resources", "AWS resource", "AWS services", "AWS service", "AWS environment",
    "Amazon Web Services", "AWS Free", "AWS Free Tier", "AWS access", "AWS account-level",
    "AWS console", "Amazon", "AWS",
}


def normalise(raw: str, pat: re.Pattern) -> str | None:
    """Map a raw regex hit to its canonical glossary term, or None to drop."""
    raw = re.sub(r"\s+", " ", raw).strip().rstrip(".,);:")
    if not raw:
        return None
    # Reconstruct full term when the pattern only captured the post-prefix bit
    if pat.pattern.startswith(r"\bAmazon"):
        term = f"Amazon {raw}"
    elif pat.pattern.startswith(r"\bAWS"):
        term = f"AWS {raw}"
    else:
        term = raw
    if term in JUNK:
        return None
    return CANONICAL.get(term.lower(), term)


def main() -> int:
    db_url = os.environ.get("SUPABASE_DB_URL")
    if not db_url:
        print("set SUPABASE_DB_URL", file=sys.stderr)
        return 1

    # 1. Load curated glossary so we can subtract existing terms.
    existing_data = json.loads(Path("data/glossary.json").read_text(encoding="utf-8"))
    existing_terms = {e["term"].lower() for e in existing_data["entries"]}
    existing_terms |= {a.lower() for e in existing_data["entries"] for a in e.get("aliases", [])}

    # 2. Rescan questions.
    counter: Counter[str] = Counter()
    with psycopg.connect(db_url) as conn, conn.cursor() as cur:
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
                    canonical = normalise(raw, pat)
                    if canonical:
                        counter[canonical] += 1

    # 3. Subtract anything already curated (term name OR aliases match).
    gap = [(t, n) for t, n in counter.most_common() if t.lower() not in existing_terms]

    out = Path("scripts/_glossary_gap_report.txt")
    lines = [
        f"Total unique normalised terms found: {len(counter)}",
        f"Already in glossary.json:            {len(counter) - len(gap)}",
        f"Missing (the gap):                   {len(gap)}",
        "",
        "MISSING TERMS (sorted by question-bank mention count):",
        f"{'COUNT':>6s}  TERM",
    ]
    for term, n in gap:
        if n < 3:  # very low signal -- noise/rare
            continue
        lines.append(f"{n:6d}  {term}")
    out.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines[:40]))
    print(f"\n... full list ({len(gap)} entries) written to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
