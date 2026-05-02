# Security Audit Report: Kofiso Health

## Vulnerability ID: BOLA-001
**Severity:** Critical
**Description:** Broken Object Level Authorization on `/records/{user_id}`.

## Impact
Any authenticated user can scrape the entire medical database by iterating through integer IDs. This violates HIPAA/NDPR compliance.

## Remediation Steps
1. Create a `require_owns_resource` dependency factory.
2. Ensure the `current_user.id` is compared against `record.owner_id`.
3. Implement an Admin override for emergency medical access.
4. Set up an `audit_logs` table for forensic tracking.

## Verification
- [ ] Pytest suite with 10 scenarios passed.
- [ ] Unauthorized access returns 403.
- [ ] Audit logs successfully capture the requester's identity.