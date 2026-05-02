import pandas as pd

def audit_memory(csv_path):
    # Read a sample to see what we're dealing with
    df = pd.read_csv(csv_path, nrows=100000)
    
    # deep=True is essential for strings/objects
    usage = df.memory_usage(deep=True) / (1024**2) # Convert to MB
    print(f"Memory usage per column (MB):\n{usage}")
    
    # Identify candidates for 'category' (low cardinality strings)
    for col in df.select_dtypes(include=['object']):
        unique_ratio = df[col].nunique() / len(df)
        if unique_ratio < 0.05:
            print(f"Suggestion: Convert {col} to 'category'")