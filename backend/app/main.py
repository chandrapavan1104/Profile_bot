import asyncio
import logging
import json
import os
import random
import shutil
import time
import uuid
from pathlib import Path
from typing import Any, AsyncGenerator

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from google.cloud import storage
from langchain_chroma import Chroma
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from openai import APIConnectionError, APIError, APITimeoutError, RateLimitError
from pydantic import BaseModel

from app.persona_prompt import persona_prompt

load_dotenv()
logger = logging.getLogger(__name__)

DEFAULT_ORIGINS = ("http://localhost:5173", "http://localhost:5174")
CHROMA_PATH = Path(os.getenv("VECTOR_STORE_PATH", "/tmp/data_store")).resolve()
VECTOR_STORE_GCS_URI = os.getenv("VECTOR_STORE_GCS_URI", "").strip()

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
CHAT_MODEL = os.getenv("CHAT_MODEL", "gpt-4o-mini")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.2"))
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "500"))
LLM_TIMEOUT_SECONDS = int(os.getenv("LLM_TIMEOUT_SECONDS", "30"))
RETRIEVER_K = int(os.getenv("RETRIEVER_K", "3"))
OPENAI_MAX_RETRIES = int(os.getenv("OPENAI_MAX_RETRIES", "2"))
OPENAI_RETRY_BASE_SECONDS = float(os.getenv("OPENAI_RETRY_BASE_SECONDS", "1.0"))
OPENAI_RETRY_MAX_SECONDS = float(os.getenv("OPENAI_RETRY_MAX_SECONDS", "8.0"))
MAX_QUERY_CHARS = int(os.getenv("MAX_QUERY_CHARS", "4000"))
MAX_MESSAGES = int(os.getenv("MAX_MESSAGES", "20"))
MAX_MESSAGE_CHARS = int(os.getenv("MAX_MESSAGE_CHARS", "1500"))
SERVICE_NAME = os.getenv("SERVICE_NAME", "profile-bot-api")
OPENAI_PROVIDER = "openai"

retriever: Any | None = None
llm: ChatOpenAI | None = None
prompt_template: ChatPromptTemplate | None = None


def _configure_langsmith() -> None:
    """
    Enable LangSmith defaults only when API key is present.
    """
    if not os.getenv("LANGSMITH_API_KEY"):
        return

    os.environ.setdefault("LANGSMITH_TRACING", "true")
    os.environ.setdefault("LANGSMITH_ENDPOINT", "https://api.smith.langchain.com")
    os.environ.setdefault("LANGSMITH_PROJECT", "profile_bot")


def _get_allowed_origins() -> list[str]:
    raw_origins = os.getenv("ALLOWED_ORIGINS", ",".join(DEFAULT_ORIGINS))
    return [origin.strip() for origin in raw_origins.split(",") if origin.strip()]


def _parse_gcs_uri(uri: str) -> tuple[str, str]:
    if not uri.startswith("gs://"):
        raise ValueError(f"VECTOR_STORE_GCS_URI must start with gs://, received: {uri}")

    bucket_and_prefix = uri[5:]
    bucket, _, prefix = bucket_and_prefix.partition("/")
    normalized_prefix = prefix.strip("/")
    if normalized_prefix:
        normalized_prefix = f"{normalized_prefix}/"
    return bucket, normalized_prefix


def _download_vector_store() -> None:
    if not VECTOR_STORE_GCS_URI:
        logger.info("VECTOR_STORE_GCS_URI not set; using local vector store path only.")
        CHROMA_PATH.mkdir(parents=True, exist_ok=True)
        return

    bucket_name, prefix = _parse_gcs_uri(VECTOR_STORE_GCS_URI)
    client = storage.Client()
    blobs = list(client.list_blobs(bucket_name, prefix=prefix))
    files = [blob for blob in blobs if not blob.name.endswith("/")]

    if not files:
        raise FileNotFoundError(
            f"No blobs found at {VECTOR_STORE_GCS_URI}. Ensure ingestion uploaded files."
        )

    if CHROMA_PATH.exists():
        shutil.rmtree(CHROMA_PATH)
    CHROMA_PATH.mkdir(parents=True, exist_ok=True)

    for blob in files:
        relative_name = blob.name[len(prefix):] if prefix else blob.name
        local_path = CHROMA_PATH / relative_name
        local_path.parent.mkdir(parents=True, exist_ok=True)
        blob.download_to_filename(local_path.as_posix())

    logger.info("Downloaded %s vector-store files to %s", len(files), CHROMA_PATH)


def _require_runtime() -> tuple[Any, ChatOpenAI, ChatPromptTemplate]:
    if retriever is None or llm is None or prompt_template is None:
        raise RuntimeError("App runtime is not initialized yet.")
    return retriever, llm, prompt_template


def _format_history(messages: list["Message"] | None) -> str:
    if not messages:
        return "None"

    lines: list[str] = []
    for msg in messages:
        role = msg.role.strip().lower()
        prefix = "User" if role == "user" else "Assistant"
        lines.append(f"{prefix}: {msg.content}")
    return "\n".join(lines) if lines else "None"


def _compose_question(query: str, messages: list["Message"] | None) -> str:
    history = _format_history(messages)
    return f"Conversation so far:\n{history}\n\nCurrent question:\n{query}"


def _validate_query_request(payload: "QueryRequest") -> None:
    query = payload.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query must not be empty.")
    if len(query) > MAX_QUERY_CHARS:
        raise HTTPException(
            status_code=413,
            detail=f"Query is too long. Max {MAX_QUERY_CHARS} characters.",
        )

    messages = payload.messages or []
    if len(messages) > MAX_MESSAGES:
        raise HTTPException(
            status_code=413,
            detail=f"Too many history messages. Max {MAX_MESSAGES}.",
        )

    for msg in messages:
        role = msg.role.strip().lower()
        if role not in {"user", "assistant"}:
            raise HTTPException(status_code=400, detail="Message role must be user or assistant.")
        if not msg.content.strip():
            raise HTTPException(status_code=400, detail="Message content must not be empty.")
        if len(msg.content) > MAX_MESSAGE_CHARS:
            raise HTTPException(
                status_code=413,
                detail=f"Message content is too long. Max {MAX_MESSAGE_CHARS} characters.",
            )


def _format_context(docs: list[Any]) -> str:
    return "\n\n".join(doc.page_content for doc in docs)


def _retrieve_documents(query: str) -> list[Any]:
    runtime_retriever, _, _ = _require_runtime()
    if hasattr(runtime_retriever, "get_relevant_documents"):
        return runtime_retriever.get_relevant_documents(query)
    if hasattr(runtime_retriever, "invoke"):
        return runtime_retriever.invoke(query)
    raise AttributeError("Retriever does not support document retrieval methods.")


async def _aretrieve_documents(query: str) -> list[Any]:
    runtime_retriever, _, _ = _require_runtime()
    if hasattr(runtime_retriever, "aget_relevant_documents"):
        return await runtime_retriever.aget_relevant_documents(query)
    if hasattr(runtime_retriever, "ainvoke"):
        return await runtime_retriever.ainvoke(query)
    return _retrieve_documents(query)


def _to_sse_event(data: str) -> str:
    lines = data.splitlines() or [""]
    return "".join(f"data: {line}\n" for line in lines) + "\n"


def _log_structured(event: str, severity: str = "INFO", **fields: Any) -> None:
    payload = {
        "severity": severity,
        "event": event,
        "service": SERVICE_NAME,
        **fields,
    }
    print(
        json.dumps(payload, ensure_ascii=True, separators=(",", ":"), default=str),
        flush=True,
    )


def _extract_token_usage(result: Any) -> dict[str, int | None]:
    usage = {
        "input_tokens": None,
        "output_tokens": None,
        "total_tokens": None,
    }

    usage_metadata = getattr(result, "usage_metadata", None)
    if isinstance(usage_metadata, dict):
        usage["input_tokens"] = usage_metadata.get("input_tokens")
        usage["output_tokens"] = usage_metadata.get("output_tokens")
        usage["total_tokens"] = usage_metadata.get("total_tokens")

    response_metadata = getattr(result, "response_metadata", None)
    if isinstance(response_metadata, dict):
        token_usage = response_metadata.get("token_usage", {})
        if isinstance(token_usage, dict):
            usage["input_tokens"] = usage["input_tokens"] or token_usage.get("prompt_tokens")
            usage["output_tokens"] = usage["output_tokens"] or token_usage.get("completion_tokens")
            usage["total_tokens"] = usage["total_tokens"] or token_usage.get("total_tokens")

    return usage


def _extract_openai_error_message(exc: Exception) -> str:
    message = str(exc).strip()
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        err = body.get("error", {})
        if isinstance(err, dict):
            message = str(err.get("message", message)).strip()
    return " ".join(message.split())[:500]


def _retry_delay_seconds(attempt: int) -> float:
    base_delay = min(OPENAI_RETRY_BASE_SECONDS * (2**attempt), OPENAI_RETRY_MAX_SECONDS)
    return base_delay + random.uniform(0, 0.25)


def _classify_openai_error(exc: Exception) -> tuple[str, int, str, bool, str]:
    status_code = getattr(exc, "status_code", None)
    error_message = _extract_openai_error_message(exc)
    lower_message = error_message.lower()

    if isinstance(exc, APITimeoutError):
        return (
            "timeout",
            504,
            "OpenAI timed out. Please retry in a moment.",
            True,
            error_message,
        )
    if isinstance(exc, RateLimitError) or status_code == 429:
        if "insufficient_quota" in lower_message or "exceeded your current quota" in lower_message:
            return (
                "quota_exceeded",
                429,
                "OpenAI quota/billing is exhausted. Please add credits or billing in OpenAI and retry.",
                False,
                error_message,
            )
        return (
            "rate_limit",
            429,
            "OpenAI is rate-limiting requests. Please retry in a few seconds.",
            True,
            error_message,
        )
    if isinstance(exc, APIConnectionError):
        return (
            "connection_error",
            503,
            "Could not reach OpenAI. Please retry in a moment.",
            True,
            error_message,
        )
    if isinstance(exc, APIError):
        if isinstance(status_code, int) and 400 <= status_code <= 599:
            retryable = status_code >= 500
            return (
                "api_error",
                status_code,
                f"OpenAI request failed with status {status_code}.",
                retryable,
                error_message,
            )
        return (
            "api_error",
            502,
            "OpenAI request failed due to an upstream API error.",
            True,
            error_message,
        )
    return (
        "unexpected",
        500,
        "Unexpected error while contacting OpenAI.",
        False,
        error_message,
    )


_configure_langsmith()
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=_get_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
    request.state.request_id = request_id
    started_at = time.perf_counter()
    status_code = 500
    error_type = ""

    try:
        response = await call_next(request)
        status_code = response.status_code
        response.headers["x-request-id"] = request_id
        return response
    except Exception as exc:
        error_type = exc.__class__.__name__
        raise
    finally:
        latency_ms = round((time.perf_counter() - started_at) * 1000, 2)
        severity = "INFO"
        if error_type or status_code >= 500:
            severity = "ERROR"
        elif status_code >= 400:
            severity = "WARNING"

        _log_structured(
            event="http_request",
            severity=severity,
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            status_code=status_code,
            latency_ms=latency_ms,
            user_agent=request.headers.get("user-agent", ""),
            error_type=error_type,
        )


class Message(BaseModel):
    role: str
    content: str


class QueryRequest(BaseModel):
    query: str
    messages: list[Message] | None = None


@app.on_event("startup")
def startup_event() -> None:
    global llm, retriever, prompt_template
    _download_vector_store()

    embeddings = OpenAIEmbeddings(model=EMBEDDING_MODEL)
    vectordb = Chroma(
        persist_directory=CHROMA_PATH.as_posix(),
        embedding_function=embeddings,
    )

    retriever = vectordb.as_retriever(search_kwargs={"k": RETRIEVER_K})
    llm = ChatOpenAI(
        model=CHAT_MODEL,
        temperature=LLM_TEMPERATURE,
        max_tokens=LLM_MAX_TOKENS,
        timeout=LLM_TIMEOUT_SECONDS,
    )
    prompt_template = ChatPromptTemplate.from_messages(
        [
            ("system", "{persona_instructions}\n\nContext:\n{context}"),
            ("human", "{question}"),
        ]
    ).partial(persona_instructions=persona_prompt.strip())

    logger.info(
        "Runtime initialized (model=%s, embedding_model=%s, retriever_k=%s)",
        CHAT_MODEL,
        EMBEDDING_MODEL,
        RETRIEVER_K,
    )
    _log_structured(
        event="runtime_initialized",
        severity="INFO",
        model=CHAT_MODEL,
        embedding_model=EMBEDDING_MODEL,
        retriever_k=RETRIEVER_K,
        vector_store_gcs_uri=VECTOR_STORE_GCS_URI,
    )


@app.get("/health")
@app.get("/healthz")
def healthz() -> dict[str, str]:
    try:
        _require_runtime()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"status": "ok"}


@app.post("/ask")
def ask(request: QueryRequest, http_request: Request) -> dict[str, str]:
    request_id = getattr(http_request.state, "request_id", "")
    started_at = time.perf_counter()
    try:
        _validate_query_request(request)
        _, runtime_llm, runtime_prompt = _require_runtime()
        question = _compose_question(request.query, request.messages)

        for attempt in range(OPENAI_MAX_RETRIES + 1):
            try:
                docs = _retrieve_documents(request.query)
                context = _format_context(docs)
                messages = runtime_prompt.format_messages(question=question, context=context)
                result = runtime_llm.invoke(messages)
                response = result.content if hasattr(result, "content") else str(result)
                usage = _extract_token_usage(result)
                _log_structured(
                    event="openai_call",
                    severity="INFO",
                    request_id=request_id,
                    endpoint="/ask",
                    upstream_provider=OPENAI_PROVIDER,
                    model=CHAT_MODEL,
                    success=True,
                    retry_attempts=attempt,
                    upstream_latency_ms=round((time.perf_counter() - started_at) * 1000, 2),
                    query_chars=len(request.query),
                    **usage,
                )
                return {"response": response}
            except (APITimeoutError, RateLimitError, APIConnectionError, APIError) as exc:
                (
                    error_type,
                    status_code,
                    user_message,
                    retryable,
                    error_message,
                ) = _classify_openai_error(exc)
                will_retry = retryable and attempt < OPENAI_MAX_RETRIES
                _log_structured(
                    event="openai_call",
                    severity="ERROR",
                    request_id=request_id,
                    endpoint="/ask",
                    upstream_provider=OPENAI_PROVIDER,
                    model=CHAT_MODEL,
                    success=False,
                    error_type=error_type,
                    error_message=error_message,
                    retry_attempt=attempt,
                    will_retry=will_retry,
                    upstream_status_code=getattr(exc, "status_code", None),
                    upstream_latency_ms=round((time.perf_counter() - started_at) * 1000, 2),
                    query_chars=len(request.query),
                )
                if will_retry:
                    time.sleep(_retry_delay_seconds(attempt))
                    continue
                raise HTTPException(status_code=status_code, detail=f"{user_message} ({error_type})") from exc
        raise HTTPException(status_code=503, detail="OpenAI request failed after retries")
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed handling /ask request")
        raise HTTPException(status_code=500, detail="Request failed") from exc


@app.post("/ask/stream")
async def ask_stream(request: QueryRequest, http_request: Request) -> StreamingResponse:
    request_id = getattr(http_request.state, "request_id", "")

    async def generate() -> AsyncGenerator[str, None]:
        started_at = time.perf_counter()
        try:
            _validate_query_request(request)
            _require_runtime()
            question = _compose_question(request.query, request.messages)

            for attempt in range(OPENAI_MAX_RETRIES + 1):
                chunk_count = 0
                streamed_chars = 0
                try:
                    docs = await _aretrieve_documents(request.query)
                    context = _format_context(docs)
                    messages = [
                        SystemMessage(content=f"{persona_prompt.strip()}\n\nContext:\n{context}"),
                        HumanMessage(content=question),
                    ]
                    streaming_llm = ChatOpenAI(
                        model=CHAT_MODEL,
                        temperature=LLM_TEMPERATURE,
                        max_tokens=LLM_MAX_TOKENS,
                        timeout=LLM_TIMEOUT_SECONDS,
                        streaming=True,
                    )
                    async for chunk in streaming_llm.astream(messages):
                        content = getattr(chunk, "content", None)
                        if not content:
                            continue
                        chunk_count += 1
                        streamed_chars += len(content)
                        yield _to_sse_event(content)

                    _log_structured(
                        event="openai_call",
                        severity="INFO",
                        request_id=request_id,
                        endpoint="/ask/stream",
                        upstream_provider=OPENAI_PROVIDER,
                        model=CHAT_MODEL,
                        success=True,
                        retry_attempts=attempt,
                        upstream_latency_ms=round((time.perf_counter() - started_at) * 1000, 2),
                        query_chars=len(request.query),
                        chunk_count=chunk_count,
                        streamed_chars=streamed_chars,
                    )
                    yield "data: [DONE]\n\n"
                    return
                except (APITimeoutError, RateLimitError, APIConnectionError, APIError) as exc:
                    (
                        error_type,
                        _,
                        user_message,
                        retryable,
                        error_message,
                    ) = _classify_openai_error(exc)
                    # Avoid retrying after partial output to prevent duplicated partial streams.
                    can_retry = retryable and attempt < OPENAI_MAX_RETRIES and chunk_count == 0
                    _log_structured(
                        event="openai_call",
                        severity="ERROR",
                        request_id=request_id,
                        endpoint="/ask/stream",
                        upstream_provider=OPENAI_PROVIDER,
                        model=CHAT_MODEL,
                        success=False,
                        error_type=error_type,
                        error_message=error_message,
                        retry_attempt=attempt,
                        will_retry=can_retry,
                        chunk_count=chunk_count,
                        upstream_status_code=getattr(exc, "status_code", None),
                        upstream_latency_ms=round((time.perf_counter() - started_at) * 1000, 2),
                        query_chars=len(request.query),
                    )
                    if can_retry:
                        await asyncio.sleep(_retry_delay_seconds(attempt))
                        continue
                    yield _to_sse_event(f"Error: {user_message} ({error_type})")
                    return
            yield _to_sse_event("Error: OpenAI request failed after retries (retry_exhausted)")
        except Exception as exc:
            logger.exception("Failed handling /ask/stream request")
            _log_structured(
                event="openai_call",
                severity="ERROR",
                request_id=request_id,
                endpoint="/ask/stream",
                upstream_provider=OPENAI_PROVIDER,
                model=CHAT_MODEL,
                success=False,
                error_type="unexpected",
                upstream_latency_ms=round((time.perf_counter() - started_at) * 1000, 2),
                query_chars=len(request.query),
            )
            yield _to_sse_event("Error: Request failed (unexpected)")

    return StreamingResponse(generate(), media_type="text/event-stream")
