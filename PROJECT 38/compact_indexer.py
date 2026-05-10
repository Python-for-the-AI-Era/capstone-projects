#!/usr/bin/env python3
"""
Compact indexer to reduce index file size and improve performance
"""

import pandas as pd
from sentence_transformers import SentenceTransformer
import faiss
import numpy as np
import gc
import os

def build_compact_index(csv_path, batch_size=256, use_quantization=True):
    """Build compact FAISS index with size optimization"""
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
    
    # Create compact index with quantization
    if use_quantization:
        # Use IVF + PQ for compact storage
        nlist = min(1000, len(summaries) // 10)  # Number of clusters
        m = 8  # PQ sub-quantizers
        index = faiss.IndexIVFPQ(faiss.IndexFlatIP(dimension), dimension, nlist, m, 8)
        
        # Train the index
        print("Training index...")
        sample_embeddings = model.encode(summaries[:min(10000, len(summaries))], batch_size=512)
        faiss.normalize_L2(sample_embeddings)
        index.train(sample_embeddings)
        index.nprobe = min(10, nlist)  # Number of clusters to search
        
    else:
        # Use flat index with reduced precision
        index = faiss.IndexFlatIP(dimension)
    
    # Process in smaller batches to manage memory
    total_processed = 0
    for i in range(0, len(summaries), batch_size):
        batch_summaries = summaries[i:i + batch_size]
        
        print(f"Processing batch {i//batch_size + 1}/{(len(summaries) + batch_size - 1)//batch_size}...")
        
        # Encode batch
        batch_embeddings = model.encode(batch_summaries, batch_size=64, show_progress_bar=False)
        
        # Normalize batch for cosine similarity
        faiss.normalize_L2(batch_embeddings)
        
        # Convert to float16 to reduce size
        batch_embeddings = batch_embeddings.astype(np.float16)
        
        # Add to index
        index.add(batch_embeddings)
        
        total_processed += len(batch_summaries)
        print(f"Added {total_processed:,} documents to index")
        
        # Clean up memory
        del batch_embeddings
        gc.collect()
    
    # Save compact index
    index_file = "legal_precedents_compact.index"
    faiss.write_index(index, index_file)
    print(f"Compact index built and saved to {index_file}")
    
    # Get file size
    file_size = os.path.getsize(index_file)
    print(f"Index file size: {file_size / (1024*1024):.2f} MB")
    
    # Save metadata
    metadata_file = "metadata_compact.csv"
    df[['case_id', 'title']].to_csv(metadata_file, index=False)
    print(f"Metadata saved to {metadata_file}")
    
    print(f"Total documents indexed: {total_processed:,}")
    print(f"Index size: {index.ntotal} vectors")
    
    return index, df

def test_index_size():
    """Test different index configurations to find optimal size"""
    print("Testing different index configurations...")
    
    # Load sample data
    df = pd.read_csv("legal_cases.csv")
    summaries = df['summary'].tolist()[:1000]  # Use sample for testing
    
    model = SentenceTransformer('all-MiniLM-L6-v2')
    sample_embedding = model.encode([summaries[0]])
    dimension = sample_embedding.shape[1]
    
    # Test different configurations
    configs = [
        ("FlatIP", lambda d: faiss.IndexFlatIP(dimension)),
        ("IVF", lambda d: faiss.IndexIVFFlat(faiss.IndexFlatIP(dimension), d, min(100, len(summaries)//10))),
        ("IVF+PQ", lambda d: faiss.IndexIVFPQ(faiss.IndexFlatIP(dimension), d, min(100, len(summaries)//10), 8, 8)),
    ]
    
    for name, create_index in configs:
        print(f"\nTesting {name} index...")
        
        # Encode sample
        embeddings = model.encode(summaries, batch_size=256)
        faiss.normalize_L2(embeddings)
        
        # Create and train index
        index = create_index(dimension)
        if hasattr(index, 'train'):
            index.train(embeddings)
        index.add(embeddings)
        
        # Save and check size
        test_file = f"test_{name.lower()}.index"
        faiss.write_index(index, test_file)
        file_size = os.path.getsize(test_file)
        
        print(f"  Index size: {file_size / (1024*1024):.2f} MB")
        print(f"  Vectors: {index.ntotal}")
        
        # Clean up
        os.remove(test_file)
        del index, embeddings
        gc.collect()

if __name__ == "__main__":
    # First test different configurations
    test_index_size()
    
    print("\n" + "="*50)
    print("Building optimized compact index...")
    
    # Build the compact index
    build_compact_index("legal_cases.csv", batch_size=256, use_quantization=True)
