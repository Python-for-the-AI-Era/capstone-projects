import pandas as pd
from sklearn.ensemble import RandomForestClassifier

def train_leaky_model(df):
    """
    FAULTY LOGIC:
    'late_payment_count' and 'repayment_status' are updated dynamically.
    If you train on a snapshot from today, these features tell the model 
    the outcome before it even makes a prediction.
    """
    features = [
        'income', 'credit_score', 'loan_amount', 
        'late_payment_count', # LEAKAGE: Known only after loan start
        'repayment_status'    # LEAKAGE: This IS the target in disguise
    ]
    
    X = df[features]
    y = df['defaulted']
    
    model = RandomForestClassifier()
    model.fit(X, y)
    return model