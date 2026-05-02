def get_shap_explanation(features):
    """
    TASK: Use SHAP TreeExplainer to find the top 3 contributors.
    Return: {"high_amount": +0.45, "unusual_velocity": +0.22, ...}
    """
    shap_values = app.state.explainer.shap_values(features)
    # Student implements logic to map indices back to feature names
    return top_3_impacts