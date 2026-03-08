# pip install chromadb langchain langchain-community langchain-huggingface sentence-transformers

from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_huggingface import HuggingFaceEmbeddings

# 1. Load py-libp2p source files
loader = DirectoryLoader(
    "../py-libp2p",
    glob="**/*.py",
    loader_cls=TextLoader
)
docs = loader.load()

# Load py-libp2p markdown docs
md_loader = DirectoryLoader(
    "../py-libp2p",
    glob="**/*.md",
    loader_cls=TextLoader
)
docs += md_loader.load()

# Load libp2p spec files (md + txt)
for glob_pattern in ("**/*.md", "**/*.txt"):
    spec_loader = DirectoryLoader(
        "../specs",           # ← cloned libp2p/specs repo
        glob=glob_pattern,
        loader_cls=TextLoader
    )
    docs += spec_loader.load()

# 2. Chunk them
splitter = RecursiveCharacterTextSplitter(
    chunk_size=300,       # reduced from 500
    chunk_overlap=30,     # reduced proportionally
    separators=["\nclass ", "\ndef ", "\n\n", "\n", " "]
)
chunks = splitter.split_documents(docs)
print(f"Total chunks: {len(chunks)}")

# 3. Embed + store in ChromaDB
embeddings = HuggingFaceEmbeddings(
    model_name="nomic-ai/nomic-embed-text-v1.5",
    model_kwargs={"trust_remote_code": True},
)
vectorstore = Chroma.from_documents(
    documents=chunks,
    embedding=embeddings,
    persist_directory="./libp2p_vectorstore"
)
print("Done! Vector store saved.")
