#!/usr/bin/env python3
"""Reconcile the source inventory with the extracted pages and recorded reviews."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT / "catalog/research"


def main():
    inventory = json.loads((RESEARCH / "local-pdf-inventory.json").read_text())
    discovery = json.loads((RESEARCH / "pandius-item-discovery.json").read_text())
    destination = RESEARCH / "exhaustive-audit.json"
    previous = json.loads(destination.read_text()) if destination.exists() else {}
    previous_pages = {
        (document["sha256"], page["page"]): page
        for document in previous.get("pdfs", [])
        for page in document["pages"]
    }
    documents = []
    for source in inventory["pdfs"]:
        cache = source.get("ocr_text_cache") or source["text_cache"]
        pages = (ROOT / cache).read_text().split("\f")
        checked = set(source.get("visually_verified_pdf_pages", []))
        documents.append({
            "file": source["file"],
            "sha256": source["sha256"],
            "text_cache": cache,
            "pages": [
                {
                    **previous_pages.get((source["sha256"], number), {}),
                    "page": number,
                    "extracted_characters": len(page.strip()),
                    "selected_facts_checked": number in checked,
                    "exhaustive_item_review": previous_pages.get(
                        (source["sha256"], number), {}
                    ).get("exhaustive_item_review", "pending"),
                }
                for number, page in enumerate(pages[:source["pages"]], 1)
            ],
        })
        if len(documents[-1]["pages"]) != source["pages"]:
            raise ValueError(f"Page count mismatch in {source['file']}")
    inventoried = {source["file"] for source in inventory["pdfs"]}
    supplied = [*ROOT.glob("*.pdf"), *(ROOT / "pdfs").iterdir()]
    reviews = previous.get("other_file_reviews", {})
    untracked = sorted(str(path.relative_to(ROOT)) for path in supplied
                       if path.is_file() and str(path.relative_to(ROOT)) not in inventoried)
    result = {
        **previous,
        "pdfs": documents,
        "other_supplied_files_to_triage": [file for file in untracked if file not in reviews],
        "other_file_reviews": reviews,
        "external_source_gaps": previous.get("external_source_gaps", {}),
        "pandius_documents": discovery["distinct_document_paths"],
        "pandius_discovery_queue": "catalog/research/pandius-item-discovery.json",
    }
    temporary = destination.with_suffix(".tmp")
    temporary.write_text(json.dumps(result, indent=2) + "\n")
    temporary.replace(destination)
    print(f"Tracked {sum(len(document['pages']) for document in documents)} PDF pages.")
    print(f"Additional files to triage: {len(result["other_supplied_files_to_triage"])}.")


if __name__ == "__main__":
    main()
