# Password Reset Security Hardening

## 1. Vulnerability Remediation
- **Bug 1 (Plaintext):** Tokens are now hashed using **Bcrypt** before storage. Even a full database leak will not allow an attacker to generate valid reset links.
- **Bug 2 (No Expiry):** Tokens now carry a 60-minute TTL.
- **Bug 3 (Reuse):** We implemented an atomic `is_used` check. Once a password is changed, the token is permanently invalidated.

## 2. Rate Limiting Strategy
We implemented a **Sliding Window** rate limiter in Redis. This prevents automated "Reset Spam" attacks and protects our SMTP reputation.

## 3. Session Invalidation (Stretch Goal)
Upon a successful password reset, we now trigger a **Global Logout**. By utilizing the Redis blacklist from Project 26, we invalidate all current JWTs for that user, ensuring that if their account was compromised, the attacker is instantly kicked out.

## 4. Security Metrics
| Threat | Mitigation | Status |
| :--- | :--- | :--- |
| Database Leak | Bcrypt Hashing | ✅ SECURE |
| Replay Attack | `is_used` Flag | ✅ SECURE |
| Brute Force | Redis Rate Limit| ✅ SECURE |
| Expired Link | `expires_at` Check| ✅ SECURE |