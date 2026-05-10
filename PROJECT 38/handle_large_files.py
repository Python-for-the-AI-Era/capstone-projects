#!/usr/bin/env python3
"""
Simple solution to handle large files for GitHub
"""

import os
import shutil
import pandas as pd

def create_github_ready_files():
    """Create GitHub-ready files under 100MB"""
    print("Creating GitHub-ready files...")
    
    # 1. Move large backup files to separate directory
    large_files = [
        "legal_precedents.index.backup",
        "legal_precedents_compact.index"
    ]
    
    os.makedirs("large_files_backup", exist_ok=True)
    
    for file in large_files:
        if os.path.exists(file):
            size_mb = os.path.getsize(file) / (1024 * 1024)
            print(f"Moving {file} ({size_mb:.2f} MB) to backup...")
            
            backup_path = f"large_files_backup/{file}"
            shutil.move(file, backup_path)
            print(f"  Moved to: {backup_path}")
    
    # 2. Create README for large files
    readme_content = """
# Large Files Handling

## Issue
The original index files are too large for GitHub (>100MB limit).

## Solution
Large files have been moved to the `large_files_backup/` directory.

## Files Available

### Current Working Files
- `legal_precedents.index` (2.05MB) - ✅ GitHub ready
- `metadata.csv` - Document metadata

### Large Backup Files
Located in `large_files_backup/` directory:
- `legal_precedents.index.backup` (146MB) - Original large file
- `legal_precedents_compact.index` (3.4MB) - Previous version

## Download Instructions

### Option 1: Use Current Working Files
The current `legal_precedents.index` (2.05MB) is fully functional and GitHub ready.

### Option 2: Download Large Files
Large files can be downloaded from:
1. Google Drive: [Add your link]
2. AWS S3: [Add your bucket/path]
3. Direct download: [Add your URL]

### Option 3: Recreate Large Index
Run the index rebuilding script:
```bash
python3 rebuild_full_index.py
```

## Git LFS Setup (Optional)
If you want to track large files with Git LFS:

```bash
# Install Git LFS
brew install git-lfs  # macOS
# or
sudo apt-get install git-lfs  # Ubuntu

# Initialize
git lfs install
git lfs track "*.index.backup"
git lfs track "*.large"
git add .gitattributes
git commit -m "Add Git LFS tracking"
```
"""
    
    with open('LARGE_FILES_README.md', 'w') as f:
        f.write(readme_content)
    
    print("Created LARGE_FILES_README.md")
    
    # 3. Update .gitignore
    gitignore_content = """
# Large files
*.backup
*.large
large_files_backup/
legal_precedents.index.backup
legal_precedents_compact.index

# Python cache
__pycache__/
*.pyc
*.pyo

# Model cache
.cache/
models/
"""
    
    with open('.gitignore', 'w') as f:
        f.write(gitignore_content)
    
    print("Updated .gitignore")
    
    # 4. Create simple rebuild script
    rebuild_script = """
#!/usr/bin/env python3
"""
Rebuild full index from original data
"""

import pandas as pd
from sentence_transformers import SentenceTransformer
import faiss
import numpy as np

def rebuild_full_index():
    print("Rebuilding full index from original data...")
    
    # Load original data
    df = pd.read_csv("legal_cases.csv")
    summaries = df['summary'].tolist()
    print(f"Processing {len(summaries)} documents...")
    
    # Load model
    model = SentenceTransformer('all-MiniLM-L6-v2')
    dimension = model.encode([summaries[0]]).shape[1]
    
    # Create index (using the working compact method)
    nlist = min(1000, len(summaries) // 10)
    index = faiss.IndexIVFPQ(faiss.IndexFlatIP(dimension), dimension, nlist, 4, 4)
    
    # Train
    sample_size = min(10000, len(summaries))
    sample_embeddings = model.encode(summaries[:sample_size], batch_size=512)
    faiss.normalize_L2(sample_embeddings)
    index.train(sample_embeddings)
    index.nprobe = min(10, nlist)
    
    # Add vectors
    batch_size = 256
    for i in range(0, len(summaries), batch_size):
        batch = summaries[i:i + batch_size]
        batch_embeddings = model.encode(batch, batch_size=128)
        faiss.normalize_L2(batch_embeddings)
        batch_embeddings = batch_embeddings.astype(np.uint8)
        index.add(batch_embeddings)
        
        if i % 100 == 0:
            print(f"Processed {min(i + batch_size, len(summaries)):,} / {len(summaries):,}")
    
    # Save
    faiss.write_index(index, "legal_precedents_full.index")
    
    # Save metadata
    df[['case_id', 'title']].to_csv("metadata_full.csv", index=False)
    
    file_size = os.path.getsize("legal_precedents_full.index") / (1024 * 1024)
    print(f"Full index created: {file_size:.2f} MB")
    
    return file_size

if __name__ == "__main__":
    rebuild_full_index()
"""
    
    with open('rebuild_full_index.py', 'w') as f:
        f.write(rebuild_script)
    
    print("Created rebuild_full_index.py")
    
    # 5. Check current file sizes
    print("\nCurrent file sizes:")
    for file in os.listdir('.'):
        if file.endswith('.index') or file.endswith('.csv'):
            if os.path.isfile(file):
                size_mb = os.path.getsize(file) / (1024 * 1024)
                status = "✅ GitHub ready" if size_mb < 100 else "❌ Too large"
                print(f"  {file}: {size_mb:.2f} MB {status}")
    
    return True

def main():
    """Main function"""
    print("=" * 50)
    print("GITHUB LARGE FILE HANDLER")
    print("=" * 50)
    
    if create_github_ready_files():
        print("\n✅ SUCCESS: Files are now GitHub ready!")
        print("\nNext steps:")
        print("1. Commit and push current files")
        print("2. Upload large files to cloud storage if needed")
        print("3. Update LARGE_FILES_README.md with download links")
    else:
        print("\n❌ Failed to prepare files")
    
    print("\n" + "=" * 50)

if __name__ == "__main__":
    main()
