# Data Integrity Report: Redbrick Analytics

## 1. Incident Analysis
Explain why `df.groupby().sum()` produced incorrect results without raising an error. 
(Hint: Discuss how Pandas handles `object` vs `float64` dtypes).

## 2. The Validation Layer
- **Fail-Loudly Policy:** Explain the 1% threshold. Why is it better to crash the pipeline than to produce a wrong number?
- **Logging:** Show an example of the row-level error logs generated.

## 3. Reconciliation Results
Show the final "True Sum" comparison. 
**Formula used:** `abs(CleanedSum - AggregatedSum) < 0.00001`

## 4. Modernization (Stretch Goal)
Compare the performance of the Pandas version vs. the Polars version on a 1-million-row dataset.