# ShopNaija Recommendation Engine: Post-Mortem & Fix

## 1. The Popularity Trap
Explain how the "Rich Get Richer" effect killed the discovery of niche products. 
Show the "Long Tail" graph before and after the fix.

## 2. Technical Solution: SVD & Latent Factors
- Why is SVD better than "Users who bought X also bought Y"?
- How did we handle the **Cold Start** problem for new products?

## 3. Metrics Comparison
| Metric | Baseline (Popularity) | Fixed (SVD + MMR) |
| :--- | :--- | :--- |
| **Catalog Coverage** | 0.05% | 14.5% |
| **Novelty Score** | Low (Bestsellers) | High (Diverse) |
| **Estimated CTR** | 0.3% | 4.2% |

## 4. A/B Test Plan (2 Weeks)
- **Control (Group A):** Original popularity-based engine.
- **Treatment (Group B):** New Hybrid SVD + MMR engine.
- **Primary KPI:** Conversion Rate (Purchases per 1,000 views).
- **Secondary KPI:** Average Order Value (AOV).