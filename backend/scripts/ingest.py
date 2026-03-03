import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import requests
from google.cloud import storage
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_core.documents import Document
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
GITHUB_USERNAME = os.getenv("GITHUB_USERNAME") or os.getenv("GITHUB_USER")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_REPO_LIMIT = int(os.getenv("GITHUB_REPO_LIMIT", "8"))
GITHUB_MAX_README_CHARS = int(os.getenv("GITHUB_MAX_README_CHARS", "8000"))
GITHUB_INCLUDE_README = os.getenv("GITHUB_INCLUDE_README", "true").lower() in ("1", "true", "yes")
GITHUB_CONTEXT_OUTPUT = os.getenv("GITHUB_CONTEXT_OUTPUT")


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


def _github_headers():
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "profile-bot-ingest",
    }
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    return headers


def _github_get(url: str, params: dict | None = None, allow_not_found: bool = False):
    try:
        response = requests.get(
            url,
            headers=_github_headers(),
            params=params,
            timeout=30
        )
    except requests.RequestException as exc:
        print(f"Warning: GitHub request failed for {url}: {exc}")
        return None

    if response.status_code == 404 and allow_not_found:
        return None

    if not response.ok:
        if response.status_code == 403 and "rate limit" in response.text.lower():
            print("GitHub API rate limit reached. Set GITHUB_TOKEN to increase limits.")
        else:
            print(f"Warning: GitHub request failed for {url}: {response.status_code}")
        return None

    return response


def _github_post(url: str, payload: dict):
    try:
        response = requests.post(
            url,
            headers=_github_headers(),
            json=payload,
            timeout=30
        )
    except requests.RequestException as exc:
        print(f"Warning: GitHub request failed for {url}: {exc}")
        return None

    if not response.ok:
        print(f"Warning: GitHub request failed for {url}: {response.status_code}")
        return None

    return response


def _fetch_github_user(username: str):
    response = _github_get(f"https://api.github.com/users/{username}")
    if not response:
        return None
    data = response.json()
    return data if isinstance(data, dict) else None


def _fetch_github_repos(username: str):
    params = {
        "per_page": GITHUB_REPO_LIMIT,
        "sort": "pushed",
        "direction": "desc",
        "type": "owner",
    }
    response = _github_get(f"https://api.github.com/users/{username}/repos", params=params)
    if not response:
        return []
    data = response.json()
    return data if isinstance(data, list) else []


def _fetch_github_contributions(username: str):
    if not GITHUB_TOKEN:
        return None
    query = """
    query($login: String!) {
      user(login: $login) {
        contributionsCollection {
          contributionCalendar {
            totalContributions
          }
        }
      }
    }
    """
    response = _github_post(
        "https://api.github.com/graphql",
        {"query": query, "variables": {"login": username}}
    )
    if not response:
        return None
    data = response.json()
    if "errors" in data:
        print(f"Warning: GitHub GraphQL errors: {data['errors']}")
        return None
    return (
        data.get("data", {})
        .get("user", {})
        .get("contributionsCollection", {})
        .get("contributionCalendar", {})
        .get("totalContributions")
    )


def _fetch_profile_readme(username: str):
    if not GITHUB_INCLUDE_README:
        return ""

    for branch in ("main", "master"):
        url = f"https://raw.githubusercontent.com/{username}/{username}/{branch}/README.md"
        response = _github_get(url, allow_not_found=True)
        if response and response.text:
            text = response.text.strip()
            if len(text) > GITHUB_MAX_README_CHARS:
                text = f"{text[:GITHUB_MAX_README_CHARS]}\n\n[README truncated]"
            return text

    return ""


def _summarize_languages(repos: list[dict]):
    totals: dict[str, int] = {}
    for repo in repos:
        if repo.get("fork"):
            continue
        languages_url = repo.get("languages_url")
        if not languages_url:
            continue
        response = _github_get(languages_url)
        if not response:
            continue
        data = response.json()
        if not isinstance(data, dict):
            continue
        for lang, size in data.items():
            totals[lang] = totals.get(lang, 0) + int(size)

    total_size = sum(totals.values())
    if total_size == 0:
        return []

    items = sorted(totals.items(), key=lambda item: item[1], reverse=True)
    top_items = items[:8]
    return [(lang, round(size / total_size * 100, 1)) for lang, size in top_items]


def _build_repo_lines(repos: list[dict]):
    lines: list[str] = []
    for repo in repos:
        if repo.get("fork"):
            continue
        name = repo.get("name")
        if not name:
            continue
        description = repo.get("description") or ""
        stars = repo.get("stargazers_count", 0)
        language = repo.get("language") or "N/A"
        updated_at = repo.get("pushed_at") or repo.get("updated_at") or ""
        updated = updated_at[:10] if updated_at else "unknown"
        if description:
            line = f"- **{name}**: {description} (Stars: {stars}, Lang: {language}, Updated: {updated})"
        else:
            line = f"- **{name}** (Stars: {stars}, Lang: {language}, Updated: {updated})"
        lines.append(line)
    return lines


def _build_github_markdown(username: str):
    user = _fetch_github_user(username)
    if not user:
        return ""

    name = user.get("name") or username
    bio = user.get("bio") or "No bio provided."
    company = user.get("company") or "N/A"
    location = user.get("location") or "N/A"
    blog = user.get("blog") or "N/A"
    followers = user.get("followers", 0)
    public_repos = user.get("public_repos", 0)

    repos = _fetch_github_repos(username)
    repo_lines = _build_repo_lines(repos)
    languages = _summarize_languages(repos)
    contributions = _fetch_github_contributions(username)
    readme = _fetch_profile_readme(username)

    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    lines = [
        f"# GitHub Profile: {name} (@{username})",
        f"Generated: {generated_at} UTC",
        "",
        "## Bio",
        bio,
        "",
        "## Highlights",
        f"- Company: {company}",
        f"- Location: {location}",
        f"- Website: {blog}",
        f"- Followers: {followers}",
        f"- Public repos: {public_repos}",
        "",
        "## Contributions",
    ]

    if contributions is None:
        lines.append("Total contributions (last 12 months): unavailable (set GITHUB_TOKEN).")
    else:
        lines.append(f"Total contributions (last 12 months): {contributions}")

    lines.append("")
    lines.append("## Repositories")
    if repo_lines:
        lines.extend(repo_lines)
    else:
        lines.append("No repositories found.")

    lines.append("")
    lines.append("## Tech Stack")
    if languages:
        lines.extend([f"- {lang}: {percent}%" for lang, percent in languages])
    else:
        lines.append("No language data available.")

    if readme:
        lines.append("")
        lines.append("## Profile README")
        lines.append(readme)

    return "\n".join(lines).strip()


def _load_github_document():
    if not GITHUB_USERNAME:
        return None

    markdown = _build_github_markdown(GITHUB_USERNAME)
    if not markdown:
        return None

    if GITHUB_CONTEXT_OUTPUT:
        output_path = Path(GITHUB_CONTEXT_OUTPUT)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(markdown, encoding="utf-8")

    return Document(
        page_content=markdown,
        metadata={"source": "github", "username": GITHUB_USERNAME}
    )


def load_documents():
    if DATA_PATH.startswith("gs://"):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            try:
                _download_gcs_docs(DATA_PATH, tmp_path)
            except Exception as exc:
                print(f"Failed to fetch documents from {DATA_PATH}: {exc}")
                return []
            documents = _load_local_documents(tmp_path.as_posix())
    else:
        documents = _load_local_documents(DATA_PATH)

    github_doc = _load_github_document()
    if github_doc:
        documents.append(github_doc)

    return documents


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
