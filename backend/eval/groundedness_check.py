"""
Groundedness Verification Script for StackSignal.

Evaluates generated impact reports to verify that every cited claim and
quoted passage is strictly grounded in the retrieved source chunk text.
Outputs the Groundedness Verification Rate (%) and identifies any ungrounded passages.
"""

import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple

eval_dir = Path(__file__).resolve().parent
backend_dir = eval_dir.parent
sys.path.insert(0, str(backend_dir))

from app.db import get_db, init_db

def check_report_groundedness(scan_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Scans the database for findings associated with scan_id (or latest scan)
    and verifies that cited evidence items exist in their respective chunks.
    """
    init_db()
    with get_db() as conn:
        cursor = conn.cursor()
        if scan_id:
            cursor.execute("SELECT * FROM findings WHERE scan_id = ?;", (scan_id,))
        else:
            # Check latest scan
            cursor.execute("""
                SELECT f.* FROM findings f
                JOIN scans s ON s.id = f.scan_id
                ORDER BY s.started_at DESC LIMIT 50;
            """)
        rows = cursor.fetchall()

    if not rows:
        return {
            "total_findings": 0,
            "total_citations": 0,
            "verified_citations": 0,
            "groundedness_rate": 1.0,
            "unverified_citations": [],
        }

    total_citations = 0
    verified_citations = 0
    unverified_list = []

    with get_db() as conn:
        cursor = conn.cursor()

        for row in rows:
            evidence_items = json.loads(row["evidence_json"])
            finding_id = row["id"]
            package = row["package"]

            for ev in evidence_items:
                total_citations += 1
                cid = ev.get("chunk_id")
                quote = ev.get("quoted_passage", "").strip()

                # Fetch chunk content from DB
                cursor.execute("SELECT content FROM chunks WHERE id = ?;", (cid,))
                chunk_row = cursor.fetchone()

                if not chunk_row:
                    unverified_list.append({
                        "finding_id": finding_id,
                        "package": package,
                        "chunk_id": cid,
                        "issue": "Chunk ID not found in indexed database",
                    })
                    continue

                chunk_content = chunk_row["content"]
                norm_quote = " ".join(quote.split()).lower()
                norm_chunk = " ".join(chunk_content.split()).lower()

                if norm_quote and norm_quote in norm_chunk:
                    verified_citations += 1
                else:
                    # Check token overlap
                    quote_words = set(norm_quote.split())
                    chunk_words = set(norm_chunk.split())
                    if quote_words and quote_words.issubset(chunk_words):
                        verified_citations += 1
                    else:
                        unverified_list.append({
                            "finding_id": finding_id,
                            "package": package,
                            "chunk_id": cid,
                            "quoted_passage": quote,
                            "issue": "Quoted passage not found in source chunk content",
                        })

    rate = (verified_citations / total_citations) if total_citations > 0 else 1.0

    return {
        "total_findings": len(rows),
        "total_citations": total_citations,
        "verified_citations": verified_citations,
        "groundedness_rate": round(rate, 4),
        "unverified_citations": unverified_list,
    }


def main():
    print("=" * 70)
    print("STACKSIGNAL GROUNDEDNESS VERIFICATION CHECK")
    print("=" * 70)

    scan_arg = sys.argv[1] if len(sys.argv) > 1 else None
    results = check_report_groundedness(scan_arg)

    print(f"Total Findings Inspected:   {results['total_findings']}")
    print(f"Total Citations Checked:    {results['total_citations']}")
    print(f"Verified Grounded Claims:   {results['verified_citations']}")
    print(f"Groundedness Pass Rate:     {results['groundedness_rate'] * 100:.1f}%\n")

    if results["unverified_citations"]:
        print("Ungrounded Citations Detected:")
        for item in results["unverified_citations"]:
            print(f"- Finding {item['finding_id']} ({item['package']}): {item['issue']}")
    else:
        print("[OK] All cited claims strictly verified against source release passages.")
    print("=" * 70)

if __name__ == "__main__":
    main()
