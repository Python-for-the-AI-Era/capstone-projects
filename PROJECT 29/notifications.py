def send_summary_email(ds, **kwargs):
    # Fetch KPIs from the transformed dataset
    # Total Volume, Total Fraud Flags, Avg Transaction Size
    
    html_content = f"""
    <h3>Kuda Bank Daily Transaction Summary ({ds})</h3>
    <ul>
        <li><b>Total Volume:</b> ₦{total_volume:,.2f}</li>
        <li><b>Fraud Alerts:</b> {fraud_count}</li>
    </ul>
    """
    # Logic to send email via SMTP