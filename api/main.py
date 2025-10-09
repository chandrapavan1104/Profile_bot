import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain.chains import RetrievalQA
from dotenv import load_dotenv
from api.persona_prompt import persona_prompt

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

CHROMA_PATH = "data_store"


class QueryRequest(BaseModel):
    query: str

@app.on_event("startup")
def startup_event():
    global qa_chain
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    vectordb = Chroma(persist_directory=CHROMA_PATH, embedding_function=embeddings)
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
