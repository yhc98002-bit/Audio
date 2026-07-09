# ADSR Compute Accounting

Project-standard step model: σ0.9=7, σ0.8=12, σ0.7=16, FULL=30 steps.
σ0.7-decision policies: all 8 candidates reach σ0.7 (8×16=128 steps), then K continue to final (K×14). For K=4: (128+56)/240 = **0.767** compute. BoN-4 = 0.5, Full BoN-8 = 1.0.

{
  "full_bon8": 1.0,
  "bon4_random": 0.5,
  "random_keep4": 0.7667,
  "common_restart": 0.7667,
  "evpd_only": 0.7667,
  "adsr_evpd": 0.7667,
  "adsr_evpd_select": 0.7667,
  "adsr_evpd_lyric_defer": 0.7667
}

Limitation: fixed-pool 'restart' = choosing which pre-generated candidates continue; true online restart would draw fresh seeds. Compute matched within the σ0.7-decision family.