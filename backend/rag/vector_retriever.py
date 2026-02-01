"""Real RAG pipeline with embeddings and vector search using ChromaDB."""
import os
from typing import List, Dict, Optional
from pathlib import Path
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
import json


class VectorRAGRetriever:
    """Real RAG retriever with semantic search using embeddings."""
    
    def __init__(self, documents_dir: str = None, collection_name: str = "chakra_documents"):
        # Get documents directory
        if documents_dir is None:
            backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            project_root = os.path.dirname(backend_dir)
            documents_dir = os.path.join(project_root, "backend", "data", "documents")
        self.documents_dir = documents_dir
        os.makedirs(self.documents_dir, exist_ok=True)
        
        # Initialize embedding model (using a lightweight model)
        print("Loading embedding model...")
        try:
            self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
            print("✓ Embedding model loaded (all-MiniLM-L6-v2)")
        except ImportError:
            print("⚠ sentence-transformers not installed. Install with: pip install sentence-transformers")
            self.embedding_model = None
        except Exception as e:
            print(f"⚠ Error loading embedding model: {e}")
            print("⚠ RAG will not work until dependencies are installed")
            self.embedding_model = None
        
        # Initialize ChromaDB
        chroma_dir = os.path.join(self.documents_dir, "chroma_db")
        os.makedirs(chroma_dir, exist_ok=True)
        
        try:
            self.client = chromadb.PersistentClient(
                path=chroma_dir,
                settings=Settings(anonymized_telemetry=False)
            )
            self.collection = self.client.get_or_create_collection(
                name=collection_name,
                metadata={"hnsw:space": "cosine"}
            )
            doc_count = len(self.collection.get()['ids'])
            print(f"✓ ChromaDB initialized: {doc_count} document chunks")
        except ImportError:
            print("⚠ chromadb not installed. Install with: pip install chromadb")
            self.client = None
            self.collection = None
        except Exception as e:
            print(f"⚠ Error initializing ChromaDB: {e}")
            print("⚠ RAG will not work until dependencies are installed")
            self.client = None
            self.collection = None
    
    def _chunk_text(self, text: str, chunk_size: int = 500, chunk_overlap: int = 50) -> List[str]:
        """Split text into overlapping chunks."""
        if not text or not text.strip():
            return []
        
        # Split by paragraphs first
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        chunks = []
        current_chunk = []
        current_length = 0
        
        for para in paragraphs:
            para_length = len(para.split())
            
            # If adding this paragraph would exceed chunk size, save current chunk
            if current_length + para_length > chunk_size and current_chunk:
                chunks.append(" ".join(current_chunk))
                
                # Start new chunk with overlap (last part of previous chunk)
                if chunk_overlap > 0 and current_chunk:
                    overlap_words = current_chunk[-1].split()[-chunk_overlap:]
                    current_chunk = [" ".join(overlap_words)] if overlap_words else []
                    current_length = len(overlap_words)
                else:
                    current_chunk = []
                    current_length = 0
            
            # If single paragraph is too large, split it
            if para_length > chunk_size:
                words = para.split()
                for i in range(0, len(words), chunk_size - chunk_overlap):
                    chunk_words = words[i:i + chunk_size]
                    chunks.append(" ".join(chunk_words))
            else:
                current_chunk.append(para)
                current_length += para_length
        
        # Add remaining chunk
        if current_chunk:
            chunks.append(" ".join(current_chunk))
        
        return chunks if chunks else [text]
    
    def add_document(self, content: str, source: str, metadata: Optional[Dict] = None):
        """Add a document to the vector database."""
        if not self.collection or not self.embedding_model:
            print("⚠ Vector database not available, skipping document addition")
            return False
        
        try:
            # Chunk the document
            chunks = self._chunk_text(content)
            
            if not chunks:
                return False
            
            # Generate embeddings
            embeddings = self.embedding_model.encode(chunks, show_progress_bar=False)
            
            # Prepare data for ChromaDB
            ids = [f"{source}_{i}" for i in range(len(chunks))]
            metadatas = [{
                "source": source,
                "chunk_index": str(i),
                **(metadata or {})
            } for i in range(len(chunks))]
            
            # Add to collection
            self.collection.add(
                ids=ids,
                embeddings=embeddings.tolist(),
                documents=chunks,
                metadatas=metadatas
            )
            
            print(f"✓ Added document '{source}' with {len(chunks)} chunks")
            return True
        except Exception as e:
            print(f"⚠ Error adding document '{source}': {e}")
            return False
    
    def retrieve(self, query: str, top_k: int = 3) -> List[str]:
        """Retrieve top-k relevant chunks using semantic search."""
        if not self.collection or not self.embedding_model:
            # Fallback to empty list if vector DB not available
            return []
        
        try:
            # Generate query embedding
            query_embedding = self.embedding_model.encode([query], show_progress_bar=False)[0]
            
            # Search in ChromaDB
            results = self.collection.query(
                query_embeddings=[query_embedding.tolist()],
                n_results=top_k
            )
            
            # Extract document texts
            if results['documents'] and len(results['documents']) > 0:
                chunks = results['documents'][0]
                return chunks if chunks else []
            else:
                return []
        except Exception as e:
            print(f"⚠ Error retrieving documents: {e}")
            return []
    
    def delete_document(self, source: str) -> bool:
        """Delete all chunks of a document."""
        if not self.collection:
            return False
        
        try:
            # Get all IDs for this source
            results = self.collection.get(where={"source": source})
            if results['ids']:
                self.collection.delete(ids=results['ids'])
                print(f"✓ Deleted document '{source}'")
                return True
            return False
        except Exception as e:
            print(f"⚠ Error deleting document '{source}': {e}")
            return False
    
    def list_documents(self) -> List[str]:
        """List all unique document sources."""
        if not self.collection:
            return []
        
        try:
            results = self.collection.get()
            sources = set()
            for metadata in results.get('metadatas', []):
                if metadata and 'source' in metadata:
                    sources.add(metadata['source'])
            return sorted(list(sources))
        except Exception as e:
            print(f"⚠ Error listing documents: {e}")
            return []
    
    def get_document_count(self) -> int:
        """Get total number of chunks in the database."""
        if not self.collection:
            return 0
        try:
            return self.collection.count()
        except:
            return 0

