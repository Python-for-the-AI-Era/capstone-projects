def validate_data(ds, **kwargs):
    import pandas as pd
    df = pd.read_parquet(f"/tmp/transactions_{ds}.parquet")
    
    # 1. Integrity Check
    if df['transaction_id'].isnull().any():
        raise ValueError(f"Data Quality Failed: Null IDs found for {ds}")
        
    # 2. Logic Check
    if (df['amount'] <= 0).any():
        raise ValueError(f"Data Quality Failed: Negative/Zero amounts found for {ds}")
        
    print(f"Validation passed for {len(df)} records.")