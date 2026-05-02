# Incident Response: S3 Exposure & Remediation

## 1. The Vulnerability
An audit revealed that the `docsafe-kyc-documents` bucket had `IgnorePublicAcls` set to `False`, and several objects were uploaded with the `public-read` ACL.

## 2. Immediate Remediation
- **Block Public Access:** Enabled globally on the bucket.
- **ACL Purge:** All object-level ACLs were reset to `private`.
- **Bucket Policy:** Added a 'Deny' effect for any request without an `aws:PrincipalAccount` matching our ID.

## 3. New Architecture: Temporary Grants
Direct links have been removed. All document access now goes through our **Access Manager API**, which:
1. Validates the user's session.
2. Logs the request (User ID, IP, Timestamp).
3. Generates a **Presigned URL** valid for only 300 seconds.

## 4. Encryption at Rest (Stretch Goal)
We implemented **Client-Side Encryption** using the `cryptography` library. 
Files are encrypted with a unique key *before* reaching S3. 
Even if AWS itself is compromised, the passport photos remain unreadable ciphertext.