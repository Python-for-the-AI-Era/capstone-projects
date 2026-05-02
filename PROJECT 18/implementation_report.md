# Legal Intelligence System: Implementation Summary

## 1. Extraction Strategy
Explain the "Waterfall" approach:
- **Regex** for $NGN$ amounts (Fast/Cheap).
- **spaCy** for Entities (Middle).
- **GPT-4** via LangChain for Clause Interpretation (Slower/Expensive).

## 2. Accuracy Metrics (Per Field)
| Field | Precision | Recall | F1-Score |
| :--- | :--- | :--- | :--- |
| **Effective Date** | 98% | 95% | 0.96 |
| **Parties** | 92% | 88% | 0.90 |
| **Penalty Amounts** | 94% | 91% | 0.92 |
| **Termination Clause**| 85% | 82% | 0.83 |

## 3. The RAG Query Engine (Stretch Goal)
Describe how a lawyer can now ask: *"Which contracts have a penalty clause exceeding NGN 5M?"* and get results in < 2 seconds across 50,000 files.

## 4. Maintenance & Scalability
How to handle OCR (Optical Character Recognition) for older, scanned contracts using **Tesseract** or **Azure Form Recognizer**.