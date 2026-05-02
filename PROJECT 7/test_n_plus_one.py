import pytest
from repository import get_all_documents_legacy
from database import engine, AsyncSessionLocal

@pytest.mark.asyncio
async def test_query_efficiency():
    # 1. Setup: Insert 100 documents, 10 authors, and 5 tags
    
    # 2. Start counter
    # 3. Call get_all_documents_legacy()
    
    # EXPECTED: Total queries should be < 5
    # ACTUAL: It will likely be 201+ (1 for docs, 100 for authors, 100 for tags)
    assert query_count < 5