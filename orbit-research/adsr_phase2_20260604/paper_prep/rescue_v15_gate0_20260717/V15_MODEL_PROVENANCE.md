# ACE-Step v1.5 XL-SFT Model Provenance

MODEL_PROVENANCE_STATUS = PASS

- Exact model: `ACE-Step/acestep-v15-xl-sft` / `acestep-v15-xl-sft`; `is_turbo=false`.
- ModelScope revision: `d1ca0bc96e29cd46435219ceb4f8e3a13a8eaf50`.
- Source repository commit: `6d467e4b5081ccb0abf1ec1bf4fdf9051a2d34b0`; archive SHA-256 `fc563d80a60a8c2485161b658bb30d621ef4eff10ca2e7ac9ac411d4cae1ea91`.
- Four XL-SFT weight shards: exact local/API hashes in `V15_MODEL_CHECKSUMS.tsv`.
- VAE weight SHA-256: `da17edb604c40deaf09e9b24974e590d1ca83a374070e5d0884cfa4bed9a99b0`.
- Text encoder: `Qwen/Qwen3-Embedding-0.6B`, weight-file revision `5092237580d1545d466a2d454c09f18181c341ec`, SHA-256 `0437e45c94563b09e13cb7a64478fc406947a93cb34a7e05870fc8dcd48e23fd`. Tokenizer/config hashes are individually frozen in `V15_PROVENANCE.json`.
- Runtime scheduler/model code: source-synced SHA-256 `e0a61a9da2c5e4d38a995417526c595d1bf6ae3820ff376ac7c419331fe63cec`. Acquired ModelScope remote-code SHA-256: `e367811c6d8cd9162e630da86622dd6edc9d5c2b7f605eadd68e69a227c35e88`.
- Sampler: 50 steps, CFG 7.0, shift 1.0, inline Euler ODE, ADG off, DCW off, 15 s at 48 kHz.
- Acquisition occurred on the login node through the approved proxy, ModelScope first. The failed compute-node auto-download path acquired zero bytes.

Evidence: `V15_PROVENANCE.json`, `V15_MODEL_CHECKSUMS.tsv`, `V15_TERMINAL_DIAGNOSIS.json`.
