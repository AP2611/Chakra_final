"""RAG pipeline with embeddings + vector search, plus a lightweight TF-IDF fallback.

The heavy dependencies (sentence-transformers, chromadb) are imported lazily
inside __init__ so that a missing/segfaulting install never crashes import
time. When they are unavailable, VectorRAGRetriever transparently delegates to
SimpleTfidfRetriever so the system still runs and RAG remains demonstrable.
"""
import os
import re
from typing import List, Dict, Optional

import numpy as np


# =============================================================================
# Lightweight TF-IDF fallback (no external dependencies beyond numpy)
# =============================================================================

class SimpleTfidfRetriever:
    """Pure-numpy TF-IDF retriever used when vector deps are unavailable."""

    def __init__(self, documents_dir: str = None, collection_name: str = "chakra_documents"):
        self.documents_dir = documents_dir
        self.collection_name = collection_name
        self.docs: List[Dict[str, str]] = []  # [{"source":..., "chunk":...}]
        self._vocab = None
        self._idf = None
        self._matrix = None

    # --- chunking (shared logic) ---
    def _chunk_text(self, text: str, chunk_size: int = 500, chunk_overlap: int = 50) -> List[str]:
        if not text or not text.strip():
            return []
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        chunks = []
        current_chunk = []
        current_length = 0
        for para in paragraphs:
            para_length = len(para.split())
            if current_length + para_length > chunk_size and current_chunk:
                chunks.append(" ".join(current_chunk))
                if chunk_overlap > 0 and current_chunk:
                    overlap_words = current_chunk[-1].split()[-chunk_overlap:]
                    current_chunk = [" ".join(overlap_words)] if overlap_words else []
                    current_length = len(overlap_words)
                else:
                    current_chunk = []
                    current_length = 0
            if para_length > chunk_size:
                words = para.split()
                for i in range(0, len(words), chunk_size - chunk_overlap):
                    chunks.append(" ".join(words[i:i + chunk_size]))
            else:
                current_chunk.append(para)
                current_length += para_length
        if current_chunk:
            chunks.append(" ".join(current_chunk))
        return chunks if chunks else [text]

    def _invalidate(self):
        self._vocab = None
        self._idf = None
        self._matrix = None

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        return re.findall(r"[a-z0-9]+", text.lower())

    def _build(self):
        if self._matrix is not None:
            return
        doc_tokens = [self._tokenize(d["chunk"]) for d in self.docs]
        vocab = {}
        for tokens in doc_tokens:
            for t in set(tokens):
                vocab[t] = vocab.get(t, 0) + 1
        self._vocab = {t: i for i, t in enumerate(sorted(vocab.keys()))}
        n = len(self.docs)
        V = len(self._vocab)
        tf = np.zeros((n, V))
        for i, tokens in enumerate(doc_tokens):
            if not tokens:
                continue
            counts = {}
            for t in tokens:
                counts[t] = counts.get(t, 0) + 1
            for t, c in counts.items():
                if t in self._vocab:
                    tf[i, self._vocab[t]] = c / len(tokens)
        df = np.zeros(V)
        for tokens in doc_tokens:
            for t in set(tokens):
                if t in self._vocab:
                    df[self._vocab[t]] += 1
        self._idf = np.log((n + 1) / (df + 1)) + 1
        self._matrix = tf * self._idf

    def add_document(self, content: str, source: str, metadata: Optional[Dict] = None) -> bool:
        chunks = self._chunk_text(content)
        if not chunks:
            return False
        for c in chunks:
            self.docs.append({"source": source, "chunk": c})
        self._invalidate()
        return True

    def retrieve(self, query: str, top_k: int = 3) -> List[str]:
        if not self.docs:
            return []
        self._build()
        q = np.zeros(len(self._vocab))
        for t in self._tokenize(query):
            if t in self._vocab:
                q[self._vocab[t]] += 1
        if q.sum() > 0:
            q = q / q.sum()
        q_vec = q * self._idf
        q_norm = np.linalg.norm(q_vec)
        if q_norm == 0:
            return []
        m_norm = np.linalg.norm(self._matrix, axis=1)
        sims = np.dot(self._matrix, q_vec) / (m_norm * q_norm + 1e-9)
        top_idx = np.argsort(-sims)[:top_k]
        return [self.docs[i]["chunk"] for i in top_idx if sims[i] > 0]

    def delete_document(self, source: str) -> bool:
        before = len(self.docs)
        self.docs = [d for d in self.docs if d["source"] != source]
        if len(self.docs) != before:
            self._invalidate()
            return True
        return False

    def list_documents(self) -> List[str]:
        return sorted({d["source"] for d in self.docs})

    def get_document_count(self) -> int:
        return len(self.docs)


# =============================================================================
# Real vector RAG retriever (delegates to TF-IDF fallback if deps missing)
# =============================================================================

class VectorRAGRetriever:
    """Real RAG retriever with semantic search using embeddings.

    Imports sentence-transformers / chromadb lazily. If they fail to load,
    falls back to :class:`SimpleTfidfRetriever` so the API never crashes.
    """

    def __init__(self, documents_dir: str = None, collection_name: str = "chakra_documents"):
        if documents_dir is None:
            backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            project_root = os.path.dirname(backend_dir)
            documents_dir = os.path.join(project_root, "backend", "data", "documents")
        self.documents_dir = documents_dir
        os.makedirs(self.documents_dir, exist_ok=True)

        self.collection_name = collection_name
        self._fallback: Optional[SimpleTfidfRetriever] = None
        self.embedding_model = None
        self.client = None
        self.collection = None

        # Lazy, guarded import of heavy dependencies
        try:
            from sentence_transformers import SentenceTransformer
            import chromadb
            from chromadb.config import Settings

            print("Loading embedding model...")
            self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
            print("✓ Embedding model loaded (all-MiniLM-L6-v2)")

            chroma_dir = os.path.join(self.documents_dir, "chroma_db")
            os.makedirs(chroma_dir, exist_ok=True)
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
        except Exception as e:
            print(f"⚠ Vector RAG unavailable ({type(e).__name__}: {e})")
            print("⚠ Falling back to TF-IDF retriever (no external deps)")
            self._fallback = SimpleTfidfRetriever(documents_dir, collection_name)

        # Index any documents already present in the documents directory
        self._load_documents_from_dir()

    def _load_documents_from_dir(self):
        """Index .txt/.md files from the documents directory into the store."""
        if not self.documents_dir or not os.path.isdir(self.documents_dir):
            return
        try:
            existing = set(self.list_documents())
        except Exception:
            existing = set()
        for fname in sorted(os.listdir(self.documents_dir)):
            if not fname.lower().endswith((".txt", ".md")):
                continue
            if fname in existing:
                continue  # already indexed
            path = os.path.join(self.documents_dir, fname)
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                if content.strip():
                    self.add_document(content, fname)
            except Exception as e:
                print(f"⚠ Could not index {fname}: {e}")

    # --- shared chunking ---
    def _chunk_text(self, text: str, chunk_size: int = 500, chunk_overlap: int = 50) -> List[str]:
        return SimpleTfidfRetriever._chunk_text(self, text, chunk_size, chunk_overlap)

    def add_document(self, content: str, source: str, metadata: Optional[Dict] = None) -> bool:
        if self._fallback is not None:
            return self._fallback.add_document(content, source, metadata)
        if not self.collection or not self.embedding_model:
            print("⚠ Vector database not available, skipping document addition")
            return False
        try:
            chunks = self._chunk_text(content)
            if not chunks:
                return False
            embeddings = self.embedding_model.encode(chunks, show_progress_bar=False)
            ids = [f"{source}_{i}" for i in range(len(chunks))]
            metadatas = [{
                "source": source,
                "chunk_index": str(i),
                **(metadata or {})
            } for i in range(len(chunks))]
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
        if self._fallback is not None:
            return self._fallback.retrieve(query, top_k)
        if not self.collection or not self.embedding_model:
            return []
        try:
            query_embedding = self.embedding_model.encode([query], show_progress_bar=False)[0]
            results = self.collection.query(
                query_embeddings=[query_embedding.tolist()],
                n_results=top_k
            )
            if results['documents'] and len(results['documents']) > 0:
                chunks = results['documents'][0]
                return chunks if chunks else []
            return []
        except Exception as e:
            print(f"⚠ Error retrieving documents: {e}")
            return []

    def delete_document(self, source: str) -> bool:
        if self._fallback is not None:
            return self._fallback.delete_document(source)
        if not self.collection:
            return False
        try:
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
        if self._fallback is not None:
            return self._fallback.list_documents()
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
        if self._fallback is not None:
            return self._fallback.get_document_count()
        if not self.collection:
            return 0
        try:
            return self.collection.count()
        except Exception:
            return 0
