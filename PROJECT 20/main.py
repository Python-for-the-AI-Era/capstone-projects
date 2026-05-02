from fastapi import FastAPI, Request, HTTPException
import joblib
import redis.asyncio as redis
from xgboost import XGBClassifier

app = FastAPI()
r = redis.from_url("redis://localhost:6379", decode_responses=True)

@app.on_event("startup")
async def startup_event():
    # Load model and explainer into memory once
    app.state.model = joblib.load("fraud_model_v1.pkl")
    app.state.explainer = joblib.load("shap_explainer.pkl")

@app.post("/v1/score")
async def score_transaction(data: dict):
    # 1. Feature Engineering (Velocity check via Redis)
    user_id = data['user_id']
    velocity_1h = await get_transaction_velocity(user_id)
    
    # 2. Inference
    features = [data['amount'], data['hour'], velocity_1h, data['merchant_cat']]
    prob = app.state.model.predict_proba([features])[0][1]
    
    # 3. Explainability on-demand
    response = {"is_fraud": prob > 0.7, "score": prob}
    if response["is_fraud"]:
        response["explanation"] = get_shap_explanation(features)
        
    return response