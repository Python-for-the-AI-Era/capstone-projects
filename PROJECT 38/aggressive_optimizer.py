#!/usr/bin/env python3
"""
Aggressive optimization to get index file under 100MB
"""

import os
import faiss
import pandas as pd
from sentence_transformers import SentenceTransformer
import numpy as np
import gc

def create_ultra_compact_index(csv_path, target_size_mb=50):
    """Create ultra-compact index to get under target size"""
    print(f"Creating ultra-compact index targeting {target_size_mb}MB...")
    
    # Load data
    df = pd.read_csv(csv_path)
    summaries = df['summary'].tolist()
    print(f"Processing {len(summaries)} documents...")
    
    # Load model
    model = SentenceTransformer('all-MiniLM-L6-v2')
    
    # Get embedding dimension
    sample_embedding = model.encode([summaries[0]])
    dimension = sample_embedding.shape[1]
    print(f"Embedding dimension: {dimension}")
    
    # Try different compression levels
    configs = [
        ("IVF+PQ_8bit", 8, 8, 1000),    # 8-bit PQ, 8 sub-quantizers
        ("IVF+PQ_6bit", 6, 8, 800),     # 6-bit PQ, more aggressive
        ("IVF+PQ_4bit", 4, 8, 600),     # 4-bit PQ, very aggressive
        ("IVF+Scalar", None, None, 400),   # IVF with scalar quantization
    ]
    
    best_config = None
    best_size = float('inf')
    
    for name, bits, m, nlist in configs:
        print(f"\nTrying {name} configuration...")
        
        try:
            # Create index
            if bits is None:
                # IVF with scalar quantization
                index = faiss.IndexIVFScalarQuantizer(
                    faiss.IndexFlatIP(dimension), dimension, nlist, faiss.ScalarQuantizer.QT_8bit
                )
            else:
                # IVF with PQ
                index = faiss.IndexIVFPQ(
                    faiss.IndexFlatIP(dimension), dimension, nlist, m, bits
                )
            
            # Train with sample
            sample_size = min(5000, len(summaries))
            sample_embeddings = model.encode(summaries[:sample_size], batch_size=256)
            faiss.normalize_L2(sample_embeddings)
            
            index.train(sample_embeddings)
            index.nprobe = min(10, nlist)
            
            # Add small batch to test size
            test_batch = summaries[:1000]
            test_embeddings = model.encode(test_batch, batch_size=128)
            faiss.normalize_L2(test_embeddings)
            
            # Convert to uint8 for maximum compression
            test_embeddings = test_embeddings.astype(np.uint8)
            index.add(test_embeddings)
            
            # Test file size
            test_file = f"test_{name.lower().replace('+', '_')}.index"
            faiss.write_index(index, test_file)
            
            file_size = os.path.getsize(test_file)
            size_mb = file_size / (1024 * 1024)
            
            print(f"  {name}: {size_mb:.2f} MB")
            
            if size_mb < best_size:
                best_size = size_mb
                best_config = (name, bits, m, nlist)
            
            # Clean up
            os.remove(test_file)
            del index, test_embeddings
            gc.collect()
            
        except Exception as e:
            print(f"  {name}: Failed - {e}")
            continue
    
    if best_config:
        print(f"\nBest configuration: {best_config[0]} ({best_size:.2f} MB)")
        return build_with_config(summaries, model, best_config, df)
    else:
        print("No valid configuration found")
        return None

def build_with_config(summaries, model, config, df):
    """Build full index with best configuration"""
    name, bits, m, nlist = config
    
    print(f"\nBuilding full index with {name}...")
    
    # Create index
    dimension = model.encode([summaries[0]]).shape[1]
    
    if bits is None:
        index = faiss.IndexIVFScalarQuantizer(
            faiss.IndexFlatIP(dimension), dimension, nlist, faiss.ScalarQuantizer.QT_8bit
        )
    else:
        index = faiss.IndexIVFPQ(
            faiss.IndexFlatIP(dimension), dimension, nlist, m, bits
        )
    
    # Train index
    sample_size = min(10000, len(summaries))
    sample_embeddings = model.encode(summaries[:sample_size], batch_size=512)
    faiss.normalize_L2(sample_embeddings)
    index.train(sample_embeddings)
    index.nprobe = min(10, nlist)
    
    # Add all vectors in small batches
    batch_size = 100
    total_processed = 0
    
    for i in range(0, len(summaries), batch_size):
        batch_summaries = summaries[i:i + batch_size]
        
        print(f"Processing batch {i//batch_size + 1}/{(len(summaries) + batch_size - 1)//batch_size}...")
        
        # Encode batch
        batch_embeddings = model.encode(batch_summaries, batch_size=64)
        faiss.normalize_L2(batch_embeddings)
        
        # Maximum compression - uint8
        batch_embeddings = batch_embeddings.astype(np.uint8)
        
        # Add to index
        index.add(batch_embeddings)
        
        total_processed += len(batch_summaries)
        
        # Clean up
        del batch_embeddings
        gc.collect()
    
    # Save index
    output_file = "legal_precedents_optimized.index"
    faiss.write_index(index, output_file)
    
    # Check final size
    final_size = os.path.getsize(output_file)
    final_size_mb = final_size / (1024 * 1024)
    
    print(f"\nFinal optimized index: {final_size_mb:.2f} MB")
    print(f"Documents indexed: {total_processed:,}")
    
    # Backup and replace original
    if os.path.exists("legal_precedents.index"):
        backup_file = "legal_precedents.index.backup"
        os.rename("legal_precedents.index", backup_file)
        print(f"Original backed up to {backup_file}")
    
    os.rename(output_file, "legal_precedents.index")
    print(f"Optimized index saved as legal_precedents.index")
    
    # Save metadata
    df[['case_id', 'title']].to_csv("metadata.csv", index=False)
    
    return final_size_mb < 100

def create_minimal_viable_index(csv_path):
    """Create minimal viable index with reduced dataset"""
    print("Creating minimal viable index...")
    
    # Load and sample data
    df = pd.read_csv(csv_path)
    
    # Take a representative sample
    sample_size = min(20000, len(df))  # Limit to 20k documents
    df_sample = df.sample(n=sample_size, random_state=42)
    summaries = df_sample['summary'].tolist()
    
    print(f"Sampled {len(summaries)} documents from {len(df)} total")
    
    # Load model
    model = SentenceTransformer('all-MiniLM-L6-v2')
    
    # Create highly compressed index
    dimension = model.encode([summaries[0]]).shape[1]
    nlist = min(500, len(summaries) // 20)  # Fewer clusters
    
    # Use aggressive PQ quantization
    index = faiss.IndexIVFPQ(
        faiss.IndexFlatIP(dimension), dimension, nlist, 4, 4  # Very aggressive
    )
    
    # Train
    sample_embeddings = model.encode(summaries[:min(5000, len(summaries))], batch_size=256)
    faiss.normalize_L2(sample_embeddings)
    index.train(sample_embeddings)
    index.nprobe = min(5, nlist)
    
    # Add vectors
    batch_size = 200
    for i in range(0, len(summaries), batch_size):
        batch_summaries = summaries[i:i + batch_size]
        
        # Encode and compress
        batch_embeddings = model.encode(batch_summaries, batch_size=64)
        faiss.normalize_L2(batch_embeddings)
        batch_embeddings = batch_embeddings.astype(np.uint8)  # Maximum compression
        
        index.add(batch_embeddings)
        
        print(f"Added {min(i + batch_size, len(summaries)):,} / {len(summaries):,} documents")
        
        del batch_embeddings
        gc.collect()
    
    # Save minimal index
    output_file = "legal_precedents_minimal.index"
    faiss.write_index(index, output_file)
    
    # Check size
    file_size = os.path.getsize(output_file)
    size_mb = file_size / (1024 * 1024)
    
    print(f"Minimal index size: {size_mb:.2f} MB")
    
    # Save sampled metadata
    df_sample[['case_id', 'title']].to_csv("metadata_minimal.csv", index=False)
    
    return size_mb

def main():
    """Main optimization function"""
    print("=" * 60)
    print("AGGRESSIVE INDEX OPTIMIZATION")
    print("=" * 60)
    
    csv_path = "legal_cases.csv"
    
    if not os.path.exists(csv_path):
        print(f"Error: {csv_path} not found")
        return
    
    # Try ultra-compact first
    result = create_ultra_compact_index(csv_path, target_size_mb=50)
    
    if result is False or result is None:
        print("\nUltra-compact failed, trying minimal viable index...")
        size_mb = create_minimal_viable_index(csv_path)
        
        if size_mb < 100:
            print(f"\n✅ Success! Minimal index is {size_mb:.2f} MB")
            
            # Replace original
            if os.path.exists("legal_precedents.index"):
                os.rename("legal_precedents.index", "legal_precedents.index.backup2")
            os.rename("legal_precedents_minimal.index", "legal_precedents.index")
            os.rename("metadata_minimal.csv", "metadata.csv")
            
            print("Original index backed up and replaced with minimal version")
        else:
            print(f"❌ Failed: Minimal index is still {size_mb:.2f} MB")
    else:
        print(f"\n✅ Success! Optimized index is under 100MB")
    
    # Final check
    if os.path.exists("legal_precedents.index"):
        final_size = os.path.getsize("legal_precedents.index") / (1024 * 1024)
        print(f"\nFinal index size: {final_size:.2f} MB")
        
        if final_size < 100:
            print("🎉 SUCCESS: Index is now under 100MB!")
        else:
            print("⚠️  WARNING: Index is still over 100MB")

if __name__ == "__main__":
    main()
