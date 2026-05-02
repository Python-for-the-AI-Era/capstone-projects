def send_drift_alert(old_auc, new_auc, drifted_features):
    message = f"""
    🚨 *Model Retraining Triggered* 🚨
    Model: Loan-Default-v2
    Reason: Drift detected in features: {', '.join(drifted_features)}
    
    *Performance Update:*
    - Pre-retrain AUC: {old_auc:.2f}
    - Post-retrain AUC: {new_auc:.2f}
    - Improvement: +{(new_auc - old_auc):.2f}
    """
    # Logic to push to Slack Webhook