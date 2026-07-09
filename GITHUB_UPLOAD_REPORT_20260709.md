# GitHub Upload Report - 2026-07-09

## Summary

The AudioDiffusion workspace was initialized as a Git repository and uploaded to:

`https://github.com/yhc98002-bit/Audio.git`

The upload was treated as a source/documentation repository import, not as a raw experiment artifact dump. Large generated outputs, model artifacts, media files, local caches, archives, credentials, and local assistant/tool state were excluded through `.gitignore`.

## Local Repository

- Local path: `/XYFS02/HDD_POOL/paratera_xy/pxy1289/HaocunYe/Research/AudioDiffusion`
- Branch: `main`
- Remote: `origin`
- Remote URL: `https://github.com/yhc98002-bit/Audio.git`

## Commits Pushed

1. `d84970b` - `Initial AudioDiffusion source import`
   - Added the initial tracked project snapshot.
   - Included code, configs, tests, scripts, top-level project docs, lightweight research reports, and publication-prep metadata.
   - Tracked file count after import: 670 files.

2. `9380a74` - `Ignore generated research artifacts`
   - Expanded `.gitignore` for generated figures, checksums, review packets, extracted tar contents, heartbeat scripts, and old generated research trees.

3. `634463e` - `Ignore local run root pointers`
   - Ignored local run-root pointer files such as `*RUN_ROOT.txt`.

Latest verified remote commit before this report was added:

`634463e4ee8f1e022811637a66a509aac06cfa2a`

## Files Included

Included categories:

- Top-level project documentation and planning files.
- `configs/`
- `scripts/`
- `src/`
- `tests/`
- `tools/`, excluding nested local repo `tools/orbit-agent/`.
- `papers/` lightweight metadata and markdown, excluding raw media.
- `refine-logs/`
- selected `batch3/` controller, sanity, and readout files.
- selected lightweight `orbit-research/` and `orbit-research/adsr_phase2_20260604/paper_prep/` reports, CSVs, JSON summaries, and scripts.

## Files Excluded

Excluded categories:

- Raw audio/media: `*.wav`, `*.flac`, `*.mp3`, `*.mp4`, etc.
- Generated figures and binary media: `*.png`, `*.jpg`, `*.pdf`, etc.
- Model/checkpoint artifacts: `*.pt`, `*.pth`, `*.ckpt`, `*.safetensors`, `*.onnx`, etc.
- Numeric/binary caches: `*.npy`, `*.npz`, `*.h5`, `*.parquet`, etc.
- Archives: `*.tar`, `*.tar.gz`, `*.zip`, etc.
- Logs and JSONL ledgers: `*.log`, `*.jsonl`.
- Credentials and secret-bearing files:
  - `CLAUDE.md`
  - `**/CLAUDE.md`
  - `.dashscope_key`
  - `.env`
  - files matching secret/credential patterns
- Local assistant/tool state:
  - `.claude/`
  - `.codex/`
  - `.aris/`
- Absolute symlink `paper_prep`, because it points to a local machine-specific path.
- Large generated research artifact trees and review packets.

## Safety Checks Performed

- Confirmed the directory was not already a Git repository before initialization.
- Created `.gitignore` before staging.
- Confirmed GitHub CLI authentication for account `yhc98002-bit`.
- Scanned for obvious credential-token patterns in staged files before committing.
- Checked staged payload size before commit:
  - staged files: 670
  - staged bytes before commit: about 12.8 MB
- Removed nested Git repository `tools/orbit-agent` from the index to avoid a broken gitlink.
- Verified no raw audio/model/archive/log/jsonl files were staged.
- Verified remote `refs/heads/main` matched local `HEAD` after push.

## Verification

Final verification before this report:

```bash
git rev-parse HEAD
git ls-remote origin refs/heads/main
git status --short --branch
```

Observed state:

- local `HEAD`: `634463e4ee8f1e022811637a66a509aac06cfa2a`
- remote `main`: `634463e4ee8f1e022811637a66a509aac06cfa2a`
- local branch: `main`
- upstream: `origin/main`
- tracked files: 670
- loose object size: about 43.68 MiB

## Data Handling

No research evidence was deleted. Large/generated/local-risk files were kept on disk and excluded from Git. This preserves the local artifact store while making the GitHub repository portable and safer to share.

## Current Status

The GitHub upload is complete. This report was created afterward to satisfy the requested markdown progress report.

