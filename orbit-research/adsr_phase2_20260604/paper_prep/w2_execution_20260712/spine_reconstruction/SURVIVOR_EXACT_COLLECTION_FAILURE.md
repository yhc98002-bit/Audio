# Survivor Exact-Collection Replay Failure

`SURVIVOR_EXACT_COLLECTION_ATTEMPT = FAILED_AFTER_GENERATION_BEFORE_SAVE`

The exact historical `collect_early_tweedie_validation.py` command was replayed
on `an12` GPU 7 for `dev_0000`, candidate 0, seed `2026052700`. ACE-Step loaded
and generated the waveform. The collector then attempted final reward scoring
before copying audio from its temporary file into the output root. CLAP's BART
tokenizer attempted an unavailable Hugging Face request and raised:

`RuntimeError: Cannot send a request, as the client has been closed.`

Evidence:

- command summary: `survivor_exact_collection_replay/run_summary.json`;
- append target: `survivor_exact_collection_replay/candidate_records.jsonl`
  (zero rows because scoring failed before ledger append);
- traceback: `spine_reconstruction/logs/survivor_exact_collection_replay.log`;
- no frozen artifact was changed.

A narrower diagnosis then retained the generated output before reward scoring
under both trajectory-capture and historical reward-initialization paths. Both
produced decoded hash
`53e0de1eb04314a79eaf7420fcb812d74cf6cad75496fb2f57c25c2d9b919886`,
which differs from the June survivor hash
`94602ca8d50bced2b16eaf58d4c7556e8a0a92adf76db8f561503a3349120bbc`.
See `survivor_fidelity_diagnosis/SURVIVOR_FIDELITY_REPORT.md`.

The 4,095 missing-candidate reconstruction proceeds against the separately
audited 50-control exactness cohort. The survivor mismatch remains a hard audit
failure and cannot be silently promoted to PASS.
