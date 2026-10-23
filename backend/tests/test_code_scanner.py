import pytest
from pathlib import Path
from app.analysis.code_scanner import scan_file, scan_project_code

def test_scan_file_ast(tmp_path: Path):
    py_file = tmp_path / "service.py"
    py_file.write_text("""
from fastapi import FastAPI, Depends
import pydantic as pyd
from langchain.chains import LLMChain

app = FastAPI()

class User(pyd.BaseModel):
    name: str

@app.get("/")
def read_root():
    chain = LLMChain()
    return {"hello": "world"}
""", encoding="utf-8")

    refs = scan_file(py_file, tmp_path)
    symbols = [r[1].symbol for r in refs]

    assert "FastAPI" in symbols
    assert "BaseModel" in symbols
    assert "LLMChain" in symbols

    # Check line numbers and snippets
    fastapi_ref = next(r[1] for r in refs if r[1].symbol == "FastAPI" and "app = FastAPI()" in r[1].snippet)
    assert fastapi_ref.line_number == 6
    assert fastapi_ref.file_path == "service.py"

def test_scan_unparseable_file_skipped(tmp_path: Path):
    bad_file = tmp_path / "broken.py"
    bad_file.write_text("def broken_syntax(:\n   this is not valid python", encoding="utf-8")

    refs = scan_file(bad_file, tmp_path)
    assert refs == []

def test_scan_project_code(tmp_path: Path):
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "app.py").write_text("""
import chromadb
client = chromadb.Client()
""", encoding="utf-8")

    res = scan_project_code(tmp_path, ["chromadb", "pydantic"])
    assert "chromadb" in res
    assert len(res["chromadb"]) >= 1
    assert any("chromadb.Client" in r.snippet or r.symbol in ("chromadb", "Client") for r in res["chromadb"])
    assert res["pydantic"] == []
