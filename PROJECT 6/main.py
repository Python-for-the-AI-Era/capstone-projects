from fastapi import FastAPI, Depends
from sqlalchemy.ext.asyncio import AsyncSession
import analytics
import database

app = FastAPI()

@app.get("/admin/analytics/monthly-total/{month}")
async def monthly_total(month: int, db: AsyncSession = Depends(database.get_db)):
    # TASK: Wrap this in Redis caching
    # TASK: Set a statement_timeout so the DB doesn't hang for 14 minutes
    data = await analytics.get_monthly_sales_total(db, month)
    return {"total_sales": data}