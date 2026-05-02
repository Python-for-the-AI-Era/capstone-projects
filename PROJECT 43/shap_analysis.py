import shap

def compare_importance(model, train_df, prod_df):
    explainer = shap.TreeExplainer(model)
    
    # Compare feature importance rankings
    shap_values_train = explainer.shap_values(train_df)
    shap_values_prod = explainer.shap_values(prod_df)
    
    # Logic to identify if a previously high-importance feature 
    # has lost its predictive power in the current environment.