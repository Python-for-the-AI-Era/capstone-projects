# Personal Finance CLI: Technical Specs

## 1. Data Pipeline
- **Parsing:** Handles multi-page PDFs using `pdfplumber`. 
- **Persistence:** SQLite database with an index on `date` for fast querying.
- **AI Integration:** Uses a 'Rule-First' fallback to LLM. This reduced LLM calls by 70% during testing.

## 2. Supported Banks
- **Standard Format A:** (Date, Description, Debit, Credit, Balance)
- **Standard Format B:** (Transaction Date, Remarks, Amount)

## 3. Financial Insights
The tool identifies "Subscription Creep" by grouping identical monthly amounts and flagging them for review.

## 4. Privacy Note
All data is stored locally. The LLM only receives transaction descriptions, never full bank account numbers or personally identifiable information (PII).