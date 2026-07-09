#!/usr/bin/env python3
"""Minimal arXiv fetcher used by /idea-to-proposal Phase 0.5.

Usage:
    python3 tools/arxiv_fetch.py download <id1> <id2> ...

Downloads each arXiv ID's PDF to papers/<id>.pdf with rate limiting and
graceful 429/timeout handling. Skips files that already exist.
"""
from __future__ import annotations

import os
import re
import sys
import time
import urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path

import requests

OUTPUT_DIR = Path("papers")
SLEEP_BETWEEN_REQUESTS = 1.2
TIMEOUT = 30
RETRY = 2


def normalize_id(arxiv_id: str) -> str:
    arxiv_id = arxiv_id.strip()
    # Strip version suffix like v1, v2
    return re.sub(r"v\d+$", "", arxiv_id)


def query_meta(arxiv_id: str) -> dict | None:
    """Fetch metadata for an arXiv ID via the search_query API."""
    base = "http://export.arxiv.org/api/query"
    params = {"id_list": arxiv_id, "max_results": 1}
    url = base + "?" + urllib.parse.urlencode(params)
    for attempt in range(RETRY + 1):
        try:
            r = requests.get(url, timeout=TIMEOUT, headers={"User-Agent": "orbit-idea-to-proposal/1.0"})
            if r.status_code == 200:
                root = ET.fromstring(r.text)
                ns = {"a": "http://www.w3.org/2005/Atom"}
                entry = root.find("a:entry", ns)
                if entry is None:
                    return None
                title_el = entry.find("a:title", ns)
                title = (title_el.text or "").strip().replace("\n", " ") if title_el is not None else "(unknown)"
                title = re.sub(r"\s+", " ", title)
                summary_el = entry.find("a:summary", ns)
                summary = (summary_el.text or "").strip().replace("\n", " ") if summary_el is not None else ""
                summary = re.sub(r"\s+", " ", summary)
                authors = []
                for a in entry.findall("a:author", ns):
                    name_el = a.find("a:name", ns)
                    if name_el is not None and name_el.text:
                        authors.append(name_el.text.strip())
                published_el = entry.find("a:published", ns)
                published = published_el.text if published_el is not None else ""
                return {
                    "id": arxiv_id,
                    "title": title,
                    "authors": authors,
                    "published": published,
                    "summary": summary[:1200],
                }
            else:
                print(f"  meta {arxiv_id}: HTTP {r.status_code} (attempt {attempt+1})")
                time.sleep(2 + attempt)
        except Exception as e:
            print(f"  meta {arxiv_id}: error {e} (attempt {attempt+1})")
            time.sleep(2 + attempt)
    return None


def download_pdf(arxiv_id: str) -> bool:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    target = OUTPUT_DIR / f"{arxiv_id}.pdf"
    if target.exists() and target.stat().st_size > 0:
        return True
    url = f"http://arxiv.org/pdf/{arxiv_id}"
    for attempt in range(RETRY + 1):
        try:
            r = requests.get(url, timeout=TIMEOUT, headers={"User-Agent": "orbit-idea-to-proposal/1.0"}, stream=True)
            if r.status_code == 200:
                with open(target, "wb") as f:
                    for chunk in r.iter_content(chunk_size=65536):
                        if chunk:
                            f.write(chunk)
                if target.stat().st_size > 1024:
                    return True
                else:
                    target.unlink()
                    print(f"  pdf {arxiv_id}: too small, retry")
            else:
                print(f"  pdf {arxiv_id}: HTTP {r.status_code} (attempt {attempt+1})")
                time.sleep(3 + attempt * 2)
        except Exception as e:
            print(f"  pdf {arxiv_id}: error {e} (attempt {attempt+1})")
            time.sleep(3 + attempt * 2)
    return False


def main(argv):
    if len(argv) < 2 or argv[1] not in {"download", "meta"}:
        print(__doc__)
        return 2
    cmd = argv[1]
    ids = [normalize_id(x) for x in argv[2:]]
    if not ids:
        print("no arxiv IDs given")
        return 2

    metas = []
    failed = []
    for i, aid in enumerate(ids):
        print(f"[{i+1}/{len(ids)}] {aid} ...")
        meta = query_meta(aid)
        time.sleep(SLEEP_BETWEEN_REQUESTS)
        if cmd == "meta":
            if meta:
                metas.append(meta)
            else:
                failed.append(aid)
            continue
        ok = download_pdf(aid)
        time.sleep(SLEEP_BETWEEN_REQUESTS)
        if ok:
            if meta:
                metas.append(meta)
            print(f"  ok {aid} ({(OUTPUT_DIR / (aid + '.pdf')).stat().st_size // 1024} KB)")
        else:
            failed.append(aid)
            print(f"  FAILED {aid}")

    # Emit a small index sidecar
    if metas:
        import json
        idx_path = OUTPUT_DIR / "_index.json"
        existing = []
        if idx_path.exists():
            try:
                existing = json.loads(idx_path.read_text())
            except Exception:
                existing = []
        # merge by id
        by_id = {x["id"]: x for x in existing}
        for m in metas:
            by_id[m["id"]] = m
        ordered = sorted(by_id.values(), key=lambda x: x.get("published", ""), reverse=True)
        idx_path.write_text(json.dumps(ordered, indent=2, ensure_ascii=False))
        print(f"index updated: {idx_path} ({len(ordered)} papers)")

    print(f"\nSUMMARY: {len(ids) - len(failed)}/{len(ids)} succeeded")
    if failed:
        print("FAILED IDs:", " ".join(failed))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
