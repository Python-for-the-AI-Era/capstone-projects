#!/usr/bin/env python3
"""
Document Similarity Search Engine for Lawpath Nigeria
Main script to run the complete pipeline
"""

import os
import sys
from indexer import build_index
from search_api import app
import uvicorn
import argparse

def main():
    parser = argparse.ArgumentParser(description="Document Similarity Search Engine")
    parser.add_argument("--generate-data", action="store_true", help="Generate sample legal case data")
    parser.add_argument("--build-index", action="store_true", help="Build FAISS index from data")
    parser.add_argument("--serve", action="store_true", help="Start FastAPI server")
    parser.add_argument("--host", default="127.0.0.1", help="Host for API server")
    parser.add_argument("--port", type=int, default=8000, help="Port for API server")
    
    args = parser.parse_args()
    
    if args.generate_data:
        print("Generating sample data...")
        from data_generator import generate_sample_data
        generate_sample_data(100000)
        
    if args.build_index:
        if not os.path.exists("legal_cases.csv"):
            print("Error: legal_cases.csv not found. Run --generate-data first.")
            sys.exit(1)
        print("Building FAISS index...")
        build_index("legal_cases.csv")
        
    if args.serve:
        if not os.path.exists("legal_precedents.index"):
            print("Error: legal_precedents.index not found. Run --build-index first.")
            sys.exit(1)
        if not os.path.exists("metadata.csv"):
            print("Error: metadata.csv not found. Run --generate-data first.")
            sys.exit(1)
        print(f"Starting API server on {args.host}:{args.port}")
        uvicorn.run(app, host=args.host, port=args.port)
        
    if not any([args.generate_data, args.build_index, args.serve]):
        print("Usage examples:")
        print("  python main.py --generate-data    # Generate 100k sample cases")
        print("  python main.py --build-index      # Build FAISS index")
        print("  python main.py --serve            # Start API server")
        print("  python main.py --generate-data --build-index --serve  # Full pipeline")

if __name__ == "__main__":
    main()
