from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession
from models import Order

async def get_monthly_sales_total(db: AsyncSession, month: int):
    """
    CRITICAL PERFORMANCE BUG: 
    Using EXTRACT(month FROM ...) forces PostgreSQL to calculate the month 
    for 40 million rows before it can filter them. This is an O(N) operation.
    """
    # FAULTY QUERY
    query = select(func.sum(Order.amount)).where(
        func.extract('month', Order.created_at) == month
    )
    
    result = await db.execute(query)
    return result.scalar()