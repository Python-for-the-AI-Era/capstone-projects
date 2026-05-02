from sqlalchemy import text
from fastapi import HTTPException

async def create_order(db_session, user_id, product_id):
    # TASK 3: Atomic Update with RETURNING
    # This happens in a single database step. No two processes can "split" this.
    query = text("""
        UPDATE inventory 
        SET stock = stock - 1 
        WHERE id = :prod_id AND stock > 0 
        RETURNING stock
    """)
    
    result = await db_session.execute(query, {"prod_id": product_id})
    updated_row = result.fetchone()

    if not updated_row:
        # If no row was updated, it means stock was 0
        raise HTTPException(status_code=400, detail="Out of Stock")

    # Proceed to create the order record...
    return {"status": "success", "remaining_stock": updated_row[0]}