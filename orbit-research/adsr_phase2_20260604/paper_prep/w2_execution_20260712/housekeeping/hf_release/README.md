# ADSR Release Staging

This directory prepares an anonymous Hugging Face dataset/demo upload. Upload is
deferred until the W2 gates are resolved and a human has reviewed the exact
manifest, account destination, license, secret scan, and claim wording.

Required environment variables at upload time are `HF_TOKEN` and `HF_REPO_ID`.
The token must never be written into this repository. Run `build_upload_manifest.py`
first, inspect `UPLOAD_MANIFEST.csv`, then run `upload_to_hf.py --execute` only
after the post-gate human release decision.
