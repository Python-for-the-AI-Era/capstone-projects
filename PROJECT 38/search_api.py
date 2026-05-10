from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import faiss
from sentence_transformers import SentenceTransformer
import pandas as pd

app = FastAPI()

class SearchRequest(BaseModel):
    query: str
    k: int = 5

@app.on_event("startup")
def load_assets():
    # Store in app state for high-speed concurrent access
    app.state.model = SentenceTransformer('all-MiniLM-L6-v2')
    app.state.index = faiss.read_index("legal_precedents.index")
    # Load metadata (titles/IDs) to map back index results
    app.state.metadata = pd.read_csv("metadata.csv")

@app.post("/search")
async def search(request: SearchRequest):
    try:
        # Validate inputs
        if not request.query or len(request.query.strip()) == 0:
            raise ValueError("Query cannot be empty")
        
        if request.k < 1 or request.k > 100:
            raise ValueError("k must be between 1 and 100")
        
        # 1. Embed query
        query_vector = app.state.model.encode([request.query])
        faiss.normalize_L2(query_vector)
        
        # 2. Vector Search
        scores, indices = app.state.index.search(query_vector, request.k)
        
        # 3. Map Results
        results = []
        for i, idx in enumerate(indices[0]):
            if idx >= 0 and idx < len(app.state.metadata):  # Bounds check
                results.append({
                    "doc_id": int(idx),
                    "score": float(scores[0][i]),
                    "title": app.state.metadata.iloc[idx]['title']
                })
        
        return {"results": results, "query": request.query, "k": request.k}
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

@app.get("/")
async def root():
    return {"message": "Document Similarity Search Engine API", "version": "1.0.0"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "index_loaded": hasattr(app.state, 'index')}