import pdfplumber

def extract_transactions(pdf_path):
    transactions = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            # Task 1: Handle varying formats with table_settings
            table = page.extract_table(table_settings={
                "vertical_strategy": "lines",
                "horizontal_strategy": "text"
            })
            if table:
                # Clean headers and extract rows
                transactions.extend(table[1:]) 
    return transactions