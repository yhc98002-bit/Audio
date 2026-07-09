"""D3a — Tweedie code-level derivation helper (STOP-B-4 pre-M1a check).

Locates the installed ACE-Step package, prints the source of the flow head + sampler step +
encoder/decoder + scaling helpers, and writes a STUB at
`orbit-research/TWEEDIE_DERIVATION_NOTE.md` if it does not exist. The human (or next-bridge)
fills in the four required slots and updates `STATUS: TBD` → `STATUS: RESOLVED`.

D3a is a hard gate on Phase B / M2 (not on M1a). `scripts/d3_tweedie_sanity.py` refuses to
run in production mode unless this note's STATUS is RESOLVED.
"""
from __future__ import annotations

import argparse
import importlib
import inspect
import re
import subprocess
import sys
from pathlib import Path


DERIVATION_NOTE = Path("orbit-research/TWEEDIE_DERIVATION_NOTE.md")
# STOP-B-8: upstream installs as `acestep` (no underscore); earlier mprm code assumed
# `ace_step` / `ace_step_v15` which never match. We try `acestep` first now. Pattern
# list also extended for v1's class name `ACEStepPipeline` and DCAE (DCAE = the
# music latent autoencoder; relevant to the "decode" / "encode" / "scaling" buckets).
TARGETS_PER_MODULE = {
    "acestep": [
        "ACEStepPipeline", "AceStepPipeline", "flow_head", "predict_velocity", "tweedie",
        "sampler", "scheduler", "step", "encode", "decode",
        "scaling_factor", "latent_scale", "dcae", "music_dcae",
        "ACEStepTransformer2DModel",
    ],
    "ace_step": [
        # legacy / fallback (some forks install under this name)
        "AceStepPipeline", "ACEStepPipeline", "flow_head", "predict_velocity", "tweedie",
        "sampler", "scheduler", "step", "encode", "decode",
        "scaling_factor", "latent_scale",
    ],
    "ace_step_v15": [
        # legacy / fallback
        "AceStepPipeline", "flow_head", "predict_velocity", "tweedie",
        "sampler", "scheduler", "step", "encode", "decode",
        "scaling_factor", "latent_scale",
    ],
}


def _find_ace_step_source() -> tuple[str, Path | None]:
    for mod_name in TARGETS_PER_MODULE:
        try:
            mod = importlib.import_module(mod_name)
        except Exception:
            continue
        path = Path(getattr(mod, "__file__", "") or "")
        if path.exists():
            return mod_name, path.parent
    return "acestep / ace_step (NOT installed)", None


def _print_relevant_source(mod_name: str, source_dir: Path) -> dict[str, list[str]]:
    """Walk source_dir, locate functions matching the target patterns, print their source."""
    findings: dict[str, list[str]] = {}
    targets = TARGETS_PER_MODULE.get(mod_name, [])
    py_files = sorted(source_dir.rglob("*.py"))
    if not py_files:
        return findings
    for path in py_files:
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            continue
        for target in targets:
            pat = re.compile(r"^\s*(class|def)\s+\w*" + re.escape(target) + r"\w*", re.IGNORECASE | re.MULTILINE)
            for m in pat.finditer(text):
                lineno = text.count("\n", 0, m.start()) + 1
                findings.setdefault(target, []).append(
                    f"{path.relative_to(source_dir.parent)}:{lineno}: {m.group(0).strip()}"
                )
    return findings


def _git_sha(path: Path) -> str | None:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=str(path), stderr=subprocess.DEVNULL
        )
        return out.decode().strip()
    except Exception:
        return None


def _read_status(note_path: Path) -> str:
    if not note_path.exists():
        return "MISSING"
    text = note_path.read_text(encoding="utf-8")
    m = re.search(r"^STATUS:\s*(RESOLVED|AMBIGUOUS|TBD)\s*$", text, re.MULTILINE)
    return m.group(1) if m else "UNKNOWN"


def _write_findings(note_path: Path, findings: dict[str, list[str]], mod_name: str,
                     source_dir: Path | None, sha: str | None) -> None:
    """Append a `## D3a auto-found references` section if not already present."""
    text = note_path.read_text(encoding="utf-8") if note_path.exists() else ""
    if "## D3a auto-found references" in text:
        return  # do not overwrite
    block = ["", "---", "", "## D3a auto-found references (do not edit by hand; rerun the script to refresh)",
              "", f"- Module: `{mod_name}`",
              f"- Source dir: `{source_dir if source_dir else 'NOT FOUND'}`",
              f"- Git SHA: `{sha if sha else 'UNAVAILABLE'}`",
              "",
              "Pattern matches in source (use these as starting points for §2 + §3 + §4 + §5):",
              ""]
    for target in sorted(findings.keys()):
        block.append(f"### `{target}` matches")
        block.append("")
        for ref in findings[target][:10]:
            block.append(f"- {ref}")
        if len(findings[target]) > 10:
            block.append(f"- ... ({len(findings[target]) - 10} more)")
        block.append("")
    note_path.write_text(text.rstrip() + "\n" + "\n".join(block) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--note-path", default=str(DERIVATION_NOTE))
    parser.add_argument("--require-resolved", action="store_true",
                        help="Exit non-zero unless STATUS: RESOLVED (used by launch_phase_a.sh)")
    args = parser.parse_args()
    note_path = Path(args.note_path)

    mod_name, source_dir = _find_ace_step_source()
    print(f"D3a: ACE-Step module = {mod_name}")
    if source_dir is None:
        print("D3a WARN: ACE-Step is NOT installed. Install per README.md before D3a can resolve.")

    sha = _git_sha(source_dir) if source_dir else None
    if sha is not None:
        print(f"D3a: git SHA = {sha}")

    findings: dict[str, list[str]] = {}
    if source_dir is not None:
        findings = _print_relevant_source(mod_name, source_dir)
        for target in sorted(findings.keys()):
            print(f"  - {target}: {len(findings[target])} match(es)")
            for ref in findings[target][:3]:
                print(f"    {ref}")
        _write_findings(note_path, findings, mod_name, source_dir, sha)

    status = _read_status(note_path)
    print(f"\nD3a derivation note: {note_path}  STATUS: {status}")

    if status == "MISSING":
        print("D3a ERROR: derivation note does not exist; rerun this script to generate it.")
        return 2
    if status == "TBD":
        print("D3a INFO: derivation note has TBD slots. Human must fill in:")
        print("  §2 flow target / §3 time convention / §4 latent scaling / §5 clean-target formula")
        print("  Then set STATUS: RESOLVED at the bottom of the note.")
    if status == "AMBIGUOUS":
        print("D3a INFO: STATUS=AMBIGUOUS. Run `d3_tweedie_sanity.py --candidate-formula <name>`")
        print("  for each candidate in §6 and pick the winner. Then set STATUS: RESOLVED.")
    if status == "RESOLVED":
        print("D3a PASS: derivation note is RESOLVED. D3 reconstruction sanity may run in production.")
        print("         Phase B / M2 is unblocked from the Tweedie-formula angle.")

    if args.require_resolved and status != "RESOLVED":
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
