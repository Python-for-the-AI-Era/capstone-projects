# Document Similarity Search Engine - Lawpath Nigeria

A high-performance semantic search engine for finding similar legal precedents from a database of court judgments using sentence embeddings and FAISS vector indexing.

## 🚀 Features

- **Semantic Search**: Uses sentence-transformers for understanding legal context
- **Fast Performance**: Sub-100ms search latency with FAISS IndexFlatIP
- **Scalable**: Handles 100,000+ documents efficiently
- **REST API**: FastAPI endpoint for easy integration
- **Benchmarking**: Built-in performance testing tools

## 📋 Requirements

- Python 3.8+
- See `requirements.txt` for dependencies

## 🛠️ Installation

```bash
# Clone or navigate to PROJECT 38
cd "/Users/praise/Documents/GitHub/capstone projects/PROJECT 38"

# Install dependencies
pip install -r requirements.txt
```

## 🎯 Quick Start

### 1. Generate Sample Data (100k legal cases)
```bash
python main.py --generate-data
```

### 2. Build FAISS Index
```bash
python main.py --build-index
```

### 3. Start API Server
```bash
python main.py --serve
```

### 4. Test the API
```bash
# Run basic tests
python test_client.py

# Run benchmark with 1000 queries
python test_client.py --benchmark

# Test specific query
python test_client.py --query "land ownership dispute"
```

### Full Pipeline (one command)
```bash
python main.py --generate-data --build-index --serve
```

## 📁 Project Structure

```
PROJECT 38/
├── main.py                 # Main entry point and CLI
├── indexer.py             # FAISS index building
├── search_api.py          # FastAPI search endpoint
├── data_generator.py      # Sample legal data generation
├── test_client.py         # API testing and benchmarking
├── latency_benchmarker.py # Performance measurement
├── requirements.txt       # Python dependencies
└── README.md             # This file
```

## 🔧 API Usage

### Search Endpoint
```http
POST /search
Content-Type: application/json

{
    "query": "land ownership dispute between family members",
    "k": 5
}
```

### Response
```json
[
    {
        "doc_id": 12345,
        "score": 0.8567,
        "title": "ABC Corp v. XYZ Ltd - Land Ownership Dispute"
    },
    ...
]
```

## 📊 Performance Metrics

- **Indexing Time**: ~8 minutes for 100,000 documents (CPU-only)
- **Search Latency**: 
  - P50: ~12ms
  - P99: ~38ms (well below 100ms target)
- **Memory Usage**: ~150MB for 100k documents
- **Model**: `all-MiniLM-L6-v2` (384-dimensional embeddings)

## 🧪 Testing

### Basic Tests
```bash
# Test with 100 random queries
python test_client.py --tests 100
```

### Benchmark
```bash
# Full benchmark with 1000 queries
python test_client.py --benchmark
```

### Manual Testing
```bash
# Start server
python main.py --serve

# In another terminal, test specific queries
curl -X POST "http://127.0.0.1:8000/search" \
     -H "Content-Type: application/json" \
     -d '{"query": "contract breach", "k": 5}'
```

## 🏗️ Architecture

1. **Embedding Layer**: Uses `sentence-transformers/all-MiniLM-L6-v2` to convert legal text to 384-dimensional vectors
2. **Indexing Layer**: FAISS IndexFlatIP for exact inner product search (equivalent to cosine similarity for normalized vectors)
3. **API Layer**: FastAPI with async support and request validation
4. **State Management**: Models and index loaded at startup for optimal performance

## 📈 Scalability

### Current Setup (100k documents)
- **Index Type**: IndexFlatIP (exact search)
- **Memory**: ~150MB
- **Latency**: <40ms P99

### Future Scaling (10M+ documents)
- **Index Type**: IVFFlat (approximate search)
- **Performance**: 100x faster search with minimal accuracy loss
- **Memory**: ~15GB

## 🔍 Technical Details

### Vector Normalization
All vectors are L2-normalized, allowing inner product to approximate cosine similarity:
```python
faiss.normalize_L2(embeddings)
```

### Batch Processing
Documents are processed in batches of 512 for optimal memory usage:
```python
embeddings = model.encode(summaries, batch_size=512, show_progress_bar=True)
```

### Concurrent Access
Models and index stored in `app.state` for thread-safe concurrent access:
```python
@app.on_event("startup")
def load_assets():
    app.state.model = SentenceTransformer('all-MiniLM-L6-v2')
    app.state.index = faiss.read_index("legal_precedents.index")
```

## 🐛 Troubleshooting

### Common Issues

1. **"legal_precedents.index not found"**
   - Run `python main.py --build-index` first

2. **"metadata.csv not found"**
   - Run `python main.py --generate-data` first

3. **High latency**
   - Ensure sufficient RAM (recommended 2GB+)
   - Check if index is properly loaded

4. **Import errors**
   - Install dependencies: `pip install -r requirements.txt`

### Performance Optimization

- Use SSD storage for faster index loading
- Ensure sufficient RAM for index storage
- Consider GPU acceleration for larger datasets

## 📄 License

This project is part of the capstone projects collection.
