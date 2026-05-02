# Task 3: Memory-efficient aggregation
total_revenue = 0

for chunk in pd.read_csv("large_data.csv", chunksize=50000, dtype=dtypes):
    # Process the chunk (e.g., filter or aggregate)
    total_revenue += chunk['amount'].sum()
    
print(f"Total Revenue: {total_revenue}")