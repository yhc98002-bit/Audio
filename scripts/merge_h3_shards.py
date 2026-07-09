"""Merge sharded H3 driver outputs into one canonical JSONL + run the verdict.

After ``scripts/phase_b3_credit_unit_comparison.py --shard-index N --shard-total M``
runs are all done, this script:

  1. Concatenates the shard JSONLs in canonical (round-robin-merged) order.
  2. Hard-fails on missing or duplicate prompt_ids vs the formal-set roster.
  3. Writes the merged ``results.jsonl``.
  4. Invokes the H3a verdict pipeline (``run_h3a`` with ``--stub-test merged.jsonl``)
     to produce H3_VERDICT.json + h3_{vocal,instrumental}_stratum.json +
     h3_combined.json.

Usage:
  python scripts/merge_h3_shards.py \
      --config configs/runs/phase_b3_credit_unit_comparison.yaml \
      --shard-dir runs/phase_b3_credit_unit/h3_held_out \
      --shard-glob 'results_shard*of*.jsonl' \
      --prompts-mode held_out \
      --pi-approved-launch
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, "scripts")
import phase_b3_credit_unit_comparison as h3  # noqa: E402


def load_expected_prompt_ids(run_cfg: dict, prompts_mode: str) -> list[str]:
    prompts_cfg = run_cfg["prompts"]
    if prompts_mode == "dev":
        block = prompts_cfg.get("h3a_dev", prompts_cfg.get("dev", prompts_cfg))
        with open(block["formal_prompt_ids_json"]) as f:
            return json.load(f)["formal_prompt_ids"]
    elif prompts_mode == "held_out":
        block = prompts_cfg.get("held_out_256", prompts_cfg.get("held_out", {}))
        path = block.get("source", "configs/prompts/held_out.jsonl")
        ids = []
        with open(path) as f:
            for line in f:
                d = json.loads(line)
                ids.append(d["prompt_id"])
        return ids
    raise ValueError(f"unknown prompts_mode: {prompts_mode!r}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--shard-dir", required=True)
    ap.add_argument("--shard-glob", default="results_shard*of*.jsonl")
    ap.add_argument("--prompts-mode", choices=["dev", "held_out"], default="dev")
    ap.add_argument("--pi-approved-launch", action="store_true",
                    help="REQUIRED to compute the verdict on the merged data.")
    ap.add_argument("--merged-name", default="results.jsonl",
                    help="Filename for the merged JSONL (default 'results.jsonl').")
    args = ap.parse_args()

    shard_dir = Path(args.shard_dir)
    shard_files = sorted(shard_dir.glob(args.shard_glob))
    if not shard_files:
        print(f"[merge] ERROR: no shard files matching {args.shard_glob} in {shard_dir}",
              file=sys.stderr)
        return 2
    print(f"[merge] found {len(shard_files)} shard files:", flush=True)
    for f in shard_files:
        print(f"  - {f.name} ({f.stat().st_size} bytes)", flush=True)

    # Load records from all shards.
    records: dict[str, dict] = {}
    for f in shard_files:
        with open(f) as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                pid = rec["prompt_id"]
                if pid in records:
                    print(f"[merge] FAIL: duplicate prompt_id={pid} (in two shards). "
                          f"Refusing to silently overwrite.", file=sys.stderr)
                    return 2
                records[pid] = rec
    print(f"[merge] collected {len(records)} unique prompt_ids", flush=True)

    # Validate against expected formal set.
    cfg = h3.load_yaml(Path(args.config))
    expected_ids = load_expected_prompt_ids(cfg, args.prompts_mode)
    expected_set = set(expected_ids)
    got_set = set(records.keys())
    missing = expected_set - got_set
    extra = got_set - expected_set
    if missing:
        print(f"[merge] FAIL: {len(missing)} expected prompt_ids missing from shards: "
              f"{sorted(missing)[:5]}...", file=sys.stderr)
        return 2
    if extra:
        print(f"[merge] FAIL: {len(extra)} unexpected prompt_ids in shards: "
              f"{sorted(extra)[:5]}...", file=sys.stderr)
        return 2
    print(f"[merge] all {len(expected_ids)} expected prompt_ids present, no extras. ✓",
          flush=True)

    # Write merged JSONL in canonical (expected_ids) order.
    merged_path = shard_dir / args.merged_name
    with open(merged_path, "w") as fh:
        for pid in expected_ids:
            fh.write(json.dumps(records[pid]) + "\n")
    print(f"[merge] wrote merged {merged_path} with {len(expected_ids)} records",
          flush=True)

    # Compute verdict via run_h3a in stub-test mode (fixture = the merged JSONL).
    rc = h3.run_h3a(
        run_cfg_path=Path(args.config),
        out_dir=shard_dir,
        pi_approved_launch_cli=args.pi_approved_launch,
        stub_test_fixture=merged_path,
    )
    if rc != 0:
        print(f"[merge] verdict computation FAILED rc={rc}", file=sys.stderr)
        return rc
    print(f"[merge] DONE. Outputs in {shard_dir}/", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
