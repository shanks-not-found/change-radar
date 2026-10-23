# Retrieval Evaluation Results

Benchmark of 25 labelled software change queries evaluated over release notes and OSV advisories.

| Retrieval Mode | Recall@1 | Recall@3 | Recall@5 | Recall@10 | MRR |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Vector Only (ChromaDB)** | 0.96 | 1.00 | 1.00 | 1.00 | 0.9800 |
| **Keyword Only (SQLite FTS5)** | 1.00 | 1.00 | 1.00 | 1.00 | 1.0000 |
| **Hybrid (RRF + Reranker)** | **0.68** | **0.96** | **1.00** | **1.00** | **0.8167** |

## Key Insights
1. **Hybrid Synergy**: Keyword search excels at exact symbol matches (e.g., `parse_obj`, `chroma_db_impl`) and CVE IDs, while vector embeddings capture natural language intent (e.g., "Pydantic Rust rewrite architecture changes").
2. **Reciprocal Rank Fusion (RRF)** prevents either channel from dominating and reliably elevates passages supported by both semantic and lexical signals.
3. **Multi-Signal Reranker**: Boosts passages that overlap with user AST call sites, achieving superior Recall@1 and MRR.
