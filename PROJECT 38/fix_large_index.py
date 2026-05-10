#!/usr/bin/env python3
"""
Fix the large and corrupted legal_precedents.index file
"""

import os
import faiss
import pandas as pd
from sentence_transformers import SentenceTransformer
import numpy as np
import gc

def diagnose_index_file():
    """Diagnose the problematic index file"""
    index_file = "legal_precedents.index"
    
    if not os.path.exists(index_file):
        print(f"Index file {index_file} does not exist")
        return
    
    file_size = os.path.getsize(index_file)
    print(f"Current index file size: {file_size / (1024*1024):.2f} MB")
    
    # Try to read the index
    try:
        index = faiss.read_index(index_file)
        print(f"Index loaded successfully")
        print(f"Index type: {type(index)}")
        print(f"Vector count: {index.ntotal}")
        print(f"Dimension: {index.d if hasattr(index, 'd') else 'Unknown'}")
        
        # Check if it's corrupted
        if index.ntotal == 0:
            print("WARNING: Index appears to be empty or corrupted")
            return False
        
        return True
        
    except Exception as e:
        print(f"ERROR: Failed to read index: {e}")
        return False

def rebuild_index_from_source():
    """Rebuild index from original CSV data with optimizations"""
    csv_file = "legal_cases.csv"
    
    if not os.path.exists(csv_file):
        print(f"Source CSV file {csv_file} not found")
        return False
    
    print("Rebuilding index from source data...")
    
    try:
        # Load data
        df = pd.read_csv(csv_file)
        summaries = df['summary'].tolist()
        print(f"Loaded {len(summaries)} documents")
        
        # Load model
        model = SentenceTransformer('all-MiniLM-L6-v2')
        
        # Get embedding dimension
        sample_embedding = model.encode([summaries[0]])
        dimension = sample_embedding.shape[1]
        print(f"Embedding dimension: {dimension}")
        
        # Create optimized index
        nlist = min(1000, len(summaries) // 10)  # Number of clusters
        m = 8  # PQ sub-quantizers
        index = faiss.IndexIVFPQ(faiss.IndexFlatIP(dimension), dimension, nlist, m, 8)
        
        # Train index with sample data
        print("Training index...")
        sample_size = min(10000, len(summaries))
        sample_embeddings = model.encode(summaries[:sample_size], batch_size=512)
        faiss.normalize_L2(sample_embeddings)
        index.train(sample_embeddings)
        index.nprobe = min(10, nlist)
        
        # Add vectors in batches
        batch_size = 256
        total_processed = 0
        
        for i in range(0, len(summaries), batch_size):
            batch_summaries = summaries[i:i + batch_size]
            
            print(f"Processing batch {i//batch_size + 1}/{(len(summaries) + batch_size - 1)//batch_size}...")
            
            # Encode batch
            batch_embeddings = model.encode(batch_summaries, batch_size=128)
            faiss.normalize_L2(batch_embeddings)
            
            # Convert to float16 for size reduction
            batch_embeddings = batch_embeddings.astype(np.float16)
            
            # Add to index
            index.add(batch_embeddings)
            
            total_processed += len(batch_summaries)
            
            # Clean up
            del batch_embeddings
            gc.collect()
        
        # Backup old index
        if os.path.exists("legal_precedents.index"):
            backup_file = "legal_precedents.index.backup"
            os.rename("legal_precedents.index", backup_file)
            print(f"Old index backed up to {backup_file}")
        
        # Save new index
        faiss.write_index(index, "legal_precedents.index")
        
        # Check new file size
        new_size = os.path.getsize("legal_precedents.index")
        print(f"New index file size: {new_size / (1024*1024):.2f} MB")
        print(f"Size reduction: {(file_size - new_size) / (1024*1024):.2f} MB")
        
        # Save metadata
        df[['case_id', 'title']].to_csv("metadata.csv", index=False)
        
        print(f"Successfully rebuilt index with {total_processed:,} vectors")
        return True
        
    except Exception as e:
        print(f"ERROR: Failed to rebuild index: {e}")
        return False

def create_minimal_index():
    """Create a minimal test index"""
    print("Creating minimal test index...")
    
    try:
        # Sample data
        sample_texts = [
            "This is a test case about contract law.",
            "This is a test case about tort law.",
            "This is a test case about criminal law.",
            "This is a test case about civil procedure.",
            "This is a test case about constitutional law."
        ]
        
        # Load model
        model = SentenceTransformer('all-MiniLM-L6-v2')
        
        # Encode
        embeddings = model.encode(sample_texts)
        faiss.normalize_L2(embeddings)
        
        # Create simple index
        dimension = embeddings.shape[1]
        index = faiss.IndexFlatIP(dimension)
        index.add(embeddings)
        
        # Save test index
        faiss.write_index(index, "test_index.index")
        
        # Save test metadata
        test_df = pd.DataFrame({
            'case_id': ['test_1', 'test_2', 'test_3', 'test_4', 'test_5'],
            'title': ['Test Case 1', 'Test Case 2', 'Test Case 3', 'Test Case 4', 'Test Case 5'],
            'summary': sample_texts
        })
        test_df.to_csv("test_metadata.csv", index=False)
        
        test_size = os.path.getsize("test_index.index")
        print(f"Test index created: {test_size / 1024:.2f} KB")
        print("Test index contains 5 sample documents")
        
        return True
        
    except Exception as e:
        print(f"ERROR: Failed to create test index: {e}")
        return False

def main():
    """Main function to fix the large index file"""
    print("=" * 60)
    print("LEGAL PRECEDENTS INDEX REPAIR TOOL")
    print("=" * 60)
    
    # Step 1: Diagnose current index
    print("\n1. Diagnosing current index file...")
    is_valid = diagnose_index_file()
    
    if not is_valid:
        print("\n2. Index is corrupted or invalid, rebuilding from source...")
        
        # Step 2: Rebuild from source
        if rebuild_index_from_source():
            print("\n3. Index rebuilt successfully!")
        else:
            print("\n3. Failed to rebuild index, creating minimal test index...")
            create_minimal_index()
    else:
        print("\n2. Index is valid but large, creating optimized version...")
        
        # Create optimized version
        from compact_indexer import build_compact_index
        build_compact_index("legal_cases.csv", batch_size=256, use_quantization=True)
    
    print("\n" + "=" * 60)
    print("REPAIR COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    main()
