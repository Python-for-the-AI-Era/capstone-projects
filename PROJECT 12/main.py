import asyncio
from fastapi import FastAPI
from parser import parse_heavy_financial_csv

app = FastAPI()

@app.get("/reconcile")
async def reconcile_data():
    """
    CRITICAL BUG: This async function calls a sync function directly.
    When this runs, the entire FastAPI process STOPS responding 
    to all other requests until this returns.
    """
    result = parse_heavy_financial_csv("transactions.csv")
    return result

@app.get("/health")
async def health_check():
    """
    In a healthy async app, this should return in < 10ms.
    If /reconcile is running, this will hang for 3-5 seconds.
    """
    return {"status": "ok"}