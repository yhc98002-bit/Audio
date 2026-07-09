# EXPLORATION BACKLOG (ranked cheap probes; soak idle GPUs — §23A)

An empty backlog under free compute is a FAILURE STATE. Pull top item whenever spine isn't using all GPUs.

| rank | probe | question | rough cost | positive means | negative means |
|---|---|---|---|---|---|
| 1 | instrumental dissociation large-N | is instrumental null low-p(action-unavailable) or ceiling/seed-recoverable? | 15 prompts×256 | RQ4 answered; possible reframe | null is just easy/ceiling |
| 2 | basin↔reward-selection link | do low-p basins predict BoN-winner errors? | replay existing ledgers + 256-seed | decomposition has practical teeth | regimes orthogonal to selection |
| 3 | paraphrase robustness on E2 vocal tail | tokenization-bound vs semantic basin? | 5–10 paraphrases×64 | semantic basin candidate | phrasing-bound (still useful) |
| 4 | early-σ feature → final regime | can one trajectory predict regime beyond router features? | reuse early mels | router lead | regime not early-observable |
| 5 | minimal intervention search | smallest edit that escapes a basin | grid on a few basins | learned-intervention motivation | basins need heavy edits |
| 6 | anti-basins | prompts where resampling helps MORE than iid predicts (positive seed corr) | scan p_hat vs BoN curve | new phenomenon | iid holds |
| 7 | break-the-decomposition | find a prompt set where seed-recoverable vs low-p doesn't hold | adversarial prompt search | sharpen/limit thesis | decomposition robust |
| 8 | genre-dependence of instrumental-leak | is the vocal-prior leak rate genre-dependent (PI: hip-hop instrumental → vocals)? | genre-stratified instrumental set × 64–256 seeds | leak rate varies by genre → conditioning target | uniform leak |
