import pytest
from pipeline import process_sales_data
import pandas as pd

def test_data_integrity():
    # Load the generated file
    df = pd.read_csv('daily_sales.csv')
    
    # Calculate what the sum SHOULD be (treating N/A as 0 for this test)
    # The current pipeline will likely return a lower number.
    expected_sum = 1000000.0 
    
    result_df = process_sales_data('daily_sales.csv')
    actual_sum = result_df['revenue'].sum()
    
    print(f"\nExpected: {expected_sum}")
    print(f"Actual: {actual_sum}")
    print(f"Discrepancy: {expected_sum - actual_sum}")
    
    # This will FAIL until the student fixes the ingestion
    assert actual_sum == expected_sum