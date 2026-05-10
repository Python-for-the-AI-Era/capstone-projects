#!/usr/bin/env python3
"""
Setup Git LFS for large files and create alternative solutions
"""

import os
import subprocess
import shutil

def setup_git_lfs():
    """Setup Git LFS for large files"""
    print("Setting up Git LFS for large files...")
    
    # Check if git-lfs is installed
    try:
        subprocess.run(['git-lfs', '--version'], check=True, capture_output=True)
        print("Git LFS is already installed")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("Git LFS not found. Installing...")
        # Instructions for installing git-lfs
        print("""
To install Git LFS:
1. macOS: brew install git-lfs
2. Ubuntu: sudo apt-get install git-lfs
3. Windows: Download from https://git-lfs.github.com/

After installation:
git lfs install
        """)
        return False
    
    # Initialize git lfs
    try:
        subprocess.run(['git', 'lfs', 'install'], check=True)
        print("Git LFS initialized")
    except subprocess.CalledProcessError as e:
        print(f"Failed to initialize Git LFS: {e}")
        return False
    
    # Add large file patterns
    lfs_patterns = [
        "*.index",
        "*.backup",
        "*.large",
        "data/*.large"
    ]
    
    for pattern in lfs_patterns:
        try:
            subprocess.run(['git', 'lfs', 'track', pattern], check=True)
            print(f"Added pattern to Git LFS: {pattern}")
        except subprocess.CalledProcessError as e:
            print(f"Failed to add pattern {pattern}: {e}")
    
    # Create .gitattributes file
    gitattributes_content = """
# Large files handled by Git LFS
*.index filter=lfs diff=lfs merge=lfs -text
*.backup filter=lfs diff=lfs merge=lfs -text
*.large filter=lfs diff=lfs merge=lfs -text
data/*.large filter=lfs diff=lfs merge=lfs -text

# Ensure large files are tracked by LFS
legal_precedents.index.backup filter=lfs diff=lfs merge=lfs -text
legal_precedents_compact.index filter=lfs diff=lfs merge=lfs -text
"""
    
    with open('.gitattributes', 'w') as f:
        f.write(gitattributes_content)
    
    print("Created .gitattributes file for Git LFS")
    
    return True

def create_split_index():
    """Create split index files to stay under 100MB limit"""
    print("Creating split index files...")
    
    import pandas as pd
    from sentence_transformers import SentenceTransformer
    import faiss
    import numpy as np
    import gc
    
    # Load data
    df = pd.read_csv("legal_cases.csv")
    summaries = df['summary'].tolist()
    
    # Calculate split size (aim for ~80MB per file)
    total_docs = len(summaries)
    docs_per_file = 50000  # Approximate based on previous results
    
    num_files = (total_docs + docs_per_file - 1) // docs_per_file
    
    print(f"Splitting {total_docs:,} documents into {num_files} files")
    
    # Load model
    model = SentenceTransformer('all-MiniLM-L6-v2')
    dimension = model.encode([summaries[0]]).shape[1]
    
    # Create split indices
    for i in range(num_files):
        start_idx = i * docs_per_file
        end_idx = min((i + 1) * docs_per_file, total_docs)
        
        file_summaries = summaries[start_idx:end_idx]
        print(f"\nCreating part {i+1}/{num_files}: {len(file_summaries):,} documents")
        
        # Create index
        nlist = min(500, len(file_summaries) // 10)
        index = faiss.IndexIVFPQ(
            faiss.IndexFlatIP(dimension), dimension, nlist, 4, 4
        )
        
        # Train and add
        sample_size = min(2000, len(file_summaries))
        sample_embeddings = model.encode(file_summaries[:sample_size], batch_size=256)
        faiss.normalize_L2(sample_embeddings)
        index.train(sample_embeddings)
        index.nprobe = min(5, nlist)
        
        # Add vectors
        batch_size = 100
        for j in range(0, len(file_summaries), batch_size):
            batch = file_summaries[j:j + batch_size]
            batch_embeddings = model.encode(batch, batch_size=64)
            faiss.normalize_L2(batch_embeddings)
            batch_embeddings = batch_embeddings.astype(np.uint8)
            index.add(batch_embeddings)
            
            del batch_embeddings
            gc.collect()
        
        # Save part
        part_file = f"legal_precedents_part_{i+1:03d}.index"
        faiss.write_index(index, part_file)
        
        file_size = os.path.getsize(part_file) / (1024 * 1024)
        print(f"Part {i+1} saved: {file_size:.2f} MB")
        
        # Save corresponding metadata
        part_metadata = df.iloc[start_idx:end_idx]
        part_metadata.to_csv(f"metadata_part_{i+1:03d}.csv", index=False)
        
        del index
        gc.collect()
    
    print(f"\nCreated {num_files} split index files")
    return num_files

def create_lightweight_index():
    """Create a lightweight index with essential documents only"""
    print("Creating lightweight index with essential documents...")
    
    import pandas as pd
    from sentence_transformers import SentenceTransformer
    import faiss
    import numpy as np
    import gc
    
    # Load data and filter
    df = pd.read_csv("legal_cases.csv")
    
    # Filter for recent/important cases (example criteria)
    # You can adjust this based on your specific needs
    df_filtered = df.head(10000)  # Take first 10k as example
    # Or filter by date/court/importance:
    # df_filtered = df[df['year'] >= 2020]  # Recent cases only
    # df_filtered = df[df['court'].isin(['Supreme Court', 'Court of Appeal'])]  # Important courts
    
    summaries = df_filtered['summary'].tolist()
    print(f"Filtered to {len(summaries):,} essential documents")
    
    # Create compact index
    model = SentenceTransformer('all-MiniLM-L6-v2')
    dimension = model.encode([summaries[0]]).shape[1]
    
    # Use aggressive compression
    nlist = min(300, len(summaries) // 15)
    index = faiss.IndexIVFPQ(
        faiss.IndexFlatIP(dimension), dimension, nlist, 4, 4
    )
    
    # Train
    sample_embeddings = model.encode(summaries[:min(1000, len(summaries))], batch_size=256)
    faiss.normalize_L2(sample_embeddings)
    index.train(sample_embeddings)
    index.nprobe = min(5, nlist)
    
    # Add vectors
    batch_size = 200
    for i in range(0, len(summaries), batch_size):
        batch = summaries[i:i + batch_size]
        batch_embeddings = model.encode(batch, batch_size=64)
        faiss.normalize_L2(batch_embeddings)
        batch_embeddings = batch_embeddings.astype(np.uint8)
        index.add(batch_embeddings)
        
        del batch_embeddings
        gc.collect()
    
    # Save lightweight index
    faiss.write_index(index, "legal_precedents_lightweight.index")
    
    # Save filtered metadata
    df_filtered[['case_id', 'title']].to_csv("metadata_lightweight.csv", index=False)
    
    file_size = os.path.getsize("legal_precedents_lightweight.index") / (1024 * 1024)
    print(f"Lightweight index created: {file_size:.2f} MB")
    
    return file_size < 100

def create_download_instructions():
    """Create instructions for downloading large files"""
    instructions = """
# Large File Download Instructions

## Option 1: Git LFS (Recommended)
```bash
# Install Git LFS
git lfs install

# Clone repository with LFS
git clone <repository-url>
cd <repository>

# Pull large files
git lfs pull
```

## Option 2: Split Files Download
The index has been split into multiple parts:
- legal_precedents_part_001.index
- legal_precedents_part_002.index
- etc.

Download all parts and use the combined_search.py to search across all parts.

## Option 3: Lightweight Version
Use the lightweight index (legal_precedents_lightweight.index) for quick prototyping.

## Option 4: Direct Download
Large files can be downloaded from:
- Google Drive: [link]
- AWS S3: [bucket/path]
- Direct URL: [url]
"""
    
    with open('DOWNLOAD_INSTRUCTIONS.md', 'w') as f:
        f.write(instructions)
    
    print("Created DOWNLOAD_INSTRUCTIONS.md")

def cleanup_large_files():
    """Clean up large files that are too big for GitHub"""
    large_files = [
        "legal_precedents.index.backup",
        "legal_precedents_compact.index"
    ]
    
    for file in large_files:
        if os.path.exists(file):
            size_mb = os.path.getsize(file) / (1024 * 1024)
            print(f"Found large file: {file} ({size_mb:.2f} MB)")
            
            # Move to large_files directory
            os.makedirs("large_files", exist_ok=True)
            backup_path = f"large_files/{file}"
            shutil.move(file, backup_path)
            print(f"Moved to: {backup_path}")
    
    # Create .gitignore entry
    with open('.gitignore', 'a') as f:
        f.write("\n# Large files\n")
        f.write("*.backup\n")
        f.write("large_files/\n")
        f.write("legal_precedents.index.backup\n")
        f.write("legal_precedents_compact.index\n")
    
    print("Updated .gitignore")

def main():
    """Main function to handle large files for GitHub"""
    print("=" * 60)
    print("LARGE FILE HANDLING FOR GITHUB")
    print("=" * 60)
    
    # Step 1: Setup Git LFS
    print("\n1. Setting up Git LFS...")
    if setup_git_lfs():
        print("✅ Git LFS setup complete")
    else:
        print("❌ Git LFS setup failed")
    
    # Step 2: Create split index
    print("\n2. Creating split index files...")
    num_parts = create_split_index()
    
    # Step 3: Create lightweight index
    print("\n3. Creating lightweight index...")
    if create_lightweight_index():
        print("✅ Lightweight index created successfully")
    else:
        print("❌ Lightweight index still too large")
    
    # Step 4: Clean up large files
    print("\n4. Cleaning up large files...")
    cleanup_large_files()
    
    # Step 5: Create download instructions
    print("\n5. Creating download instructions...")
    create_download_instructions()
    
    print("\n" + "=" * 60)
    print("LARGE FILE HANDLING COMPLETE")
    print("=" * 60)
    print(f"Created {num_parts} split index files")
    print("Files are ready for GitHub push")
    print("See DOWNLOAD_INSTRUCTIONS.md for details")

if __name__ == "__main__":
    main()
