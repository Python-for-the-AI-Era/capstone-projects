from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from models import Document

async def get_all_documents_legacy(db: AsyncSession):
    """
    FAULTY AI-GENERATED CODE:
    This query only fetches the Document table.
    When the API later accesses 'doc.author.name', SQLAlchemy
    is forced to emit a new SELECT query for EVERY SINGLE ROW.
    """
    result = await db.execute(select(Document))
    documents = result.scalars().all()
    
    # Simulating what the serializer (Pydantic) does:
    # This loop is where the N+1 explosion happens.
    report = []
    for doc in documents:
        report.append({
            "title": doc.title,
            "author": doc.author.name,  # TRIGGER: Query N+1
            "tags": [t.name for t in doc.tags] # TRIGGER: Query N+2...
        })
    return report