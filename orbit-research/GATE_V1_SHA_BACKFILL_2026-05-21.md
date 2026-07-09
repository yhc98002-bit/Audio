# gate_v1 Provenance Backfill — 2026-05-21 (Paratera A800, audit-round)

> **Purpose.** Record the **actual local cached** reward-harness model paths, file
> hashes, file mtimes, installed package versions, and HF/Git revision SHAs that
> were used at M1a + R050 runtime on the Paratera box. This file is **the
> companion** to `configs/eval/gate_v1.yaml` for provenance — NOT a substitute,
> and **NOT** appended into `gate_v1.yaml` itself (`gate_v1.yaml` stays FROZEN
> per project policy).
>
> **Scope.** Records what is on disk **now**. The M1a runtime that produced the
> R050 / M1a results loaded these same files, but no per-run sidecar captured
> these SHAs at the time. Per PI directive 2026-05-21: **do NOT use "HF latest
> main" as binding provenance for past runs.** What is captured here is the
> *current best evidence of what M1a actually used* on this filesystem; it is
> not a backdated pre-registration.
>
> **Authority.** PI directive 2026-05-21 ("Provenance / SHA handling" §7 of the
> Phase-B pre-kickoff patch). Future `gate_v2.yaml` activation should consume
> these values (or freshly re-verified equivalents) into the `sha_pinned` block,
> not just point at `revision: main`.

---

## 1. Environment snapshot (Paratera, an12, 2026-05-21)

| Item | Value |
|---|---|
| OS | Linux 5.15.0-78-th-an (Paratera Ubuntu derivative) |
| GPU | 8× NVIDIA A800 80GB PCIe (640 GB total VRAM) |
| Driver | 535.104.12 |
| CUDA | 12.1 (via PyTorch wheel) |
| Conda env | `audio-prm` at `/HOME/paratera_xy/pxy1289/.conda/envs/audio-prm` |
| Python | 3.10 (anaconda3/2023.09 base) |

### 1.1 Installed package versions (verified via `pip show` 2026-05-21)

| Package | Version | Notes |
|---|---|---|
| `torch` | 2.5.1+cu121 | Pinned per pyproject |
| `torchaudio` | 2.5.1 | Pinned alongside torch |
| `numpy` | 1.26.4 | Pinned `<2` for `laion_clap` ABI compatibility |
| `transformers` | 4.50.0 | Downgraded by `acestep` install |
| `diffusers` | 0.38.0 | — |
| `accelerate` | 1.6.0 | — |
| `peft` | 0.19.1 | — |
| `laion_clap` | 1.1.7 | No `__version__` attribute exposed; reported by `pip show` |
| `audiobox_aesthetics` | 0.0.4 | No `__version__` attribute exposed |
| `openai-whisper` | 20250625 (date-coded release) | — |
| `demucs` | 4.0.1 | `htdemucs` provided |
| `acestep` | 0.2.0 | Editable install from local clone (PyPI 0.1.0 setup.py broken) |
| `wandb` | 0.27.0 | — |
| `stable_audio_tools` | NOT INSTALLED | `pypesq` transitive dep broken under numpy>=1.26; SAO audit-only, deferred |

## 2. Local cached weights — paths, sizes, hashes, mtimes

### 2.1 CLAP (laion/clap-htsat-fused via `laion_clap.CLAP_Module`)

| Field | Value |
|---|---|
| Checkpoint path | `/HOME/paratera_xy/pxy1289/.cache/clap/630k-audioset-best.pt` |
| File size | 1,863,587,645 bytes (≈1.74 GiB) |
| File mtime | 2026-05-19 14:53:00 UTC+8 |
| SHA-256 | `8053c9775516af2f4902e1e8281e356cc1bf7a85e8b761908170767b77c3f037` |
| HF repo (reference) | `laion/clap-htsat-fused` |
| HF commit_sha | TODO_PI_VERIFY — auto-download via `laion_clap` from `https://huggingface.co/lukewys/laion_clap/resolve/main/630k-audioset-best.pt` was via `hf-mirror.com` proxy; the checkpoint file itself is not from a git-rev'd HF repo (it is published as a release asset). Provenance is the **file SHA-256 above**, not an HF commit SHA. |

### 2.2 CLAP text-side tokenizers (BERT / RoBERTa / BART)

The `laion_clap` text branch loads three HF-hosted tokenizers at runtime via
`HF_HUB_OFFLINE=1` lookups against the local cache. Both the HF cache copy and
the `~/HDD_POOL/source/laion_clap_tokenizers/...` re-staged copy are present.

| Repo | HF cache revision (current `main` snapshot) | Local re-staged path |
|---|---|---|
| `bert-base-uncased` | `86b5e0934494bd15c9632b12f734a8a67f723594` | `~/HDD_POOL/source/laion_clap_tokenizers/bert-base-uncased` |
| `roberta-base` | `e2da8e2f811d1448a5b465c236feacd80ffbac7b` | `~/HDD_POOL/source/laion_clap_tokenizers/roberta-base` |
| `facebook/bart-base` | `aadd2ab0ae0c8268c7c9693540e9904811f36177` | `~/HDD_POOL/source/laion_clap_tokenizers/facebook--bart-base` |

These three SHAs are the revisions present in `~/.cache/huggingface/hub/models--*/refs/main` at audit time. They are **not** independently re-verified against upstream HF on this run; per PI directive, they should be treated as "the SHA M1a actually loaded" rather than "the SHA we hand-picked for the experiment."

### 2.3 Audiobox-aesthetics (`facebook/audiobox-aesthetics`)

| Field | Value |
|---|---|
| Checkpoint path | `/HOME/paratera_xy/pxy1289/HDD_POOL/source/audiobox_aesthetics/checkpoint.pt` |
| File size | 415,520,834 bytes (≈396 MiB) |
| File mtime | 2026-05-19 14:46:08 UTC+8 |
| SHA-256 | `a4931a7a01c3e6733352e9d85371835f03bf9135f8b31e1583c23538811d4a32` |
| HF repo (reference) | `facebook/audiobox-aesthetics` |
| HF commit_sha | TODO_PI_VERIFY |
| Filename note | gate_v2.yaml.draft references `audiobox_aesthetics_v1.pth` but the actual local filename is `checkpoint.pt`. PI to decide whether to rename the file or update the draft to match — the file-SHA above is the binding identifier. |

### 2.4 MERT (m-a-p)

| Field | Value |
|---|---|
| Local path | `/HOME/paratera_xy/pxy1289/HDD_POOL/source/mert/MERT-v1-95M` |
| Variant present locally | **MERT-v1-95M** (the 95M-param model) |
| Variant referenced in gate_v2.yaml.draft | `m-a-p/MERT-v1-330M` (the 330M-param model) — **mismatch** |
| Weight file | `MERT-v1-95M/pytorch_model.bin` |
| File size | 377,552,987 bytes (≈360 MiB) |
| File mtime | 2026-05-19 14:45:33 UTC+8 |
| SHA-256 | `a2b8b747f72c06e0595aeae41ae5473f4364938c6b39b2c58be38c48e6bd3fcd` |
| HF commit_sha | TODO_PI_VERIFY (no `.huggingface/refs` for this dir — it was pre-staged via `tools/predownload_reward_weights.sh`, not via `huggingface_hub.snapshot_download`) |
| **Open PI decision** | Either (a) rebuild gate_v2 to bind to MERT-v1-95M (the variant actually pre-staged + used at M1a per `tools/predownload_reward_weights.sh` and `CLAUDE.md`'s "MERT-v1-95M" line), OR (b) re-download MERT-v1-330M and rerun. (a) is consistent with the M1a + R050 evidence on disk; (b) would invalidate the historical comparison. |

### 2.5 ACE-Step v1 (3.5B) — generator backbone

| Field | Value |
|---|---|
| ModelScope cache path | `/HOME/paratera_xy/pxy1289/.cache/modelscope/hub/models/ACE-Step/ACE-Step-v1-3___5B/` (symlink alias `ACE-Step-v1-3.5B`) |
| Source clone path | `/HOME/paratera_xy/pxy1289/HDD_POOL/source/ACE-Step` (editable pip install) |
| Source git commit | `1bee4c9f5b43e30995f8d4d33b3919197ce1bd68` (`1bee4c9`, 2026-02-15) |
| Sub-modules present | `ace_step_transformer/` (6.61 GB), `music_dcae_f8c8/` (313 MB), `music_vocoder/`, `umt5-base/` |
| Weight format | `diffusion_pytorch_model.safetensors` (per sub-module) |
| HF / ModelScope revision | TODO_PI_VERIFY (auto-downloaded via ModelScope on 2026-05-17; no explicit revision pin on file) |

### 2.6 Whisper (large-v3) + Demucs (htdemucs)

| Component | Source | Status |
|---|---|---|
| `openai-whisper` 20250625 | PyPI wheel | Models lazy-downloaded into `~/.cache/whisper/`; large-v3 download URL is fixed per release. SHA inventory not yet captured (large-v3 is ~3 GB; defer hashing until first use). |
| `demucs` 4.0.1 (htdemucs) | PyPI wheel + auto-download | Bundled checkpoint downloaded on first use. SHA inventory not yet captured. |

## 3. What this note does NOT do (per PI directive)

- **Does NOT** append SHA pins into `configs/eval/gate_v1.yaml`. `gate_v1.yaml` stays
  byte-identical to its M1a/R050 form.
- **Does NOT** claim "HF latest main" was the binding revision for past runs. The
  binding evidence is **the file SHA-256 + mtime + size** captured above, plus the
  cached HF refs that were on disk at audit time.
- **Does NOT** backdate any pre-registration. The audit-round M1a + R050 ran
  before this note was written; the note records on-disk state, not retroactive
  pre-registration.
- **Does NOT** activate `gate_v2.yaml` — the draft remains a draft pending PI
  decision on (a) the MERT-95M vs 330M divergence, (b) the audiobox filename
  mismatch, (c) explicit commit_sha resolution for the four `TODO_PI_VERIFY`
  slots.

## 4. PI decisions surfaced by this audit

1. **MERT variant.** gate_v2.yaml.draft says `MERT-v1-330M`; local cache has
   `MERT-v1-95M`. Pick one. Recommendation: bind to **MERT-v1-95M** (matches
   M1a/R050 evidence) unless PI wants the 330M model and is willing to re-run
   any past results that depended on the 95M model.
2. **Audiobox filename.** gate_v2.yaml.draft references `audiobox_aesthetics_v1.pth`;
   local file is `checkpoint.pt`. Either update the draft to match the actual
   filename, or rename the file. The file-SHA is binding regardless.
3. **HF/ModelScope commit_sha resolution.** For each `TODO_PI_VERIFY` slot in
   `gate_v2.yaml.draft.sha_pinned.models`, the choice is: (a) pin to the
   currently-cached HF revision SHA (recorded in this file at §2 for the
   tokenizers; TODO for the others), OR (b) re-download from `revision: <X>`
   and re-stamp. (a) preserves M1a/R050 comparability; (b) requires a re-run.
4. **Whisper large-v3 + Demucs hashing.** Defer to first use (current cache may
   be empty if Phase A only exercised CLAP + Audiobox + MERT). Capture file
   SHAs at Phase B kickoff before any reward-model sidecar is stamped against
   `gate_v2`.

## 5. Status

| Field | Value |
|---|---|
| `gate_v1.yaml` integrity | UNCHANGED (FROZEN per project policy) |
| `gate_v2.yaml.draft` status | DRAFT — NOT activated |
| `audio-prm` env integrity | OK (verified via D0 + ACE-Step adapter smoke 2026-05-19) |
| Reward-weight inventory completeness | PARTIAL — CLAP + Audiobox + MERT-95M + ACE-Step verified; Whisper + Demucs deferred |
| Open PI decisions | 4 (see §4) |
