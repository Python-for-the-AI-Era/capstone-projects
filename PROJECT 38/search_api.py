from fastapi import FastAPI
import faiss
from sentence_transformers import SentenceTransformer

app = FastAPI()

@app.on_event("startup")
def load_assets():
    # Store in app state for high-speed concurrent access
    app.state.model = SentenceTransformer('all-MiniLM-L6-v2')
    app.state.index = faiss.read_index("legal_precedents.index")
    # Load metadata (titles/IDs) to map back index results
    app.state.metadata = pd.read_csv("metadata.csv")

@app.post("/search")
async def search(query: str, k: int = 5):
    # 1. Embed query
    query_vector = app.state.model.encode([query])
    faiss.normalize_L2(query_vector)
    
    # 2. Vector Search
    scores, indices = app.state.index.search(query_vector, k)
    
    # 3. Map Results
    results = []
    for i, idx in enumerate(indices[0]):
        results.append({
            "doc_id": int(idx),
            "score": float(scores[0][i]),
            "title": app.state.metadata.iloc[idx]['title']
        })
    return results