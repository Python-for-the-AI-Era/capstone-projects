# Large Files Handling

## Issue
The original index files are too large for GitHub (>100MB limit).

## Solution
Large files have been moved to the `large_files_backup/` directory.

## Files Available

### Current Working Files
- `legal_precedents.index` (2.05MB) - GitHub ready
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
