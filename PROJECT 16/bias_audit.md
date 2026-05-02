# Bias Audit Report: NairaVoice Sentiment Engine

## 1. The "Default Negative" Crisis
Explain why the model classified Pidgin as Negative. 
- **Tokenization:** How many Pidgin words were flagged as `[UNK]`?
- **Bias Stats:** Before the fix, the model had a **78% False Negative Rate** for Nigerian Pidgin.

## 2. Dataset Evolution

Explain the importance of the 30/70 split in preventing "Model Drift."

## 3. Retraining Results
| Metric | English (Before) | Pidgin (Before) | Pidgin (After Fix) |
| :--- | :--- | :--- | :--- |
| **Precision** | 0.91 | 0.22 | 0.88 |
| **Recall** | 0.89 | 0.15 | 0.85 |
| **F1-Score** | 0.90 | 0.18 | 0.86 |

## 4. The Linguistic Routing (Stretch Goal)
Explain how the `FastText` language detector identifies Pidgin and routes it to the specific classifier, ensuring "Omo, the service na fire!" is correctly identified as a 5-star review.