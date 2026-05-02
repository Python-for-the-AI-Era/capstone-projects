# Forensic Audit: CreditPulse Default Model

## 1. The Root Cause: Target Leakage
Explain how `late_payment_count` acted as a "proxy" for the target. 
In training, the model saw that people who defaulted had high late payments. 
In production, a new applicant has *zero* late payments for the *new* loan, 
so the model loses its strongest signal.

## 2. SHAP Analysis Results
- **Top Feature:** `repayment_status` (SHAP Value: 0.82)
- **Conclusion:** The model was not predicting creditworthiness; 
  it was merely restating the current status of the loan.

## 3. Temporal Validation Impact
| Split Method | Training AUC | Testing AUC |
| :--- | :--- | :--- |
| **Random Split** | 0.88 | 0.87 (Fake) |
| **Temporal Split**| 0.64 | 0.61 (Real) |

## 4. The Path Forward (Stretch Goal)
Describe the **Population Stability Index (PSI)** monitor. 
If the distribution of 'income' in our applicants changes significantly 
compared to our training data, the model must be retrained.