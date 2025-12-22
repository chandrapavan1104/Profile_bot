import os
import shutil
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import AsyncGenerator
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain.chains import RetrievalQA
from dotenv import load_dotenv
from google.cloud import storage

from app.persona_prompt import persona_prompt

load_dotenv()

# Configure LangSmith tracing via environment variables
# These should be set in your .env file or environment:
# LANGSMITH_TRACING=true
# LANGSMITH_API_KEY=your_api_key
# LANGSMITH_PROJECT=profile_bot (optional)
# LANGSMITH_ENDPOINT=https://api.smith.langchain.com (optional, defaults to this)

# Set LangSmith environment variables if not already set
if os.getenv("LANGSMITH_TRACING") is None:
    os.environ["LANGSMITH_TRACING"] = "true"

if os.getenv("LANGSMITH_ENDPOINT") is None:
    os.environ["LANGSMITH_ENDPOINT"] = "https://api.smith.langchain.com"

# Optional: Set project name if not already set
if os.getenv("LANGSMITH_PROJECT") is None:
    os.environ["LANGSMITH_PROJECT"] = "profile_bot"

app = FastAPI()

allowed_origins = [
    origin.strip()
    for origin in os.getenv("ALLOWED_ORIGINS", "http://localhost:5173").split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

CHROMA_PATH = Path(os.getenv("VECTOR_STORE_PATH", "/tmp/data_store")).resolve()
VECTOR_STORE_GCS_URI = os.getenv("VECTOR_STORE_GCS_URI")


class Message(BaseModel):
    role: str
    content: str


class QueryRequest(BaseModel):
    query: str
    messages: list[Message] | None = None


def _download_vector_store():
    if not VECTOR_STORE_GCS_URI:
        print("VECTOR_STORE_GCS_URI not set; using local vector store path only.")
        CHROMA_PATH.mkdir(parents=True, exist_ok=True)
        return

    if not VECTOR_STORE_GCS_URI.startswith("gs://"):
        raise ValueError("VECTOR_STORE_GCS_URI must start with gs://")

    bucket_path = VECTOR_STORE_GCS_URI[5:]
    if "/" in bucket_path:
        bucket_name, prefix = bucket_path.split("/", 1)
    else:
        bucket_name, prefix = bucket_path, ""

    client = storage.Client()
    blobs = list(client.list_blobs(bucket_name, prefix=prefix))

    if not blobs:
        raise FileNotFoundError(
            f"No blobs found at {VECTOR_STORE_GCS_URI}. Ensure the ingestion job uploaded files."
        )

    if CHROMA_PATH.exists():
        shutil.rmtree(CHROMA_PATH)
    CHROMA_PATH.mkdir(parents=True, exist_ok=True)

    for blob in blobs:
        if blob.name.endswith("/"):
            continue

        relative_name = blob.name[len(prefix):].lstrip("/") if prefix else blob.name
        local_path = CHROMA_PATH / relative_name
        local_path.parent.mkdir(parents=True, exist_ok=True)
        blob.download_to_filename(local_path.as_posix())

    print(f"Downloaded vector store from {VECTOR_STORE_GCS_URI} to {CHROMA_PATH}")


@app.on_event("startup")
def startup_event():
    global qa_chain, llm, retriever
    _download_vector_store()
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    vectordb = Chroma(persist_directory=CHROMA_PATH.as_posix(), embedding_function=embeddings)
    # Reduce k from 5 to 3 for faster retrieval and less context
    retriever = vectordb.as_retriever(search_kwargs={"k": 3})
    # Use faster model: gpt-4o-mini is much faster than gpt-4 variants
    # Alternative: "gpt-3.5-turbo" for even faster responses
    llm = ChatOpenAI(
        temperature=0.2,
        model="gpt-4o-mini",  # Fastest GPT-4 class model
        max_tokens=500,  # Limit response length for faster generation
        timeout=30,  # Set timeout to fail fast
    )

    # Prompt is kept simple; we inline chat history into the question text
    prompt_template = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "{persona_instructions}\n\nContext:\n{context}",
            ),
            ("human", "{question}"),
        ]
    ).partial(persona_instructions=persona_prompt.strip())

    qa_chain = RetrievalQA.from_chain_type(
        llm=llm,
        chain_type="stuff",
        retriever=retriever,
        chain_type_kwargs={
            "prompt": prompt_template,
            "document_variable_name": "context"
        }
    )


@app.post("/ask")
def ask(request: QueryRequest):
    """
    Optimized endpoint for low-latency responses.
    Uses invoke instead of run for better performance.
    """
    # Build chat history text from provided messages
    history_text = "None"
    if request.messages:
        parts: list[str] = []
        for msg in request.messages:
            role = msg.role.lower()
            prefix = "User" if role == "user" else "Assistant"
            parts.append(f"{prefix}: {msg.content}")
        history_text = "\n".join(parts) if parts else "None"

    # Inline history into the question we send to the chain
    combined_question = (
        f"Conversation so far:\n{history_text}\n\n"
        f"Current question:\n{request.query}"
    )

    # Use invoke instead of run for better performance
    # invoke returns dict, run returns string directly
    result = qa_chain.invoke({"query": combined_question})
    
    # Extract response from result dict
    if isinstance(result, dict):
        response = result.get("result", result.get("answer", str(result)))
    else:
        response = str(result)
    
    return {"response": response}


@app.post("/ask/stream")
async def ask_stream(request: QueryRequest):
    """
    Streaming endpoint for lower perceived latency.
    Returns response chunks as they're generated.
    """
    async def generate() -> AsyncGenerator[str, None]:
        try:
            # Use the chain's streaming capability
            full_response = ""
            # Build chat history
            history_text = "None"
            if request.messages:
                parts: list[str] = []
                for msg in request.messages:
                    role = msg.role.lower()
                    prefix = "User" if role == "user" else "Assistant"
                    parts.append(f"{prefix}: {msg.content}")
                history_text = "\n".join(parts) if parts else "None"

            combined_question = (
                f"Conversation so far:\n{history_text}\n\n"
                f"Current question:\n{request.query}"
            )

            async for chunk in qa_chain.astream({"query": combined_question}):
                if isinstance(chunk, dict):
                    text = chunk.get("result", chunk.get("answer", ""))
                else:
                    text = str(chunk)
                
                if text and text != full_response:  # Only send new content
                    new_content = text[len(full_response):]
                    full_response = text
                    if new_content:
                        yield f"data: {new_content}\n\n"
            
            yield "data: [DONE]\n\n"
        except Exception as e:
            yield f"data: Error: {str(e)}\n\n"
    
    return StreamingResponse(generate(), media_type="text/event-stream")
