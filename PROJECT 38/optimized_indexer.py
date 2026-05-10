#!/usr/bin/env python3
"""
Optimized indexer for large datasets with memory management
"""

import pandas as pd
from sentence_transformers import SentenceTransformer
import faiss
import numpy as np
import gc

def build_optimized_index(csv_path, batch_size=512):
    """Build FAISS index with memory optimization"""
    print(f"Loading data from {csv_path}...")
    df = pd.read_csv(csv_path)
    summaries = df['summary'].tolist()
    
    print(f"Processing {len(summaries)} documents...")
    
    # Load model
    model = SentenceTransformer('all-MiniLM-L6-v2')
    
    # Get embedding dimension by encoding a sample
    sample_embedding = model.encode([summaries[0]])
    dimension = sample_embedding.shape[1]
    print(f"Embedding dimension: {dimension}")
    
    # Create FAISS index
    index = faiss.IndexFlatIP(dimension)
    
    # Process in batches to manage memory
    total_processed = 0
    for i in range(0, len(summaries), batch_size):
        batch_summaries = summaries[i:i + batch_size]
        
        print(f"Processing batch {i//batch_size + 1}/{(len(summaries) + batch_size - 1)//batch_size}...")
        
        # Encode batch
        batch_embeddings = model.encode(batch_summaries, batch_size=128, show_progress_bar=False)
        
        # Normalize batch
        faiss.normalize_L2(batch_embeddings)
        
        # Add to index
        index.add(batch_embeddings)
        
        total_processed += len(batch_summaries)
        print(f"Added {total_processed:,} documents to index")
        
        # Clean up memory
        del batch_embeddings
        gc.collect()
    
    # Save index
    index_file = "legal_precedents.index"
    faiss.write_index(index, index_file)
    print(f"Index built and saved to {index_file}")
    
    # Save metadata
    metadata_file = "metadata.csv"
    df[['case_id', 'title']].to_csv(metadata_file, index=False)
    print(f"Metadata saved to {metadata_file}")
    
    print(f"Total documents indexed: {total_processed:,}")
    print(f"Index size: {index.ntotal} vectors")
    
    return index, df

if __name__ == "__main__":
    build_optimized_index("legal_cases.csv", batch_size=512)
