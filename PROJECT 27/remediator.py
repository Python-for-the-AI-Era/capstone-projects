def lockdown_bucket(bucket_name: str):
    # 1. Enable Block Public Access
    s3.put_public_access_block(
        Bucket=bucket_name,
        PublicAccessBlockConfiguration={
            'BlockPublicAcls': True,
            'IgnorePublicAcls': True,
            'BlockPublicPolicy': True,
            'RestrictPublicBuckets': True
        }
    )
    # 2. Remove any "public-read" ACLs from individual objects
    # (Student must implement object-level ACL cleanup)