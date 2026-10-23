import sqlite3
import json
from contextlib import contextmanager
from pathlib import Path
from typing import Generator
from app.config import settings

def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(settings.database_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

@contextmanager
def get_db() -> Generator[sqlite3.Connection, None, None]:
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def init_db() -> None:
    db_path = Path(settings.database_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    with get_db() as conn:
        cursor = conn.cursor()

        # Projects Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                source_type TEXT NOT NULL,
                source_ref TEXT,
                local_path TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL
            );
        """)

        # Dependencies Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS dependencies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id TEXT NOT NULL,
                package_name TEXT NOT NULL,
                specifier TEXT,
                pinned_version TEXT,
                source_file TEXT NOT NULL,
                latest_version TEXT,
                vulnerability_count INTEGER DEFAULT 0,
                usage_count INTEGER DEFAULT 0,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
            );
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_dep_project ON dependencies(project_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_dep_pkg ON dependencies(package_name);")

        # Code References Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS code_references (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id TEXT NOT NULL,
                package_name TEXT NOT NULL,
                file_path TEXT NOT NULL,
                line_number INTEGER NOT NULL,
                snippet TEXT NOT NULL,
                symbol TEXT,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
            );
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_code_ref_proj_pkg ON code_references(project_id, package_name);")

        # Scans Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS scans (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                status TEXT NOT NULL,
                stage_description TEXT,
                progress_percentage INTEGER DEFAULT 0,
                error_message TEXT,
                started_at TIMESTAMP NOT NULL,
                completed_at TIMESTAMP,
                summary_counts_json TEXT,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
            );
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_scans_project ON scans(project_id);")

        # Raw Documents Table (GitHub Releases, OSV Advisories)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS raw_documents (
                id TEXT PRIMARY KEY,
                package_name TEXT NOT NULL,
                source_type TEXT NOT NULL,
                version TEXT,
                title TEXT,
                url TEXT NOT NULL,
                published_at TEXT,
                raw_content TEXT NOT NULL,
                content_hash TEXT UNIQUE NOT NULL,
                created_at TIMESTAMP NOT NULL
            );
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_raw_doc_pkg ON raw_documents(package_name);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_raw_doc_hash ON raw_documents(content_hash);")

        # Chunks Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS chunks (
                id TEXT PRIMARY KEY,
                document_id TEXT NOT NULL,
                package_name TEXT NOT NULL,
                version TEXT,
                section_heading TEXT,
                chunk_index INTEGER NOT NULL,
                content TEXT NOT NULL,
                url TEXT NOT NULL,
                published_at TEXT,
                metadata_json TEXT NOT NULL,
                FOREIGN KEY (document_id) REFERENCES raw_documents(id) ON DELETE CASCADE
            );
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_chunks_pkg ON chunks(package_name);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_chunks_doc ON chunks(document_id);")

        # SQLite FTS5 Virtual Table for Keyword Search
        cursor.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
                chunk_id UNINDEXED,
                package_name,
                version,
                section_heading,
                content,
                tokenize = 'porter unicode61'
            );
        """)

        # Findings Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS findings (
                id TEXT PRIMARY KEY,
                scan_id TEXT NOT NULL,
                project_id TEXT NOT NULL,
                package TEXT NOT NULL,
                change_summary TEXT NOT NULL,
                change_type TEXT NOT NULL,
                affects_project TEXT NOT NULL,
                severity TEXT NOT NULL,
                confidence REAL NOT NULL,
                why_it_matters TEXT NOT NULL,
                code_references_json TEXT NOT NULL,
                recommended_checks_json TEXT NOT NULL,
                suggested_tests_json TEXT NOT NULL,
                evidence_json TEXT NOT NULL,
                uncertainty_notes TEXT,
                explainability_json TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL,
                FOREIGN KEY (scan_id) REFERENCES scans(id) ON DELETE CASCADE,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
            );
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_findings_scan ON findings(scan_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_findings_proj ON findings(project_id);")

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully.")
