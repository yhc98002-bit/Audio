# HUMAN AUDIT REQUEST (async, non-blocking) — rare vocal-miss prompts
Purpose: confirm the lowest-p vocal-miss "failures" are REAL (no vocals), not a Demucs artifact
(PANNs proxy unreliable, so human ears are the independent check). Resolves detector-independence
for the rare-but-recoverable vocal basins (S002).
Candidates (p_hat at N=256): held_out_0199 (3/256), held_out_0254 (6/256), held_out_0024/0045/0240 (7/256).
Packet: a sample of all-failed (Demucs no-vocal) + the rare clean draws per prompt, from
01_core_basin_test/keep/bon256/. To be built into a blinded audit packet next cycle.
