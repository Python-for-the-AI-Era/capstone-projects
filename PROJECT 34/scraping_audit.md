# Procurement Portal Data Extraction: Stealth Audit

## 1. Detection Analysis
- **The Block:** Cloudflare was triggering a 403 Forbidden after 3 hits due to missing `sec-ch-ua` headers and an active `webdriver` flag.
- **The Solution:** Implemented `playwright-stealth` and randomized User-Agents to match standard Nigerian desktop traffic.

## 2. Stealth Strategies
- **Session Stickiness:** We reuse `state.json` to maintain valid cookies for up to 48 hours.
- **Rate Throttling:** Every request is separated by a 2-8 second Gaussian random delay. 
- **Headless vs Headful:** During testing, 'Headless' mode was flagged immediately. Production runs use 'Headful' mode on a dedicated VPS.

## 3. Data Integrity
- **Total Records Targeted:** 45,000
- **Success Rate:** 98.4% (Intermittent manual intervention for CAPTCHAs).
- **Format:** Exported to cleaned CSV and JSON for investigative analysis.

## 4. Ethical Compliance
The scraper includes a `robots.txt` check and identifies its traffic via a custom (but realistic) header to ensure we aren't causing a Denial of Service (DoS) on government infrastructure.