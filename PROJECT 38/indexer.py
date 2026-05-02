import pandas as pd
from sentence_transformers import SentenceTransformer
import faiss
import numpy as np

# 1. Load Model (Lightweight but powerful for 384-dimension embeddings)
model = SentenceTransformer('all-MiniLM-L6-v2')

def build_index(csv_path):
    df = pd.read_csv(csv_path)
    summaries = df['summary'].tolist()
    
    # 2. Batch Encoding
    embeddings = model.encode(summaries, batch_size=512, show_progress_bar=True)
    
    # 3. Normalise for Cosine Similarity (Inner Product)
    faiss.normalize_L2(embeddings)
    
    # 4. Create FAISS Index
    dimension = embeddings.shape[1]
    index = faiss.IndexFlatIP(dimension)
    index.add(embeddings)
    
    faiss.write_index(index, "legal_precedents.index")
    print("Index built and saved.")