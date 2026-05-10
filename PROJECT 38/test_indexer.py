#!/usr/bin/env python3
"""
Test indexer with smaller dataset to debug issues
"""

import pandas as pd
from sentence_transformers import SentenceTransformer
import faiss
import numpy as np

def build_small_index(csv_path, num_samples=1000):
    """Build index with smaller dataset for testing"""
    print(f"Loading data from {csv_path}...")
    df = pd.read_csv(csv_path)
    
    # Take first N samples for testing
    df_sample = df.head(num_samples)
    summaries = df_sample['summary'].tolist()
    
    print(f"Processing {len(summaries)} documents...")
    
    # Load model
    model = SentenceTransformer('all-MiniLM-L6-v2')
    
    # Batch encoding with smaller batches to reduce memory
    print("Encoding documents...")
    embeddings = model.encode(summaries, batch_size=128, show_progress_bar=True)
    
    print(f"Embeddings shape: {embeddings.shape}")
    print(f"Memory usage: {embeddings.nbytes / 1024 / 1024:.1f} MB")
    
    # Normalize for Cosine Similarity
    print("Normalizing vectors...")
    faiss.normalize_L2(embeddings)
    
    # Create FAISS Index
    dimension = embeddings.shape[1]
    index = faiss.IndexFlatIP(dimension)
    
    print("Adding vectors to index...")
    index.add(embeddings)
    
    # Save index
    index_file = "legal_precedents_test.index"
    faiss.write_index(index, index_file)
    print(f"Index built and saved to {index_file}")
    
    # Save sample metadata
    metadata_file = "metadata_test.csv"
    df_sample[['case_id', 'title']].to_csv(metadata_file, index=False)
    print(f"Metadata saved to {metadata_file}")
    
    return index, df_sample

if __name__ == "__main__":
    build_small_index("legal_cases.csv", 1000)
