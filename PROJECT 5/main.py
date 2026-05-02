from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import models, auth

app = FastAPI(title="Formify SaaS")

@app.get("/forms/{form_id}")
async def get_form(form_id: int, user: dict = Depends(auth.get_current_user)):
    """
    CRITICAL DESIGN FLAW: 
    This query looks for the form ID globally. 
    It doesn't care if the user belongs to the same Org as the form.
    """
    # TASK: Update this to use a scoped query: 
    # select(Form).where(Form.id == form_id, Form.org_id == user['org_id'])
    return {"message": "Returning form data (potentially from another tenant!)"}