# Task 2: Optimised Schema
dtypes = {
    'transaction_id': 'int32',
    'customer_region': 'category',  # Huge savings for repeated strings
    'amount': 'float32',
    'is_fraud': 'bool'
}

# Loading with fixed dtypes prevents the initial bloat
df_small = pd.read_csv("large_data.csv", dtype=dtypes)