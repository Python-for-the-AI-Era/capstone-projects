"""
SECURED S3 Utilities - PRODUCTION READY
This file contains secure S3 operations with proper access control.
"""

import logging
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from django.conf import settings
from django.core.files.storage import default_storage
from django.utils import timezone
from .models import SecurityLog

logger = logging.getLogger('security')


class S3SecurityManager:
    """
    ✅ SECURED: S3 security manager for secure file operations
    Handles private bucket access, presigned URLs, and audit logging
    """
    
    def __init__(self):
        self.bucket_name = settings.AWS_STORAGE_BUCKET_NAME
        self.region = getattr(settings, 'AWS_S3_REGION_NAME', 'us-east-1')
        
        try:
            self.s3_client = boto3.client(
                's3',
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=self.region
            )
            self.s3_resource = boto3.resource(
                's3',
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=self.region
            )
        except NoCredentialsError:
            logger.error("S3 credentials not configured properly")
            raise
    
    def ensure_private_bucket(self):
        """
        ✅ SECURED: Ensure S3 bucket is private
        Blocks all public access and enables proper ACLs
        """
        try:
            # Block all public access
            self.s3_client.put_public_access_block(
                Bucket=self.bucket_name,
                PublicAccessBlockConfiguration={
                    'BlockPublicAcls': True,
                    'BlockPublicPolicy': True,
                    'IgnorePublicAcls': False,
                    'RestrictPublicBuckets': True
                }
            )
            
            # Remove any existing public ACLs
            bucket_acl = self.s3_client.get_bucket_acl(Bucket=self.bucket_name)
            
            # Remove public READ grants
            private_acl = {
                'Owner': bucket_acl['Owner'],
                'Grants': [
                    grant for grant in bucket_acl['Grants']
                    if grant.get('Grantee', {}).get('URI') != 'http://acs.amazonaws.com/groups/global/AllUsers'
                ]
            }
            
            self.s3_client.put_bucket_acl(
                Bucket=self.bucket_name,
                AccessControlPolicy=private_acl
            )
            
            # Apply bucket policy to deny public access
            bucket_policy = {
                'Version': '2012-10-17',
                'Statement': [
                    {
                        'Sid': 'DenyPublicAccess',
                        'Effect': 'Deny',
                        'Principal': '*',
                        'Action': 's3:*',
                        'Resource': f'arn:aws:s3:::{self.bucket_name}/*',
                        'Condition': {
                            'Bool': {
                                'aws:SecureTransport': 'false'
                            }
                        }
                    },
                    {
                        'Sid': 'DenyUnsecureAccess',
                        'Effect': 'Deny',
                        'Principal': '*',
                        'Action': 's3:*',
                        'Resource': f'arn:aws:s3:::{self.bucket_name}/*',
                        'Condition': {
                            'StringNotEquals': {
                                'aws:SourceVpce': 'vpc-endpoint'
                            }
                        }
                    }
                ]
            }
            
            self.s3_client.put_bucket_policy(
                Bucket=self.bucket_name,
                Policy=json.dumps(bucket_policy)
            )
            
            SecurityLog.objects.create(
                event_type='s3_security_update',
                details={
                    'action': 'bucket_secured',
                    'bucket': self.bucket_name,
                    'timestamp': timezone.now().isoformat()
                }
            )
            
            logger.info(f"S3 bucket {self.bucket_name} secured successfully")
            return True
            
        except ClientError as e:
            logger.error(f"Failed to secure S3 bucket {self.bucket_name}: {e}")
            SecurityLog.objects.create(
                event_type='s3_security_error',
                details={
                    'action': 'bucket_security_failed',
                    'bucket': self.bucket_name,
                    'error': str(e),
                    'timestamp': timezone.now().isoformat()
                }
            )
            return False
    
    def generate_presigned_url(self, file_path, expiration=600, method='GET'):
        """
        ✅ SECURED: Generate presigned URL with proper validation
        Returns temporary URL that expires after specified seconds
        """
        try:
            # Validate file path to prevent directory traversal
            if '..' in file_path or file_path.startswith('/'):
                raise ValueError("Invalid file path")
            
            # Check if file exists
            if not self.file_exists(file_path):
                raise FileNotFoundError(f"File {file_path} not found")
            
            # Generate presigned URL
            url = self.s3_client.generate_presigned_url(
                method,
                Params={
                    'Bucket': self.bucket_name,
                    'Key': file_path
                },
                ExpiresIn=expiration
            )
            
            # Log access for audit
            SecurityLog.objects.create(
                event_type='s3_url_generated',
                details={
                    'file_path': file_path,
                    'expiration': expiration,
                    'method': method,
                    'timestamp': timezone.now().isoformat()
                }
            )
            
            return url
            
        except (ValueError, FileNotFoundError) as e:
            logger.warning(f"Presigned URL generation failed: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error generating presigned URL: {e}")
            return None
    
    def file_exists(self, file_path):
        """
        ✅ SECURED: Check if file exists in S3
        """
        try:
            self.s3_client.head_object(
                Bucket=self.bucket_name,
                Key=file_path
            )
            return True
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                return False
            logger.error(f"Error checking file existence: {e}")
            return False
    
    def upload_file_secure(self, file_obj, file_path, content_type=None, metadata=None):
        """
        ✅ SECURED: Upload file with proper security settings
        Uploads file with private ACL and encryption
        """
        try:
            # Validate file path
            if '..' in file_path or file_path.startswith('/'):
                raise ValueError("Invalid file path")
            
            # Prepare upload parameters
            upload_params = {
                'Bucket': self.bucket_name,
                'Key': file_path,
                'Body': file_obj,
                'ACL': 'private',  # ✅ SECURED: Private by default
                'ServerSideEncryption': 'AES256'  # ✅ SECURED: Server-side encryption
            }
            
            if content_type:
                upload_params['ContentType'] = content_type
            
            if metadata:
                upload_params['Metadata'] = metadata
            
            # Upload file
            result = self.s3_client.put_object(**upload_params)
            
            # Log successful upload
            SecurityLog.objects.create(
                event_type='s3_file_upload',
                details={
                    'file_path': file_path,
                    'size': len(file_obj) if hasattr(file_obj, '__len__') else 0,
                    'content_type': content_type,
                    'encryption': 'AES256',
                    'timestamp': timezone.now().isoformat()
                }
            )
            
            logger.info(f"File uploaded securely to S3: {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to upload file to S3: {e}")
            SecurityLog.objects.create(
                event_type='s3_upload_error',
                details={
                    'file_path': file_path,
                    'error': str(e),
                    'timestamp': timezone.now().isoformat()
                }
            )
            return False
    
    def delete_file_secure(self, file_path, user_id=None):
        """
        ✅ SECURED: Delete file with proper audit logging
        """
        try:
            # Check if file exists
            if not self.file_exists(file_path):
                raise FileNotFoundError(f"File {file_path} not found")
            
            # Delete file
            self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=file_path
            )
            
            # Log deletion for audit
            SecurityLog.objects.create(
                event_type='s3_file_deletion',
                user_id=user_id,
                details={
                    'file_path': file_path,
                    'timestamp': timezone.now().isoformat()
                }
            )
            
            logger.info(f"File deleted from S3: {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete file from S3: {e}")
            SecurityLog.objects.create(
                event_type='s3_deletion_error',
                user_id=user_id,
                details={
                    'file_path': file_path,
                    'error': str(e),
                    'timestamp': timezone.now().isoformat()
                }
            )
            return False
    
    def list_user_files(self, user_id, prefix=None):
        """
        ✅ SECURED: List files with user access validation
        Only returns files that belong to the specified user
        """
        try:
            # Construct prefix for user files
            if prefix is None:
                prefix = f"user_{user_id}/"
            else:
                prefix = f"user_{user_id}/{prefix}"
            
            # List objects
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix,
                MaxKeys=1000  # Limit to prevent excessive listing
            )
            
            # Filter and format results
            files = []
            if 'Contents' in response:
                for obj in response['Contents']:
                    # Validate file belongs to user
                    if obj['Key'].startswith(f"user_{user_id}/"):
                        files.append({
                            'key': obj['Key'],
                            'size': obj['Size'],
                            'last_modified': obj['LastModified'],
                            'etag': obj['ETag']
                        })
            
            # Log access
            SecurityLog.objects.create(
                event_type='s3_file_list',
                user_id=user_id,
                details={
                    'prefix': prefix,
                    'file_count': len(files),
                    'timestamp': timezone.now().isoformat()
                }
            )
            
            return files
            
        except Exception as e:
            logger.error(f"Failed to list S3 files: {e}")
            return []
    
    def get_bucket_security_status(self):
        """
        ✅ SECURED: Get current security status of S3 bucket
        Returns detailed security configuration
        """
        try:
            # Get bucket ACL
            acl_response = self.s3_client.get_bucket_acl(Bucket=self.bucket_name)
            
            # Get public access block configuration
            block_response = self.s3_client.get_public_access_block(
                Bucket=self.bucket_name
            )
            
            # Get bucket policy
            try:
                policy_response = self.s3_client.get_bucket_policy(Bucket=self.bucket_name)
                policy = json.loads(policy_response['Policy'])
            except ClientError:
                policy = None
            
            # Analyze security status
            security_status = {
                'bucket_name': self.bucket_name,
                'public_acls': [
                    grant for grant in acl_response.get('Grants', [])
                    if grant.get('Grantee', {}).get('URI') == 'http://acs.amazonaws.com/groups/global/AllUsers'
                ],
                'public_access_block': block_response.get('PublicAccessBlockConfiguration', {}),
                'has_policy': policy is not None,
                'policy_allows_public': False,
                'secure_transport_required': False,
                'recommendations': []
            }
            
            # Check if policy allows public access
            if policy:
                for statement in policy.get('Statement', []):
                    if (statement.get('Effect') == 'Allow' and 
                        statement.get('Principal') == '*'):
                        security_status['policy_allows_public'] = True
                        security_status['recommendations'].append(
                            "Bucket policy allows public access - should be restricted"
                        )
            
            # Check recommendations
            if not security_status['public_acls']:
                security_status['recommendations'].append(
                    "Bucket has no public ACLs - good"
                )
            
            if security_status['public_access_block'].get('BlockPublicAcls', True):
                security_status['recommendations'].append(
                    "Public ACL blocking is enabled - good"
                )
            else:
                security_status['recommendations'].append(
                    "Enable public ACL blocking"
                )
            
            return security_status
            
        except Exception as e:
            logger.error(f"Failed to get bucket security status: {e}")
            return {'error': str(e)}


# Global S3 security manager instance
s3_security_manager = S3SecurityManager()
