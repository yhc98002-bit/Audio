#!/usr/bin/env python3
"""Build the blinded 20-pair PI spot check for the W2 factorial."""

from __future__ import annotations

import csv
import hashlib
import hmac
import json
import os
import shutil
import sys
from pathlib import Path


def find_repo_root(start: Path) -> Path:
    for candidate in (start, *start.parents):
        if (candidate / "src/mprm").is_dir() and (candidate / "orbit-research").is_dir():
            return candidate
    raise RuntimeError(f"could not locate repository root from {start}")


ROOT = find_repo_root(Path(__file__).resolve())
sys.path.insert(0, str(ROOT / "paper_prep/scripts"))
from build_rater_bundles_20260711 import QUALITY_WORDING, make_zip, render_html  # noqa: E402

PAPER = ROOT / "paper_prep"
FACTORIAL = PAPER / "w2_execution_20260712/factorial"
INPUT = FACTORIAL / "FACTORIAL_PI_SPOTCHECK_MANIFEST.csv"
PROMPTS = FACTORIAL / "FACTORIAL_PROMPTS.jsonl"
BUNDLE = FACTORIAL / "pi_spotcheck_bundle"
ADMIN = FACTORIAL / "admin_keys/FACTORIAL_PI_SPOTCHECK_ADMIN.csv"
ZIP_PATH = FACTORIAL / "FACTORIAL_PI_SPOTCHECK_BUNDLE.zip"
SHA_PATH = FACTORIAL / "FACTORIAL_PI_SPOTCHECK_SHA256SUMS"
SEED = 20260712


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def read_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def opaque(nonce: str, value: str, purpose: str) -> str:
    return hmac.new(nonce.encode(), f"{SEED}|{purpose}|{value}".encode(), hashlib.sha256).hexdigest()


def link(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(source, destination)
    except OSError:
        shutil.copy2(source, destination)


def build(nonce: str) -> dict:
    if not nonce:
        raise ValueError("ADSR_BLINDING_NONCE is required")
    if BUNDLE.exists() or ADMIN.exists() or ZIP_PATH.exists():
        raise FileExistsError("factorial spot-check output exists; refusing overwrite")
    rows = read_csv(INPUT)
    if len(rows) != 20 or len({row["pair_id"] for row in rows}) != 20:
        raise ValueError("factorial spot-check manifest must contain 20 unique pairs")
    prompts = {row["prompt_id"]: row for row in read_jsonl(PROMPTS)}
    ordered = sorted(rows, key=lambda row: opaque(nonce, row["pair_id"], "shuffle"))
    BUNDLE.mkdir(parents=True)
    (BUNDLE / "media").mkdir()
    public = []
    admin = []
    for position, row in enumerate(ordered, start=1):
        rating_id = "r_" + opaque(nonce, row["pair_id"], "rating_id")[:20]
        swap = int(opaque(nonce, row["pair_id"], "ab_order"), 16) % 2 == 1
        baseline = ROOT / row["baseline_path"]
        comparison = ROOT / row["comparison_path"]
        if not baseline.is_file() or not comparison.is_file():
            raise FileNotFoundError(f"pair media missing for {row['pair_id']}")
        arm_a, arm_b = ("comparison", "baseline") if swap else ("baseline", "comparison")
        source_a, source_b = (comparison, baseline) if swap else (baseline, comparison)
        suffix_a, suffix_b = source_a.suffix.lower(), source_b.suffix.lower()
        destination_a = BUNDLE / "media" / f"audio_{rating_id}_A{suffix_a}"
        destination_b = BUNDLE / "media" / f"audio_{rating_id}_B{suffix_b}"
        link(source_a, destination_a)
        link(source_b, destination_b)
        prompt = prompts[row["prompt_id"]]
        public.append(
            {
                "rating_id": rating_id,
                "media_a": f"media/{destination_a.name}",
                "media_b": f"media/{destination_b.name}",
                "prompt_text": prompt["text"],
                "request_mode": "instrumental",
            }
        )
        admin.append(
            {
                "rating_id": rating_id,
                "pair_id": row["pair_id"],
                "prompt_id": row["prompt_id"],
                "seed_idx": row["seed_idx"],
                "baseline_path": row["baseline_path"],
                "comparison_path": row["comparison_path"],
                "comparison_condition": row["comparison_condition"],
                "arm_a": arm_a,
                "arm_b": arm_b,
                "media_a_sha256": digest(destination_a),
                "media_b_sha256": digest(destination_b),
                "position": position,
                "shuffle_seed": SEED,
                "nonce_sha256": hashlib.sha256(nonce.encode()).hexdigest(),
                "analysis_role": "PI_SPOTCHECK_NOT_PROMOTION_GATE",
            }
        )
    payload = {
        "bundle_id": "w2_factorial_pi_spotcheck",
        "title": "W2 instrumental-factorial PI spot check",
        "mode": "pair_staged",
        "wording_html": f"<p><strong>Quality:</strong> {QUALITY_WORDING}</p>",
        "rows": public,
    }
    html = render_html("W2 instrumental-factorial PI spot check", payload)
    html = html.replace(
        'return /^(pi:[A-Za-z][A-Za-z0-9 ._-]{0,63}|human:CXY)$/.test(v)',
        'return v==="pi:Richard"',
    ).replace(
        "Enter one approved source once: <code>pi:&lt;name&gt;</code> or <code>human:CXY</code>.",
        "This bundle accepts only <code>pi:Richard</code>.",
    ).replace(
        "Use pi:&lt;name&gt; or human:CXY exactly.",
        "Use pi:Richard exactly.",
    )
    (BUNDLE / "index.html").write_text(html, encoding="utf-8")
    (BUNDLE / "README").write_text(
        "W2 factorial: 20 blinded baseline-versus-apparent-best pairs for a later PI spot check.\n"
        "Rate quality blind, reveal the instrumental request, then rate constraint and overall preference.\n"
        "This package is descriptive and cannot promote the corrected instrument or change PLAN.md.\n",
        encoding="utf-8",
    )
    write_csv(ADMIN, admin)
    make_zip(BUNDLE, ZIP_PATH)
    SHA_PATH.write_text(f"{digest(ZIP_PATH)}  {ZIP_PATH.resolve()}\n", encoding="utf-8")
    return {
        "status": "PASS",
        "pairs": len(public),
        "media_files": len(list((BUNDLE / "media").iterdir())),
        "zip_sha256": digest(ZIP_PATH),
        "rating_source": "pi:Richard",
    }


def audit() -> dict:
    html = (BUNDLE / "index.html").read_text(encoding="utf-8")
    admin = read_csv(ADMIN)
    if len(admin) != 20 or len(list((BUNDLE / "media").iterdir())) != 40:
        raise ValueError("factorial spot-check cardinality mismatch")
    for token in ("expected_label", '"bucket"', '"arm"', '"set_name"'):
        if token in html.lower():
            raise ValueError(f"factorial spot-check leak: {token}")
    if "pair_staged" not in html or 'return v==="pi:Richard"' not in html:
        raise ValueError("factorial spot-check reveal/source controls missing")
    if digest(ZIP_PATH) not in SHA_PATH.read_text(encoding="utf-8"):
        raise ValueError("factorial spot-check checksum mismatch")
    return {"status": "PASS", "pairs": 20, "media_files": 40, "leak_test": "PASS"}


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["build", "audit"])
    args = parser.parse_args()
    result = build(os.environ.get("ADSR_BLINDING_NONCE", "")) if args.command == "build" else audit()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
