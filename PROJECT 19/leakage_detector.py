import shap

def audit_model_importance(model, X):
    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(X)
    
    # TASK: Visualize the SHAP values. 
    # If 'repayment_status' has a massive bar, the model has found the leak.
    shap.summary_plot(shap_values, X)