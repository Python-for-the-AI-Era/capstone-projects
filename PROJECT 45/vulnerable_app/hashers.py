"""
VULNERABLE Password Hashers - DO NOT USE IN PRODUCTION
This file contains intentional security vulnerabilities for educational purposes.
"""

import hashlib
from django.contrib.auth.hashers import BasePasswordHasher, mask_hash
from django.utils.crypto import constant_time_compare


class MD5PasswordHasher(BasePasswordHasher):
    """
    VULNERABLE: MD5 password hasher
    MD5 is cryptographically broken and should never be used for passwords
    """
    algorithm = "md5"
    
    def encode(self, password, salt):
        """VULNERABLE: Simple MD5 without salt"""
        return hashlib.md5(password.encode()).hexdigest()
    
    def verify(self, password, encoded):
        """VULNERABLE: Plain MD5 comparison"""
        encoded_2 = self.encode(password, '')
        return constant_time_compare(encoded, encoded_2)
    
    def safe_summary(self, encoded):
        """VULNERABLE: Exposes full hash"""
        return {
            'algorithm': self.algorithm,
            'hash': encoded,
        }
