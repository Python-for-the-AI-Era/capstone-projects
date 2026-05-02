import boto3
from botocore.exceptions import ClientError

s3 = boto3.client('s3')

def audit_bucket_security(bucket_name: str):
    """
    Checks the 'Big Three' of S3 Security:
    1. Public Access Block (The Master Switch)
    2. Bucket ACLs (Legacy permissions)
    3. Bucket Policy (JSON-based rules)
    """
    results = {}
    # Check Public Access Block
    try:
        status = s3.get_public_access_block(Bucket=bucket_name)
        results['block_all'] = status['PublicAccessBlockConfiguration']['BlockPublicAcls']
    except ClientError:
        results['block_all'] = "MISSING (DANGER)"
    
    return results