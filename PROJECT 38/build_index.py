#!/usr/bin/env python3
"""
Script to build FAISS index from legal cases data
"""

from indexer import build_index

if __name__ == "__main__":
    print("Building FAISS index from legal_cases.csv...")
    build_index("legal_cases.csv")
