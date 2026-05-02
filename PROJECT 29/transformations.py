def transform_transactions(ds, **kwargs):
    df = pd.read_parquet(f"/tmp/transactions_{ds}.parquet")
    
    # TASK 4: Normalize Currency
    # Assuming 'currency' and 'amount' columns exist
    exchange_rates = {"USD": 1450, "GBP": 1800, "NGN": 1}
    df['amount_ngn'] = df.apply(
        lambda x: x['amount'] * exchange_rates.get(x['currency'], 1), axis=1
    )
    
    # Enrich with Fraud Score (using a pre-loaded model)
    # df['fraud_flag'] = model.predict(df)
    
    df.to_parquet(f"/tmp/transformed_{ds}.parquet")