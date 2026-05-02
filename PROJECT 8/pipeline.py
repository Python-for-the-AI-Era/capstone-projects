import pandas as pd
import logging

def process_sales_data(file_path: str):
    """
    FAULTY PIPELINE:
    This code assumes 'revenue' is always a float. 
    When Pandas encounters 'N/A' or '-', it may cast the whole column 
    to 'object' type, and sum() might skip non-numeric values silently.
    """
    df = pd.read_csv(file_path)
    
    # The CFO's nightmare: Silent exclusion of invalid data
    regional_totals = df.groupby('region')['revenue'].sum().reset_index()
    
    return regional_totals

# TASK: The student must inject a validation layer here to catch 'N/A' strings.