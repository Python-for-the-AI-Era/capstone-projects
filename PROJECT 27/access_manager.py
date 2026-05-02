def get_secure_document_link(bucket_name: str, object_key: str, user_id: str):
    """
    Generates a 300-second (5 min) temporary link.
    LOGGING: We must record WHO requested this link for the audit trail.
    """
    # Log to DB first: insert_audit_log(user_id, object_key, ip_address)
    
    url = s3.generate_presigned_url(
        'get_object',
        Params={'Bucket': bucket_name, 'Key': object_key},
        ExpiresIn=300 
    )
    return url