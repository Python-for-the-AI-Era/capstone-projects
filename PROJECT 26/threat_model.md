# Security Audit: JWT Authorization Fixes

## 1. The Vulnerability: Infinite Persistence
The original implementation lacked the `exp` claim, making tokens valid forever. 
Combined with a lack of revocation, a leaked token was a permanent backdoor.

## 2. Solution: Hybrid Revocation
- **Short-Lived Access Tokens:** Expire every 30 minutes.
- **Redis Blacklist:** Allows us to instantly kick a user off the platform (Logout/Ban).
- **Password Invalidation:** All tokens issued before a password change are now 
  rejected by the middleware.

## 3. Cryptographic Upgrade (Stretch Goal)
We moved from **HS256** (Symmetric) to **RS256** (Asymmetric). 
- **Benefit:** The internal services can verify tokens using a **Public Key**, 
  but only the Auth service has the **Private Key** required to issue them. 
  If a microservice is breached, the attacker cannot forge new tokens.

## 4. Key Metrics
| Feature | Before | After |
| :--- | :--- | :--- |
| **Token Expiry** | None | 30 Minutes |
| **Instant Revocation**| NO | YES (< 5ms via Redis) |
| **Signature Safety** | Weak (Shared Secret) | Strong (RSA Keypair) |