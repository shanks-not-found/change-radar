"""
Demo Project: FastAPI + LangChain + ChromaDB Service.
Realistic AI service utilizing pinned dependencies.
"""

from typing import List, Optional
from fastapi import FastAPI, HTTPException, Query, status
from pydantic import BaseModel, Field
import chromadb
from chromadb.config import Settings
from langchain.chains import LLMChain
from langchain_core.prompts import PromptTemplate

app = FastAPI(title="Document AI Service", version="1.0.0")

class SearchQuery(BaseModel):
    query: str = Field(..., min_length=2)
    top_k: int = Field(default=5, ge=1, le=20)

    class Config:
        # Note: Pydantic v2 replaces Config with ConfigDict
        schema_extra = {
            "example": {"query": "vector retrieval", "top_k": 3}
        }

class DocumentPayload(BaseModel):
    doc_id: str
    content: str
    metadata: Optional[dict] = None

# Initialize persistent ChromaDB client
client = chromadb.Client(Settings(chroma_db_impl="duckdb+parquet", persist_directory="./chroma_data"))
collection = client.get_or_create_collection(name="project_documents")

@app.post("/documents", status_code=status.HTTP_201_CREATED)
def index_document(payload: DocumentPayload):
    # Uses legacy pydantic dict() method
    raw_dict = payload.dict()
    collection.add(
        ids=[payload.doc_id],
        documents=[payload.content],
        metadatas=[payload.metadata or {}],
    )
    return {"status": "indexed", "data": raw_dict}

@app.post("/search")
def search_documents(query: SearchQuery):
    results = collection.query(
        query_texts=[query.query],
        n_results=query.top_k,
    )
    return {"results": results}

@app.get("/summarize")
def summarize_doc(text: str = Query(..., min_length=5)):
    # Legacy LangChain LLMChain usage
    prompt = PromptTemplate(
        input_variables=["text"],
        template="Summarize the following text in one sentence:\n{text}"
    )
    # chain = LLMChain(llm=..., prompt=prompt)
    return {"summary": f"Summary of: {text[:30]}..."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8080)
