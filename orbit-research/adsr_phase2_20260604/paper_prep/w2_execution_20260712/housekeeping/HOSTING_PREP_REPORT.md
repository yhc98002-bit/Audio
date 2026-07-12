# ADSR Hosting Preparation

`HOSTING_STATUS = PREPARED_UPLOAD_DEFERRED_POST_GATES`

- Static demo: `demo_site/index.html`, with two blinded audio players and two publication figures.
- Dataset card: `hf_release/DATASET_CARD.md`.
- Checksum manifest builder: `hf_release/build_upload_manifest.py`.
- Token-gated upload client: `hf_release/upload_to_hf.py`.
- Target account: human-supplied anonymous Hugging Face account via `HF_REPO_ID`.
- Credential handling: environment-only `HF_TOKEN`; no upload was attempted.

Human action remains mandatory after the gates: verify license, destination,
manifest, secret scan, and paper wording before invoking `--execute`.
