from fastapi import FastAPI, Depends, HTTPException
from auth_utils import get_current_user

app = FastAPI(title="Kofiso Health API")

# Mock Database
records_db = {
    1: {"id": 1, "owner_id": 1, "data": "Blood Type: O+, Patient: Praise"},
    2: {"id": 2, "owner_id": 2, "data": "Blood Type: A-, Patient: John Doe"}
}

@app.get("/records/{user_id}")
async def get_record(user_id: int, current_user: dict = Depends(get_current_user)):
    """
    CRITICAL VULNERABILITY: 
    It checks if you are A user, but not if you are THE user.
    """
    record = records_db.get(user_id)
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")
    
    return record

# TASK 4: User needs to implement audit logging here