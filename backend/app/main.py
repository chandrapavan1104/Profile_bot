import os
import shutil
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain.chains import RetrievalQA
from dotenv import load_dotenv
from google.cloud import storage

from app.persona_prompt import persona_prompt

load_dotenv()

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


class QueryRequest(BaseModel):
    query: str


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
    global qa_chain
    _download_vector_store()
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    vectordb = Chroma(persist_directory=CHROMA_PATH.as_posix(), embedding_function=embeddings)
    retriever = vectordb.as_retriever(search_kwargs={"k": 5})
    llm = ChatOpenAI(temperature=0.2, model="gpt-4")

    prompt_template = ChatPromptTemplate.from_messages(
        [
            ("system", "{persona_instructions}\n\nRelevant context:\n{context}"),
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
    response = qa_chain.run(request.query)
    return {"response": response}
