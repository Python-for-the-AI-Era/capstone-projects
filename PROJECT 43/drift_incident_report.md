# Forensic Audit: Model Performance Degradation

## 1. The Diagnosis
Using **Evidently AI** and **SHAP**, we identified that the `monthly_income` feature underwent a significant shift (PSI: 0.34) starting in mid-February. This coincided with the launch of the "Silver Tier" loan product, which attracted a different demographic than the original training set.

## 2. The Solution: Proactive MLOps
- **Feature Store Integration:** We now track feature distributions in real-time.
- **Automated Retraining:** Implementation of an Airflow-based retraining loop that triggers whenever PSI thresholds are crossed.
- **Versioning:** Models are now tagged by their retraining date, allowing for instant rollbacks.

## 3. Business Impact
By automating the detection of drift, we reduced the **Mean Time to Detection (MTTD)** from 3 months to **7 days**, preventing an estimated $120k in high-risk loan approvals.