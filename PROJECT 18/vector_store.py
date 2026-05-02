from langchain.vectorstores import Chroma
from langchain.embeddings import OpenAIEmbeddings

def index_contracts(texts: list, metadata: list):
    """
    TASK: Convert 50,000 contract strings into vectors.
    Store them in ChromaDB so we can search by meaning, not just keywords.
    """
    vector_db = Chroma.from_texts(
        texts=texts,
        embedding=OpenAIEmbeddings(),
        metadatas=metadata
    )
    return vector_db