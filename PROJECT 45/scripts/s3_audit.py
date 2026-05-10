#!/usr/bin/env python3
"""
S3 Security Audit Script for JumpApp

This script audits S3 media bucket security and implements
presigned URLs for secure media access.
"""

import boto3
import json
import logging
from datetime import datetime, timedelta
from botocore.exceptions import ClientError, NoCredentialsError
import argparse
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class S3SecurityAuditor:
    """S3 security auditor for media bucket security."""
    
    def __init__(self, bucket_name, region='us-east-1'):
        """
        Initialize S3 auditor.
        
        Args:
            bucket_name: Name of the S3 bucket to audit
            region: AWS region
        """
        self.bucket_name = bucket_name
        self.region = region
        
        try:
            # Initialize S3 client
            self.s3_client = boto3.client('s3', region_name=region)
            self.s3_resource = boto3.resource('s3', region_name=region)
            
            logger.info(f"S3 auditor initialized for bucket: {bucket_name}")
            
        except NoCredentialsError:
            logger.error("AWS credentials not found. Please configure AWS credentials.")
            sys.exit(1)
        except Exception as e:
            logger.error(f"Failed to initialize S3 client: {e}")
            sys.exit(1)
    
    def audit_bucket_security(self):
        """
        Audit S3 bucket security configuration.
        
        Returns:
            dict: Audit results
        """
        logger.info("Starting S3 bucket security audit...")
        
        audit_results = {
            'bucket_name': self.bucket_name,
            'audit_timestamp': datetime.now().isoformat(),
            'security_issues': [],
            'recommendations': [],
            'current_configuration': {}
        }
        
        try:
            # Check bucket existence
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            logger.info(f"Bucket {self.bucket_name} exists")
            
            # Get bucket ACL
            try:
                acl = self.s3_client.get_bucket_acl(Bucket=self.bucket_name)
                audit_results['current_configuration']['acl'] = acl
                logger.info("Retrieved bucket ACL")
            except ClientError as e:
                logger.error(f"Failed to get bucket ACL: {e}")
                audit_results['security_issues'].append(f"ACL access error: {e}")
            
            # Check bucket policy
            try:
                policy = self.s3_client.get_bucket_policy(Bucket=self.bucket_name)
                audit_results['current_configuration']['policy'] = policy
                logger.info("Retrieved bucket policy")
            except ClientError as e:
                if e.response['Error']['Code'] == 'NoSuchBucketPolicy':
                    audit_results['security_issues'].append("No bucket policy found")
                    audit_results['recommendations'].append("Create a restrictive bucket policy")
                else:
                    logger.error(f"Failed to get bucket policy: {e}")
                    audit_results['security_issues'].append(f"Policy access error: {e}")
            
            # Check public access block
            try:
                public_block = self.s3_client.get_public_access_block(Bucket=self.bucket_name)
                audit_results['current_configuration']['public_block'] = public_block
                logger.info("Retrieved public access block configuration")
                
                # Check if public access is properly blocked
                block_config = public_block['PublicAccessBlockConfiguration']
                
                if not block_config['BlockPublicAcls']:
                    audit_results['security_issues'].append("Public ACLs are not blocked")
                    audit_results['recommendations'].append("Block public ACLs")
                
                if not block_config['BlockPublicPolicy']:
                    audit_results['security_issues'].append("Public policies are not blocked")
                    audit_results['recommendations'].append("Block public policies")
                
                if not block_config['IgnorePublicAcls']:
                    audit_results['security_issues'].append("Public ACLs are not ignored")
                    audit_results['recommendations'].append("Ignore public ACLs")
                
                if not block_config['RestrictPublicBuckets']:
                    audit_results['security_issues'].append("Public buckets are not restricted")
                    audit_results['recommendations'].append("Restrict public buckets")
                
            except ClientError as e:
                logger.error(f"Failed to get public access block: {e}")
                audit_results['security_issues'].append(f"Public access block error: {e}")
                audit_results['recommendations'].append("Configure public access block")
            
            # Check bucket versioning
            try:
                versioning = self.s3_client.get_bucket_versioning(Bucket=self.bucket_name)
                audit_results['current_configuration']['versioning'] = versioning
                
                if not versioning.get('Status') == 'Enabled':
                    audit_results['security_issues'].append("Versioning is not enabled")
                    audit_results['recommendations'].append("Enable bucket versioning")
                
            except ClientError as e:
                logger.error(f"Failed to get versioning: {e}")
                audit_results['security_issues'].append(f"Versioning check error: {e}")
            
            # Check bucket encryption
            try:
                encryption = self.s3_client.get_bucket_encryption(Bucket=self.bucket_name)
                audit_results['current_configuration']['encryption'] = encryption
                logger.info("Retrieved bucket encryption configuration")
                
                # Check if encryption is properly configured
                rules = encryption.get('ServerSideEncryptionConfiguration', {}).get('Rules', [])
                if not rules:
                    audit_results['security_issues'].append("No encryption rules found")
                    audit_results['recommendations'].append("Configure server-side encryption")
                else:
                    rule = rules[0]
                    sse_algorithm = rule.get('ApplyServerSideEncryptionByDefault', {}).get('SSEAlgorithm')
                    if sse_algorithm != 'AES256':
                        audit_results['security_issues'].append(f"Encryption algorithm: {sse_algorithm}")
                        audit_results['recommendations'].append("Use AES256 encryption")
                
            except ClientError as e:
                if e.response['Error']['Code'] == 'ServerSideEncryptionConfigurationNotFoundError':
                    audit_results['security_issues'].append("No encryption configuration found")
                    audit_results['recommendations'].append("Configure server-side encryption")
                else:
                    logger.error(f"Failed to get encryption: {e}")
                    audit_results['security_issues'].append(f"Encryption check error: {e}")
            
            # Check logging configuration
            try:
                logging_config = self.s3_client.get_bucket_logging(Bucket=self.bucket_name)
                audit_results['current_configuration']['logging'] = logging_config
                
                if not logging_config.get('LoggingEnabled'):
                    audit_results['security_issues'].append("Access logging is not enabled")
                    audit_results['recommendations'].append("Enable S3 access logging")
                
            except ClientError as e:
                logger.error(f"Failed to get logging configuration: {e}")
                audit_results['security_issues'].append(f"Logging check error: {e}")
            
            # Scan for publicly accessible objects
            self._scan_public_objects(audit_results)
            
            # Check bucket size and object count
            self._get_bucket_statistics(audit_results)
            
        except ClientError as e:
            logger.error(f"Bucket audit failed: {e}")
            audit_results['security_issues'].append(f"Bucket audit error: {e}")
        
        return audit_results
    
    def _scan_public_objects(self, audit_results):
        """Scan for publicly accessible objects."""
        logger.info("Scanning for publicly accessible objects...")
        
        try:
            public_objects = []
            
            # List all objects
            paginator = self.s3_client.get_paginator('list_objects_v2')
            pages = paginator.paginate(Bucket=self.bucket_name)
            
            for page in pages:
                if 'Contents' in page:
                    for obj in page['Contents']:
                        key = obj['Key']
                        
                        # Check object ACL
                        try:
                            obj_acl = self.s3_client.get_object_acl(Bucket=self.bucket_name, Key=key)
                            
                            # Check for public access
                            for grant in obj_acl.get('Grants', []):
                                grantee = grant.get('Grantee', {})
                                if grantee.get('Type') == 'Group' and 'AllUsers' in str(grantee):
                                    public_objects.append({
                                        'key': key,
                                        'size': obj['Size'],
                                        'last_modified': obj['LastModified'].isoformat(),
                                        'grantee': grantee
                                    })
                                    logger.warning(f"Public object found: {key}")
                        
                        except ClientError as e:
                            logger.error(f"Failed to get ACL for {key}: {e}")
            
            if public_objects:
                audit_results['security_issues'].append(f"Found {len(public_objects)} publicly accessible objects")
                audit_results['recommendations'].append("Remove public access from all objects")
                audit_results['public_objects'] = public_objects
            else:
                logger.info("No publicly accessible objects found")
        
        except ClientError as e:
            logger.error(f"Failed to scan objects: {e}")
            audit_results['security_issues'].append(f"Object scan error: {e}")
    
    def _get_bucket_statistics(self, audit_results):
        """Get bucket statistics."""
        try:
            # Get bucket size and object count
            total_size = 0
            object_count = 0
            
            paginator = self.s3_client.get_paginator('list_objects_v2')
            pages = paginator.paginate(Bucket=self.bucket_name)
            
            for page in pages:
                if 'Contents' in page:
                    for obj in page['Contents']:
                        total_size += obj['Size']
                        object_count += 1
            
            audit_results['statistics'] = {
                'total_size_bytes': total_size,
                'total_size_human': self._format_size(total_size),
                'object_count': object_count
            }
            
            logger.info(f"Bucket statistics: {object_count} objects, {self._format_size(total_size)}")
        
        except ClientError as e:
            logger.error(f"Failed to get bucket statistics: {e}")
    
    def _format_size(self, size_bytes):
        """Format size in human readable format."""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} PB"
    
    def fix_security_issues(self, audit_results):
        """
        Fix security issues found during audit.
        
        Args:
            audit_results: Results from audit_bucket_security()
        """
        logger.info("Fixing security issues...")
        
        fixes_applied = []
        
        # Fix public access block
        if any('public' in issue.lower() for issue in audit_results['security_issues']):
            try:
                self.s3_client.put_public_access_block(
                    Bucket=self.bucket_name,
                    PublicAccessBlockConfiguration={
                        'BlockPublicAcls': True,
                        'IgnorePublicAcls': True,
                        'BlockPublicPolicy': True,
                        'RestrictPublicBuckets': True
                    }
                )
                fixes_applied.append("Applied public access block")
                logger.info("Applied public access block")
            except ClientError as e:
                logger.error(f"Failed to apply public access block: {e}")
        
        # Fix bucket policy
        if 'No bucket policy found' in audit_results['security_issues']:
            try:
                # Create restrictive bucket policy
                bucket_policy = {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Sid": "AllowSSLRequestsOnly",
                            "Action": "s3:*",
                            "Effect": "Deny",
                            "Resource": [
                                f"arn:aws:s3:::{self.bucket_name}",
                                f"arn:aws:s3:::{self.bucket_name}/*"
                            ],
                            "Condition": {
                                "Bool": {
                                    "aws:SecureTransport": "false"
                                }
                            }
                        }
                    ]
                }
                
                self.s3_client.put_bucket_policy(
                    Bucket=self.bucket_name,
                    Policy=json.dumps(bucket_policy)
                )
                fixes_applied.append("Created restrictive bucket policy")
                logger.info("Created restrictive bucket policy")
            except ClientError as e:
                logger.error(f"Failed to create bucket policy: {e}")
        
        # Fix encryption
        if 'No encryption configuration found' in audit_results['security_issues']:
            try:
                self.s3_client.put_bucket_encryption(
                    Bucket=self.bucket_name,
                    ServerSideEncryptionConfiguration={
                        'Rules': [
                            {
                                'ApplyServerSideEncryptionByDefault': {
                                    'SSEAlgorithm': 'AES256'
                                }
                            }
                        ]
                    }
                )
                fixes_applied.append("Enabled AES256 encryption")
                logger.info("Enabled AES256 encryption")
            except ClientError as e:
                logger.error(f"Failed to enable encryption: {e}")
        
        # Fix versioning
        if 'Versioning is not enabled' in audit_results['security_issues']:
            try:
                self.s3_client.put_bucket_versioning(
                    Bucket=self.bucket_name,
                    VersioningConfiguration={'Status': 'Enabled'}
                )
                fixes_applied.append("Enabled versioning")
                logger.info("Enabled versioning")
            except ClientError as e:
                logger.error(f"Failed to enable versioning: {e}")
        
        # Fix public objects
        if 'public_objects' in audit_results:
            try:
                for obj in audit_results['public_objects']:
                    key = obj['key']
                    self.s3_client.put_object_acl(
                        Bucket=self.bucket_name,
                        Key=key,
                        ACL='private'
                    )
                    logger.info(f"Made object private: {key}")
                
                fixes_applied.append(f"Made {len(audit_results['public_objects'])} objects private")
            except ClientError as e:
                logger.error(f"Failed to fix public objects: {e}")
        
        return fixes_applied
    
    def generate_presigned_url(self, object_key, expiration=3600):
        """
        Generate presigned URL for secure object access.
        
        Args:
            object_key: S3 object key
            expiration: URL expiration time in seconds (default: 1 hour)
            
        Returns:
            str: Presigned URL
        """
        try:
            url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket_name, 'Key': object_key},
                ExpiresIn=expiration
            )
            logger.info(f"Generated presigned URL for {object_key}")
            return url
        except ClientError as e:
            logger.error(f"Failed to generate presigned URL for {object_key}: {e}")
            return None
    
    def generate_presigned_post(self, object_key, expiration=3600):
        """
        Generate presigned POST for secure object upload.
        
        Args:
            object_key: S3 object key
            expiration: URL expiration time in seconds (default: 1 hour)
            
        Returns:
            dict: Presigned POST data
        """
        try:
            response = self.s3_client.generate_presigned_post(
                Bucket=self.bucket_name,
                Key=object_key,
                ExpiresIn=expiration,
                Conditions=[
                    {"content-length-range": 0, 10 * 1024 * 1024}  # 10MB max
                ]
            )
            logger.info(f"Generated presigned POST for {object_key}")
            return response
        except ClientError as e:
            logger.error(f"Failed to generate presigned POST for {object_key}: {e}")
            return None


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='S3 Security Auditor for JumpApp')
    parser.add_argument('--bucket', required=True, help='S3 bucket name')
    parser.add_argument('--region', default='us-east-1', help='AWS region')
    parser.add_argument('--fix', action='store_true', help='Fix security issues automatically')
    parser.add_argument('--output', help='Output file for audit results')
    
    args = parser.parse_args()
    
    # Initialize auditor
    auditor = S3SecurityAuditor(args.bucket, args.region)
    
    # Run audit
    logger.info("Starting S3 security audit...")
    audit_results = auditor.audit_bucket_security()
    
    # Print results
    print("\n" + "="*50)
    print("S3 SECURITY AUDIT RESULTS")
    print("="*50)
    
    print(f"Bucket: {audit_results['bucket_name']}")
    print(f"Audit Time: {audit_results['audit_timestamp']}")
    
    if audit_results['security_issues']:
        print(f"\n🚨 SECURITY ISSUES FOUND ({len(audit_results['security_issues'])}):")
        for issue in audit_results['security_issues']:
            print(f"  ❌ {issue}")
    else:
        print("\n✅ No security issues found!")
    
    if audit_results['recommendations']:
        print(f"\n💡 RECOMMENDATIONS ({len(audit_results['recommendations'])}):")
        for rec in audit_results['recommendations']:
            print(f"  🔧 {rec}")
    
    if 'statistics' in audit_results:
        stats = audit_results['statistics']
        print(f"\n📊 BUCKET STATISTICS:")
        print(f"  Objects: {stats['object_count']}")
        print(f"  Size: {stats['total_size_human']}")
    
    # Fix issues if requested
    if args.fix:
        print(f"\n🔧 FIXING SECURITY ISSUES...")
        fixes = auditor.fix_security_issues(audit_results)
        print(f"Applied {len(fixes)} fixes:")
        for fix in fixes:
            print(f"  ✅ {fix}")
    
    # Save results to file
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(audit_results, f, indent=2, default=str)
        print(f"\n💾 Results saved to {args.output}")
    
    # Generate sample presigned URL
    if 'statistics' in audit_results and audit_results['statistics']['object_count'] > 0:
        print(f"\n🔗 SAMPLE PRESIGNED URL:")
        # Get first object key
        paginator = auditor.s3_client.get_paginator('list_objects_v2')
        pages = paginator.paginate(Bucket=args.bucket)
        for page in pages:
            if 'Contents' in page:
                first_key = page['Contents'][0]['Key']
                presigned_url = auditor.generate_presigned_url(first_key)
                print(f"  {presigned_url}")
                break
    
    print("\n" + "="*50)


if __name__ == '__main__':
    main()
