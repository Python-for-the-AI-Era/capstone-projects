# FinEdge Fraud Detection: Technical Specs

## 1. Inference Performance
We achieved a **P99 of 32ms** by:
- Offloading state to **Redis**.
- Caching the **XGBoost** model in memory.
- Using **FastAPI**'s async event loop.

## 2. Explainability & Compliance
Every transaction > 0.7 probability triggers a **SHAP analysis**. 
Compliance officers can see the exact features that pushed the score into the "Fraud" zone.

## 3. Shadow Mode (Stretch Goal)
We implemented a **Shadow Deployment** strategy:
- 90% of traffic uses `v1`.
- 10% of traffic is sent to `v2` (XGBoost + New Features).
- We log `v2`'s predictions but do not act on them. This allows us to calculate 
  Precision/Recall for the new model using real-world data before full rollout.

## 4. Feature Registry
| Feature | Source | Processing Time |
| :--- | :--- | :--- |
| **Amount** | Request | 0.1ms |
| **Velocity (1h)** | Redis ZSET | 2.4ms |
| **Inference** | XGBoost | 18.0ms |
| **SHAP (if needed)**| TreeExplainer | 10.0ms |