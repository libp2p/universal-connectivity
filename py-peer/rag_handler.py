"""
RAG (Retrieval-Augmented Generation) handler for the py-libp2p assistant.

Exposes:
  POST /api/v1/ask   — accepts {"question": "..."}, returns {"answer": "...", "sources": [...]}

The vector store (ChromaDB) is loaded once at startup via load_vectorstore().
Queries are answered by: embed question → ChromaDB similarity search → build grounded
prompt → send to Groq (llama-3.3-70b-versatile).
"""

import json
import logging
import os

import tornado.web
from groq import AsyncGroq

log = logging.getLogger("rag_handler")

# Absolute path derived from this file's location — works regardless of cwd
_HERE = os.path.dirname(os.path.abspath(__file__))
VECTOR_STORE_DIR = os.path.join(_HERE, "llm", "codes", "libp2p_vectorstore")
GROQ_MODEL       = "llama-3.3-70b-versatile"
_groq_client     = None
TOP_K            = 4


def _get_groq_client() -> AsyncGroq:
    global _groq_client
    if _groq_client is None:
        _groq_client = AsyncGroq()
    return _groq_client


def load_vectorstore():
    """
    Load ChromaDB vector store with nomic-embed-text embeddings.
    Returns None (with a warning) if the directory doesn't exist or
    the required packages aren't installed, so the rest of the app
    can still start normally.
    """
    if not os.path.isdir(VECTOR_STORE_DIR):
        log.warning(
            "RAG vector store not found at %s — /api/v1/ask will be unavailable. "
            "Run the indexer (llm/codes/build_vectorstore.py) first.",
            VECTOR_STORE_DIR,
        )
        return None

    try:
        from langchain_huggingface import HuggingFaceEmbeddings
        from langchain_chroma import Chroma

        embeddings = HuggingFaceEmbeddings(
            model_name="nomic-ai/nomic-embed-text-v1.5",
            model_kwargs={"trust_remote_code": True},
        )
        store = Chroma(
            persist_directory=VECTOR_STORE_DIR,
            embedding_function=embeddings,
        )
        log.info("✅ RAG vector store loaded from %s", VECTOR_STORE_DIR)
        return store
    except ImportError as exc:
        log.warning("RAG packages not installed (%s) — /api/v1/ask unavailable.", exc)
        return None
    except Exception as exc:
        log.warning("Failed to load RAG vector store: %s — /api/v1/ask unavailable.", exc)
        return None


def _build_prompt(question: str, chunks: list) -> str:
    context = "\n\n---\n\n".join(
        f"[Source: {c.metadata.get('source', 'unknown')}]\n{c.page_content}"
        for c in chunks
    )
    return (
        "You are an expert assistant for the py-libp2p library and libp2p protocols.\n"
        "Answer the question using ONLY the context below.\n"
        "If the answer is not in the context, say \"I don't have enough context to answer that.\"\n"
        "Always mention which file or spec the answer comes from.\n\n"
        f"{context}\n\n"
        "---\n"
        f"Question: {question}\n"
        "Answer:"
    )


class AskHandler(tornado.web.RequestHandler):
    """
    POST /api/v1/ask
    Body:     {"question": "how does DHT routing work?"}
    Response: {"answer": "...", "sources": ["file1.py", "spec.md"]}
    """

    def initialize(self, vectorstore):
        self.vectorstore = vectorstore

    def set_default_headers(self):
        self.set_header("Access-Control-Allow-Origin", "*")
        self.set_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.set_header("Access-Control-Allow-Headers", "Content-Type")
        self.set_header("Content-Type", "application/json")

    async def options(self):
        self.set_status(204)
        self.finish()

    async def post(self):
        if self.vectorstore is None:
            self.set_status(503)
            self.finish(json.dumps({
                "success": False,
                "error": "RAG assistant is not available. Vector store not loaded.",
            }))
            return

        try:
            body = json.loads(self.request.body)
            question = body.get("question", "").strip()
        except (json.JSONDecodeError, AttributeError):
            self.set_status(400)
            self.finish(json.dumps({
                "success": False,
                "error": "Request body must be JSON with a 'question' field.",
            }))
            return

        if not question:
            self.set_status(400)
            self.finish(json.dumps({
                "success": False,
                "error": "'question' cannot be empty.",
            }))
            return

        # Retrieve relevant chunks from ChromaDB
        try:
            chunks = self.vectorstore.similarity_search(question, k=TOP_K)
        except Exception as exc:
            log.error("ChromaDB similarity search failed: %s", exc)
            self.set_status(500)
            self.finish(json.dumps({"success": False, "error": "Vector search failed."}))
            return

        if not chunks:
            self.finish(json.dumps({
                "success": True,
                "answer": "No relevant context found in the knowledge base.",
                "sources": [],
            }))
            return

        prompt = _build_prompt(question, chunks)

        # Call Groq (llama-3.3-70b-versatile)
        try:
            completion = await _get_groq_client().chat.completions.create(
                model=GROQ_MODEL,
                messages=[{"role": "user", "content": prompt}],
            )
            answer = completion.choices[0].message.content.strip()
        except Exception as exc:
            log.error("Groq error: %s", exc)
            self.set_status(502)
            self.finish(json.dumps({
                "success": False,
                "error": f"LLM backend error: {exc}",
            }))
            return

        sources = sorted({c.metadata.get("source", "unknown") for c in chunks})
        self.finish(json.dumps({
            "success": True,
            "answer": answer,
            "sources": sources,
        }))
