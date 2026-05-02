# Scoring API Python SDK

## 1. Installation
Install from our internal PyPI:
`pip install ml-scoring-sdk`

## 2. Quick Start
```python
from scoring_sdk import ScoringClient

client = ScoringClient(base_url="[https://ml-api.internal](https://ml-api.internal)", api_key="secret-key")
result = client.score({"user_age": 25.0, "credit_score": 750.0})
print(f"Risk Score: {result.score}")