import os
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
from dotenv import load_dotenv

load_dotenv()

DATA_PATH = "docs"
CHROMA_PATH = "data_store"

def load_documents():
    # Start with simple text files (markdown) that don't require complex processing
    all_documents = []
    
    try:
        # Load markdown files using TextLoader (simpler, more reliable)
        loader = DirectoryLoader(
            DATA_PATH,
            glob="*.md",
            show_progress=True,
            loader_cls=TextLoader
        )
        documents = loader.load()
        all_documents.extend(documents)
        print(f"Loaded {len(documents)} markdown documents")
    except Exception as e:
        print(f"Warning: Could not load markdown files: {e}")
    
    # Try to load other file types if available
    for ext in ["*.txt"]:
        try:
            loader = DirectoryLoader(
                DATA_PATH,
                glob=ext,
                show_progress=True,
                loader_cls=TextLoader
            )
            documents = loader.load()
            all_documents.extend(documents)
            print(f"Loaded {len(documents)} documents with extension {ext}")
        except Exception as e:
            print(f"Warning: Could not load files with extension {ext}: {e}")
            continue
    
    return all_documents

def split_documents(documents):
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=100
    )
    return splitter.split_documents(documents)

def main():
    documents = load_documents()
    
    if not documents:
        print("No documents were loaded. Please check that there are supported files in the docs directory.")
        return
    
    chunks = split_documents(documents)
    print(f"Loaded {len(documents)} documents, split into {len(chunks)} chunks.")

    if not chunks:
        print("No text chunks were created from the documents.")
        return

    # Try OpenAI embeddings first, fall back to local embeddings if API key has insufficient permissions
    try:
        embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
        print("Using OpenAI embeddings...")
    except Exception as e:
        print(f"OpenAI embeddings failed: {e}")
        print("Falling back to local HuggingFace embeddings...")
        embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    db = Chroma.from_documents(chunks, embeddings, persist_directory=CHROMA_PATH)
    print("Documents embedded and saved to ChromaDB.")

if __name__ == "__main__":
    main()