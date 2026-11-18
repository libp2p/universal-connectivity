"""
RAG (Retrieval-Augmented Generation) handler for the py-libp2p assistant.

Exposes:
  POST /api/v1/ask   — accepts {"question": "..."}, returns {"answer": "...", "sources": [...]}

The vector store (ChromaDB) is loaded lazily on the first request via
get_vectorstore(), never during peer startup. Queries are answered by:
embed question → ChromaDB similarity search → build grounded prompt → send to
Groq (llama-3.3-70b-versatile).
"""

import asyncio
import json
import logging
import os
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

import tornado.ioloop
import tornado.web

if TYPE_CHECKING:
    from groq import AsyncGroq
    from groq.types.chat import ChatCompletionUserMessageParam

log = logging.getLogger("rag_handler")

RAG_INSTALL_HINT = (
    "Groq SDK not installed. Install the RAG extra with "
    "`uv pip install -e '.[rag]'` or `pip install -r requirements-rag.txt`."
)


class RagDependencyError(RuntimeError):
    """Raised when an optional RAG dependency is missing at runtime."""

# Resolve the index from the project root, not from this module's directory.
# ``core/rag_handler.py`` is one level below the repository root.
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
VECTOR_STORE_DIR = str(
    _PROJECT_ROOT / "llm" / "codes" / "libp2p_vectorstore"
)
GROQ_MODEL       = "llama-3.3-70b-versatile"
_groq_client     = None
TOP_K            = 4
MAX_QUESTION_LEN = 2000  # characters; prevents token-limit abuse and cost blowup


def _get_groq_client() -> "AsyncGroq":
    global _groq_client
    if _groq_client is None:
        try:
            from groq import AsyncGroq
        except ImportError as exc:
            raise RagDependencyError(RAG_INSTALL_HINT) from exc
        _groq_client = AsyncGroq()
    return _groq_client


def load_vectorstore() -> Any:
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


_vectorstore: Any = None
_vectorstore_loaded = False
_vectorstore_lock = threading.Lock()


def get_vectorstore() -> Any:
    """Load the vector store at most once, on first use.

    Importing Chroma/torch and downloading the embedding model can take
    seconds to minutes and must not happen while the peer is starting, so the
    API server resolves it lazily from the first ``/api/v1/ask`` request
    (off the IOLoop, via ``run_in_executor``).
    """
    global _vectorstore, _vectorstore_loaded
    with _vectorstore_lock:
        if not _vectorstore_loaded:
            _vectorstore = load_vectorstore()
            _vectorstore_loaded = True
    return _vectorstore


def _build_prompt(question: str, chunks: list[Any]) -> str:
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
    Response: standard ApiResponse envelope containing {"answer": "...", "sources": [...]}
    """

    vectorstore: Any

    def initialize(self, vectorstore: Any = None) -> None:
        self.vectorstore = vectorstore

    async def _resolve_vectorstore(self) -> Any:
        """Return the store, loading it off the IOLoop on first use."""
        if self.vectorstore is not None:
            return self.vectorstore
        loop = tornado.ioloop.IOLoop.current()
        self.vectorstore = await loop.run_in_executor(None, get_vectorstore)
        return self.vectorstore

    def set_default_headers(self) -> None:
        self.set_header("Access-Control-Allow-Origin", "*")
        self.set_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.set_header("Access-Control-Allow-Headers", "Content-Type")
        self.set_header("Content-Type", "application/json")

    async def options(self) -> None:
        self.set_status(204)
        self.finish()

    def send_success(self, data: Any = None, status: int = 200) -> None:
        self.set_status(status)
        self.finish(json.dumps({
            "success": True,
            "data": data,
            "error": None,
            "timestamp": time.time(),
        }))

    def send_error_response(
        self,
        message: str,
        status: int = 400,
        detail: str | None = None,
    ) -> None:
        self.set_status(status)
        self.finish(json.dumps({
            "success": False,
            "data": None,
            "error": {
                "code": status,
                "message": message,
                "detail": detail,
            },
            "timestamp": time.time(),
        }))

    async def post(self) -> None:
        store = await self._resolve_vectorstore()
        if store is None:
            self.send_error_response(
                "RAG assistant is not available. Vector store not loaded.",
                status=503,
            )
            return

        try:
            body = json.loads(self.request.body)
            question = body.get("question", "").strip()
        except (json.JSONDecodeError, AttributeError):
            self.send_error_response(
                "Request body must be JSON with a 'question' field.",
                status=400,
            )
            return

        if not question:
            self.send_error_response("'question' cannot be empty.", status=400)
            return

        if len(question) > MAX_QUESTION_LEN:
            self.send_error_response(
                f"'question' must be at most {MAX_QUESTION_LEN} characters.",
                status=400,
            )
            return

        # Retrieve relevant chunks from ChromaDB
        try:
            chunks = await asyncio.to_thread(lambda: store.similarity_search(question, k=TOP_K))
        except Exception as exc:
            log.error("ChromaDB similarity search failed: %s", exc)
            self.send_error_response("Vector search failed.", status=500)
            return

        if not chunks:
            self.send_success({
                "answer": "No relevant context found in the knowledge base.",
                "sources": [],
            })
            return

        prompt = _build_prompt(question, chunks)

        # Call Groq (llama-3.3-70b-versatile)
        try:
            messages: list[ChatCompletionUserMessageParam] = [
                {"role": "user", "content": prompt}
            ]
            completion = await _get_groq_client().chat.completions.create(
                model=GROQ_MODEL,
                messages=messages,
            )
            content = completion.choices[0].message.content
            answer = content.strip() if content else ""
        except RagDependencyError as exc:
            log.error("%s", exc)
            self.send_error_response(str(exc), status=503)
            return
        except Exception as exc:
            log.error("Groq error: %s", exc)
            self.send_error_response(
                "LLM request failed. Please try again later.", status=502
            )
            return

        sources = sorted({c.metadata.get("source", "unknown") for c in chunks})
        self.send_success({
            "answer": answer,
            "sources": sources,
        })
