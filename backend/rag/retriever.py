"""RAG (Retrieval-Augmented Generation) system for document retrieval."""
import os
from typing import List, Dict, Optional
from pathlib import Path
import json


class SimpleRAGRetriever:
    """Simple RAG retriever for document chunks."""
    
    def __init__(self, documents_dir: str = None):
        # Use path relative to this file's location for portability
        if documents_dir is None:
            # Get the backend directory (parent of rag/)
            backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            # Get the project root (parent of backend/)
            project_root = os.path.dirname(backend_dir)
            # Use data/documents directory in project root
            documents_dir = os.path.join(project_root, "backend", "data", "documents")
        self.documents_dir = documents_dir
        self.chunks: List[Dict[str, str]] = []
        self._load_documents()
    
    def _load_documents(self):
        """Load and chunk documents."""
        os.makedirs(self.documents_dir, exist_ok=True)
        
        # Load from JSON index if it exists
        index_path = os.path.join(self.documents_dir, "index.json")
        if os.path.exists(index_path):
            with open(index_path, "r", encoding="utf-8") as f:
                self.chunks = json.load(f)
        else:
            # Scan for text files
            for file_path in Path(self.documents_dir).glob("*.txt"):
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    # Simple chunking by paragraphs
                    paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
                    for i, para in enumerate(paragraphs):
                        self.chunks.append({
                            "text": para,
                            "source": file_path.name,
                            "chunk_id": f"{file_path.stem}_{i}"
                        })
    
    def retrieve(self, query: str, top_k: int = 3) -> List[str]:
        """Retrieve top-k relevant chunks for a query."""
        if not self.chunks:
            return []
        
        query_lower = query.lower()
        query_words = set(query_lower.split())
        
        # Simple keyword-based scoring
        scored_chunks = []
        for chunk in self.chunks:
            chunk_text = chunk["text"].lower()
            chunk_words = set(chunk_text.split())
            
            # Jaccard similarity
            intersection = len(query_words & chunk_words)
            union = len(query_words | chunk_words)
            score = intersection / union if union > 0 else 0
            
            scored_chunks.append((score, chunk["text"]))
        
        # Sort by score and return top-k
        scored_chunks.sort(key=lambda x: x[0], reverse=True)
        return [chunk_text for score, chunk_text in scored_chunks[:top_k] if score > 0]
    
    def add_document(self, content: str, source: str):
        """Add a new document to the index."""
        paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
        for i, para in enumerate(paragraphs):
            self.chunks.append({
                "text": para,
                "source": source,
                "chunk_id": f"{source}_{i}"
            })
        
        # Save to index
        self._save_index()
    
    def _save_index(self):
        """Save chunks to index file."""
        index_path = os.path.join(self.documents_dir, "index.json")
        with open(index_path, "w", encoding="utf-8") as f:
            json.dump(self.chunks, f, indent=2)

