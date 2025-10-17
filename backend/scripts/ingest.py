import os
import shutil
import tempfile
from pathlib import Path

from google.cloud import storage
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
from dotenv import load_dotenv

load_dotenv()

DATA_PATH = os.getenv("DOCUMENTS_PATH", "docs")
CHROMA_PATH = Path(os.getenv("VECTOR_STORE_PATH", "/tmp/data_store")).resolve()
VECTOR_STORE_GCS_URI = os.getenv("VECTOR_STORE_GCS_URI")
SUPPORTED_SUFFIXES = (".md", ".txt")


def _load_local_documents(path: str):
    all_documents = []

    try:
        loader = DirectoryLoader(
            path,
            glob="*.md",
            show_progress=True,
            loader_cls=TextLoader
        )
        documents = loader.load()
        all_documents.extend(documents)
        print(f"Loaded {len(documents)} markdown documents from {path}")
    except Exception as e:
        print(f"Warning: Could not load markdown files from {path}: {e}")

    for ext in ["*.txt"]:
        try:
            loader = DirectoryLoader(
                path,
                glob=ext,
                show_progress=True,
                loader_cls=TextLoader
            )
            documents = loader.load()
            all_documents.extend(documents)
            print(f"Loaded {len(documents)} documents with extension {ext} from {path}")
        except Exception as e:
            print(f"Warning: Could not load files with extension {ext} from {path}: {e}")
            continue

    return all_documents


def _download_gcs_docs(uri: str, destination: Path):
    if not uri.startswith("gs://"):
        raise ValueError(f"Expected GCS URI starting with gs://, received: {uri}")

    bucket_path = uri[5:]
    if "/" in bucket_path:
        bucket_name, prefix = bucket_path.split("/", 1)
    else:
        bucket_name, prefix = bucket_path, ""

    client = storage.Client()
    blobs = client.list_blobs(bucket_name, prefix=prefix)
    downloaded = 0

    for blob in blobs:
        if blob.name.endswith("/"):
            continue

        if not blob.name.lower().endswith(SUPPORTED_SUFFIXES):
            continue

        relative_name = blob.name[len(prefix):].lstrip("/") if prefix else blob.name
        local_path = destination / relative_name
        local_path.parent.mkdir(parents=True, exist_ok=True)
        blob.download_to_filename(local_path.as_posix())
        downloaded += 1

    print(f"Downloaded {downloaded} files from gs://{bucket_name}/{prefix}")


def _upload_directory_to_gcs(directory: Path, uri: str):
    if not uri:
        print("VECTOR_STORE_GCS_URI not set; skipping upload to Cloud Storage.")
        return

    if not uri.startswith("gs://"):
        raise ValueError(f"VECTOR_STORE_GCS_URI must start with gs://, received: {uri}")

    bucket_path = uri[5:]
    if "/" in bucket_path:
        bucket_name, prefix = bucket_path.split("/", 1)
    else:
        bucket_name, prefix = bucket_path, ""

    client = storage.Client()
    bucket = client.bucket(bucket_name)

    if not directory.exists():
        raise FileNotFoundError(f"Vector store directory does not exist: {directory}")

    existing_blobs = list(client.list_blobs(bucket_name, prefix=prefix))
    if existing_blobs:
        for blob in existing_blobs:
            blob.delete()
        print(f"Cleared {len(existing_blobs)} existing vector store files at {uri}")

    uploaded = 0
    for path in directory.rglob("*"):
        if path.is_dir():
            continue

        relative_path = path.relative_to(directory).as_posix()
        blob_name = f"{prefix.rstrip('/')}/{relative_path}" if prefix else relative_path
        blob = bucket.blob(blob_name)
        blob.upload_from_filename(path.as_posix())
        uploaded += 1

    print(f"Uploaded {uploaded} vector store files to gs://{bucket_name}/{prefix}")


def load_documents():
    if DATA_PATH.startswith("gs://"):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            try:
                _download_gcs_docs(DATA_PATH, tmp_path)
            except Exception as exc:
                print(f"Failed to fetch documents from {DATA_PATH}: {exc}")
                return []
            return _load_local_documents(tmp_path.as_posix())

    return _load_local_documents(DATA_PATH)


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

    try:
        embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
        print("Using OpenAI embeddings...")
    except Exception as e:
        print(f"OpenAI embeddings failed: {e}")
        print("Falling back to local HuggingFace embeddings...")
        embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")

    if CHROMA_PATH.exists():
        shutil.rmtree(CHROMA_PATH)
    CHROMA_PATH.mkdir(parents=True, exist_ok=True)

    db = Chroma.from_documents(chunks, embeddings, persist_directory=CHROMA_PATH.as_posix())
    # db.persist()
    print("Documents embedded and saved to ChromaDB.")

    try:
        _upload_directory_to_gcs(CHROMA_PATH, VECTOR_STORE_GCS_URI)
    except Exception as exc:
        print(f"Failed to upload vector store to Cloud Storage: {exc}")
        raise


if __name__ == "__main__":
    main()
