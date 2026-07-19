# V15 Checkpoint-State Contract

STATE_CONTRACT_STATUS = FAIL

Two diagnostic step-20 states were retained. They include latent, scheduler/timestep/sigma state, native decoder cache, model-output state, APG momentum, conditioning payload, prompt/root seed, Python/NumPy/torch RNG state, dtype/shape, and model/runtime hashes.

The seed-17 state file is `/XYFS02/HDD_POOL/paratera_xy/pxy1289/HaocunYe/Research/AudioDiffusion_v15_gate0_20260717/orbit-research/adsr_phase2_20260604/paper_prep/rescue_v15_gate0_20260717/artifacts/run_20260717/states/cal_v15g0_p00_seed2072000017/step_20.pt` with SHA-256 `f32241bf9d0a136d4a7595e5b9b21af0aab76c6ba838d42a93e25fa89af128e6`. Its latent and cache hashes were recorded at capture. Separate-process continuation was invoked, but the native API rejected the list-valued timestep suffix before any transformer forward call. Therefore restartability, exact continuation, and 64/64 equivalence are not established.

No threshold was relaxed and no failed state was overwritten.
