# ADSR Phase-1: Axis x sigma Observability Matrix (cached sigma only)

- Generated: 2026-06-04T15:43:56
- Dataset: `/XYFS02/HDD_POOL/paratera_xy/pxy1289/HaocunYe/Research/AudioDiffusion/orbit-research/trajectory_candidate_dataset.jsonl`
- Records: 4096  |  Prompts: 512  |  Group size: 8 candidates/prompt
- Cached sigma: 0.9, 0.8, 0.7  |  Reference: final

## Evidence honesty / scope

This is **offline analysis on existing cached data**. No ADSR / EVPD / restart real result is being generated here. Observability = within-prompt agreement between an early-sigma scalar reward and the final reward, over the 8 cached candidates per prompt.

**PLANNED / deferred (not in this pool, not fabricated):**
- sigma {0.5, 0.3}: NOT cached here (only 0.9/0.8/0.7/final). Comes from parallel GPU re-collection.
- vocal-presence / type-match axis: no measured labels yet -> PLANNED/deferred.

**Lyric headline rule:** `lyric_intelligibility` is reported ONLY on `vocal_scorable` = (vocal AND language==en), n=282 prompts. Instrumental `final_lyric_intelligibility == 1.0` sentinel and non-EN prompts are excluded from every lyric headline. Other axes report `all` plus per-stratum.

**Stratum prompt counts:** all=512, vocal=316, instrumental=196, vocal_scorable=282

## Heatmap-ready table: within-prompt Spearman (early-sigma vs final)

Headline stratum per axis: `vocal_scorable` for lyric, `all` otherwise.

| axis (stratum) | sigma=0.9 | sigma=0.8 | sigma=0.7 | sigma=0.5 | sigma=0.3 |
|---|---|---|---|---|---|
| common_robust_lcb (all) | 0.2472 | 0.4833 | 0.6524 | PLANNED | PLANNED |
| aesthetic_pq (all) | 0.2813 | 0.5381 | 0.6291 | PLANNED | PLANNED |
| aesthetic_cu (all) | 0.2846 | 0.5117 | 0.6169 | PLANNED | PLANNED |
| semantic_fit (all) | 0.1301 | 0.2044 | 0.3032 | PLANNED | PLANNED |
| lyric_intelligibility (vocal_scorable) | 0.0384 | 0.2497 | 0.5540 | PLANNED | PLANNED |
| section_coherence (all) | 0.3883 | 0.5831 | 0.6860 | PLANNED | PLANNED |

## Full matrix (per axis, per sigma, per stratum)

### common_robust_lcb  *(PRIMARY)*


| sigma | stratum | n_subset | usable_n | Spearman | NDCG@1 | NDCG@2 | NDCG@4 | ret@1 | ret@2 | ret@4 | FN@1 | FN@2 | FN@4 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0.9 | all **<-headline** | 512 | 512 | 0.2472 | 0.6805 | 0.6925 | 0.7299 | 0.2285 | 0.4121 | 0.6660 | 0.7715 | 0.5879 | 0.3340 |
| 0.9 | vocal | 316 | 316 | 0.2403 | 0.6809 | 0.6942 | 0.7293 | 0.2278 | 0.3892 | 0.6424 | 0.7722 | 0.6108 | 0.3576 |
| 0.9 | instrumental | 196 | 196 | 0.2583 | 0.6798 | 0.6897 | 0.7307 | 0.2296 | 0.4490 | 0.7041 | 0.7704 | 0.5510 | 0.2959 |
| 0.9 | vocal_scorable | 282 | 282 | 0.2516 | 0.6910 | 0.6968 | 0.7324 | 0.2447 | 0.4007 | 0.6596 | 0.7553 | 0.5993 | 0.3404 |
| 0.8 | all **<-headline** | 512 | 512 | 0.4833 | 0.7984 | 0.8144 | 0.8256 | 0.3906 | 0.6094 | 0.8242 | 0.6094 | 0.3906 | 0.1758 |
| 0.8 | vocal | 316 | 316 | 0.5103 | 0.8017 | 0.8248 | 0.8342 | 0.3639 | 0.5854 | 0.8165 | 0.6361 | 0.4146 | 0.1835 |
| 0.8 | instrumental | 196 | 196 | 0.4397 | 0.7931 | 0.7977 | 0.8116 | 0.4337 | 0.6480 | 0.8367 | 0.5663 | 0.3520 | 0.1633 |
| 0.8 | vocal_scorable | 282 | 282 | 0.5084 | 0.8006 | 0.8233 | 0.8319 | 0.3759 | 0.5851 | 0.8050 | 0.6241 | 0.4149 | 0.1950 |
| 0.7 | all **<-headline** | 512 | 512 | 0.6524 | 0.8629 | 0.8733 | 0.8921 | 0.4707 | 0.6797 | 0.9102 | 0.5293 | 0.3203 | 0.0898 |
| 0.7 | vocal | 316 | 316 | 0.6832 | 0.8716 | 0.8838 | 0.9024 | 0.4684 | 0.6930 | 0.9209 | 0.5316 | 0.3070 | 0.0791 |
| 0.7 | instrumental | 196 | 196 | 0.6028 | 0.8487 | 0.8563 | 0.8754 | 0.4745 | 0.6582 | 0.8929 | 0.5255 | 0.3418 | 0.1071 |
| 0.7 | vocal_scorable | 282 | 282 | 0.6845 | 0.8689 | 0.8840 | 0.9015 | 0.4645 | 0.7021 | 0.9255 | 0.5355 | 0.2979 | 0.0745 |

### aesthetic_pq


| sigma | stratum | n_subset | usable_n | Spearman | NDCG@1 | NDCG@2 | NDCG@4 | ret@1 | ret@2 | ret@4 | FN@1 | FN@2 | FN@4 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0.9 | all **<-headline** | 512 | 512 | 0.2813 | 0.6938 | 0.7039 | 0.7397 | 0.2461 | 0.4180 | 0.6719 | 0.7539 | 0.5820 | 0.3281 |
| 0.9 | vocal | 316 | 316 | 0.2524 | 0.6703 | 0.6772 | 0.7262 | 0.2310 | 0.3861 | 0.6582 | 0.7690 | 0.6139 | 0.3418 |
| 0.9 | instrumental | 196 | 196 | 0.3279 | 0.7317 | 0.7471 | 0.7615 | 0.2704 | 0.4694 | 0.6939 | 0.7296 | 0.5306 | 0.3061 |
| 0.9 | vocal_scorable | 282 | 282 | 0.2546 | 0.6744 | 0.6793 | 0.7285 | 0.2411 | 0.3936 | 0.6631 | 0.7589 | 0.6064 | 0.3369 |
| 0.8 | all **<-headline** | 512 | 512 | 0.5381 | 0.8082 | 0.8218 | 0.8454 | 0.4199 | 0.6309 | 0.8457 | 0.5801 | 0.3691 | 0.1543 |
| 0.8 | vocal | 316 | 316 | 0.5320 | 0.8002 | 0.8157 | 0.8383 | 0.4146 | 0.6203 | 0.8418 | 0.5854 | 0.3797 | 0.1582 |
| 0.8 | instrumental | 196 | 196 | 0.5479 | 0.8210 | 0.8316 | 0.8568 | 0.4286 | 0.6480 | 0.8520 | 0.5714 | 0.3520 | 0.1480 |
| 0.8 | vocal_scorable | 282 | 282 | 0.5301 | 0.8018 | 0.8128 | 0.8370 | 0.4184 | 0.6206 | 0.8440 | 0.5816 | 0.3794 | 0.1560 |
| 0.7 | all **<-headline** | 512 | 512 | 0.6291 | 0.8585 | 0.8679 | 0.8815 | 0.4902 | 0.6992 | 0.8887 | 0.5098 | 0.3008 | 0.1113 |
| 0.7 | vocal | 316 | 316 | 0.6182 | 0.8459 | 0.8579 | 0.8731 | 0.4557 | 0.6677 | 0.8861 | 0.5443 | 0.3323 | 0.1139 |
| 0.7 | instrumental | 196 | 196 | 0.6467 | 0.8789 | 0.8840 | 0.8949 | 0.5459 | 0.7500 | 0.8929 | 0.4541 | 0.2500 | 0.1071 |
| 0.7 | vocal_scorable | 282 | 282 | 0.6190 | 0.8507 | 0.8604 | 0.8752 | 0.4610 | 0.6738 | 0.8972 | 0.5390 | 0.3262 | 0.1028 |

### aesthetic_cu


| sigma | stratum | n_subset | usable_n | Spearman | NDCG@1 | NDCG@2 | NDCG@4 | ret@1 | ret@2 | ret@4 | FN@1 | FN@2 | FN@4 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0.9 | all **<-headline** | 512 | 512 | 0.2846 | 0.7209 | 0.7248 | 0.7538 | 0.2832 | 0.4473 | 0.7207 | 0.7168 | 0.5527 | 0.2793 |
| 0.9 | vocal | 316 | 316 | 0.2498 | 0.7118 | 0.7083 | 0.7398 | 0.2816 | 0.4335 | 0.7025 | 0.7184 | 0.5665 | 0.2975 |
| 0.9 | instrumental | 196 | 196 | 0.3405 | 0.7355 | 0.7514 | 0.7764 | 0.2857 | 0.4694 | 0.7500 | 0.7143 | 0.5306 | 0.2500 |
| 0.9 | vocal_scorable | 282 | 282 | 0.2551 | 0.7177 | 0.7129 | 0.7423 | 0.2979 | 0.4574 | 0.7163 | 0.7021 | 0.5426 | 0.2837 |
| 0.8 | all **<-headline** | 512 | 512 | 0.5117 | 0.8242 | 0.8306 | 0.8471 | 0.4121 | 0.5957 | 0.8340 | 0.5879 | 0.4043 | 0.1660 |
| 0.8 | vocal | 316 | 316 | 0.5060 | 0.8184 | 0.8231 | 0.8426 | 0.3861 | 0.5665 | 0.8354 | 0.6139 | 0.4335 | 0.1646 |
| 0.8 | instrumental | 196 | 196 | 0.5209 | 0.8336 | 0.8427 | 0.8544 | 0.4541 | 0.6429 | 0.8316 | 0.5459 | 0.3571 | 0.1684 |
| 0.8 | vocal_scorable | 282 | 282 | 0.5014 | 0.8199 | 0.8232 | 0.8408 | 0.4043 | 0.5816 | 0.8227 | 0.5957 | 0.4184 | 0.1773 |
| 0.7 | all **<-headline** | 512 | 512 | 0.6169 | 0.8694 | 0.8701 | 0.8831 | 0.4941 | 0.6523 | 0.8789 | 0.5059 | 0.3477 | 0.1211 |
| 0.7 | vocal | 316 | 316 | 0.5880 | 0.8514 | 0.8527 | 0.8685 | 0.4557 | 0.5981 | 0.8608 | 0.5443 | 0.4019 | 0.1392 |
| 0.7 | instrumental | 196 | 196 | 0.6635 | 0.8985 | 0.8983 | 0.9065 | 0.5561 | 0.7398 | 0.9082 | 0.4439 | 0.2602 | 0.0918 |
| 0.7 | vocal_scorable | 282 | 282 | 0.5865 | 0.8589 | 0.8551 | 0.8688 | 0.4681 | 0.6028 | 0.8582 | 0.5319 | 0.3972 | 0.1418 |

### semantic_fit


| sigma | stratum | n_subset | usable_n | Spearman | NDCG@1 | NDCG@2 | NDCG@4 | ret@1 | ret@2 | ret@4 | FN@1 | FN@2 | FN@4 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0.9 | all **<-headline** | 512 | 512 | 0.1301 | 0.5417 | 0.5794 | 0.6436 | 0.1777 | 0.3281 | 0.5469 | 0.8223 | 0.6719 | 0.4531 |
| 0.9 | vocal | 316 | 316 | 0.0805 | 0.4942 | 0.5441 | 0.6204 | 0.1519 | 0.2816 | 0.5190 | 0.8481 | 0.7184 | 0.4810 |
| 0.9 | instrumental | 196 | 196 | 0.2099 | 0.6184 | 0.6362 | 0.6811 | 0.2194 | 0.4031 | 0.5918 | 0.7806 | 0.5969 | 0.4082 |
| 0.9 | vocal_scorable | 282 | 282 | 0.0899 | 0.4926 | 0.5460 | 0.6234 | 0.1560 | 0.2837 | 0.5213 | 0.8440 | 0.7163 | 0.4787 |
| 0.8 | all **<-headline** | 512 | 512 | 0.2044 | 0.5591 | 0.6122 | 0.6726 | 0.1777 | 0.3672 | 0.6113 | 0.8223 | 0.6328 | 0.3887 |
| 0.8 | vocal | 316 | 316 | 0.1567 | 0.5095 | 0.5818 | 0.6434 | 0.1456 | 0.3544 | 0.5759 | 0.8544 | 0.6456 | 0.4241 |
| 0.8 | instrumental | 196 | 196 | 0.2812 | 0.6392 | 0.6612 | 0.7197 | 0.2296 | 0.3878 | 0.6684 | 0.7704 | 0.6122 | 0.3316 |
| 0.8 | vocal_scorable | 282 | 282 | 0.1597 | 0.5185 | 0.5878 | 0.6463 | 0.1454 | 0.3652 | 0.5816 | 0.8546 | 0.6348 | 0.4184 |
| 0.7 | all **<-headline** | 512 | 512 | 0.3032 | 0.6088 | 0.6570 | 0.7129 | 0.2227 | 0.4473 | 0.6816 | 0.7773 | 0.5527 | 0.3184 |
| 0.7 | vocal | 316 | 316 | 0.2434 | 0.5591 | 0.6101 | 0.6800 | 0.1962 | 0.4051 | 0.6424 | 0.8038 | 0.5949 | 0.3576 |
| 0.7 | instrumental | 196 | 196 | 0.3994 | 0.6890 | 0.7325 | 0.7660 | 0.2653 | 0.5153 | 0.7449 | 0.7347 | 0.4847 | 0.2551 |
| 0.7 | vocal_scorable | 282 | 282 | 0.2411 | 0.5586 | 0.6078 | 0.6782 | 0.1986 | 0.4078 | 0.6454 | 0.8014 | 0.5922 | 0.3546 |

### lyric_intelligibility

Headline = **vocal_scorable**. `instrumental` shown for transparency only (final==1.0 sentinel -> degenerate, expect usable_n~0).

| sigma | stratum | n_subset | usable_n | Spearman | NDCG@1 | NDCG@2 | NDCG@4 | ret@1 | ret@2 | ret@4 | FN@1 | FN@2 | FN@4 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0.9 | all | 512 | 102 | 0.0384 | 0.4119 | 0.4503 | 0.5321 | 0.1275 | 0.2745 | 0.5196 | 0.8725 | 0.7255 | 0.4804 |
| 0.9 | vocal | 316 | 102 | 0.0384 | 0.4119 | 0.4503 | 0.5321 | 0.1275 | 0.2745 | 0.5196 | 0.8725 | 0.7255 | 0.4804 |
| 0.9 | instrumental | 196 | 0 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| 0.9 | vocal_scorable **<-headline** | 282 | 102 | 0.0384 | 0.4119 | 0.4503 | 0.5321 | 0.1275 | 0.2745 | 0.5196 | 0.8725 | 0.7255 | 0.4804 |
| 0.8 | all | 512 | 232 | 0.2490 | 0.5467 | 0.5571 | 0.6145 | 0.2672 | 0.4612 | 0.6983 | 0.7328 | 0.5388 | 0.3017 |
| 0.8 | vocal | 316 | 232 | 0.2490 | 0.5467 | 0.5571 | 0.6145 | 0.2672 | 0.4612 | 0.6983 | 0.7328 | 0.5388 | 0.3017 |
| 0.8 | instrumental | 196 | 0 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| 0.8 | vocal_scorable **<-headline** | 282 | 230 | 0.2497 | 0.5484 | 0.5598 | 0.6178 | 0.2696 | 0.4652 | 0.7043 | 0.7304 | 0.5348 | 0.2957 |
| 0.7 | all | 512 | 240 | 0.5505 | 0.7317 | 0.7522 | 0.7833 | 0.4750 | 0.6667 | 0.8167 | 0.5250 | 0.3333 | 0.1833 |
| 0.7 | vocal | 316 | 240 | 0.5505 | 0.7317 | 0.7522 | 0.7833 | 0.4750 | 0.6667 | 0.8167 | 0.5250 | 0.3333 | 0.1833 |
| 0.7 | instrumental | 196 | 0 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| 0.7 | vocal_scorable **<-headline** | 282 | 237 | 0.5540 | 0.7363 | 0.7583 | 0.7879 | 0.4768 | 0.6709 | 0.8186 | 0.5232 | 0.3291 | 0.1814 |

### section_coherence


| sigma | stratum | n_subset | usable_n | Spearman | NDCG@1 | NDCG@2 | NDCG@4 | ret@1 | ret@2 | ret@4 | FN@1 | FN@2 | FN@4 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0.9 | all **<-headline** | 512 | 512 | 0.3883 | 0.7148 | 0.7339 | 0.7780 | 0.3203 | 0.5273 | 0.7773 | 0.6797 | 0.4727 | 0.2227 |
| 0.9 | vocal | 316 | 316 | 0.3816 | 0.7066 | 0.7298 | 0.7754 | 0.3006 | 0.5222 | 0.7785 | 0.6994 | 0.4778 | 0.2215 |
| 0.9 | instrumental | 196 | 196 | 0.3991 | 0.7281 | 0.7405 | 0.7822 | 0.3520 | 0.5357 | 0.7755 | 0.6480 | 0.4643 | 0.2245 |
| 0.9 | vocal_scorable | 282 | 282 | 0.3744 | 0.7069 | 0.7294 | 0.7734 | 0.2943 | 0.5106 | 0.7589 | 0.7057 | 0.4894 | 0.2411 |
| 0.8 | all **<-headline** | 512 | 512 | 0.5831 | 0.8093 | 0.8285 | 0.8549 | 0.4199 | 0.6523 | 0.8711 | 0.5801 | 0.3477 | 0.1289 |
| 0.8 | vocal | 316 | 316 | 0.5848 | 0.7878 | 0.8210 | 0.8537 | 0.3829 | 0.6519 | 0.8861 | 0.6171 | 0.3481 | 0.1139 |
| 0.8 | instrumental | 196 | 196 | 0.5802 | 0.8440 | 0.8407 | 0.8569 | 0.4796 | 0.6531 | 0.8469 | 0.5204 | 0.3469 | 0.1531 |
| 0.8 | vocal_scorable | 282 | 282 | 0.5924 | 0.7897 | 0.8240 | 0.8566 | 0.3688 | 0.6525 | 0.8830 | 0.6312 | 0.3475 | 0.1170 |
| 0.7 | all **<-headline** | 512 | 512 | 0.6860 | 0.8790 | 0.8801 | 0.8988 | 0.5527 | 0.7500 | 0.9375 | 0.4473 | 0.2500 | 0.0625 |
| 0.7 | vocal | 316 | 316 | 0.6772 | 0.8678 | 0.8723 | 0.8939 | 0.5190 | 0.7437 | 0.9367 | 0.4810 | 0.2563 | 0.0633 |
| 0.7 | instrumental | 196 | 196 | 0.7002 | 0.8971 | 0.8926 | 0.9066 | 0.6071 | 0.7602 | 0.9388 | 0.3929 | 0.2398 | 0.0612 |
| 0.7 | vocal_scorable | 282 | 282 | 0.6775 | 0.8705 | 0.8749 | 0.8959 | 0.5177 | 0.7376 | 0.9326 | 0.4823 | 0.2624 | 0.0674 |

## Explicit answers

### (1) Is aesthetic / production early-observable?
- **Verdict: NOT_CLEARLY_EARLY**
- aesthetic_pq Spearman by sigma (all): 0.9=0.2813, 0.8=0.5381, 0.7=0.6291  -> MID_OBSERVABLE
- aesthetic_cu Spearman by sigma (all): 0.9=0.2846, 0.8=0.5117, 0.7=0.6169  -> MID_OBSERVABLE

### (2) Vocal presence / type-match
- **PLANNED_DEFERRED** -- No measured vocal-presence / type-match labels in this cached pool. Not fabricated; deferred to GPU re-collection.

### (3) Is lyric_intelligibility late-observable?
- Stratum: vocal_scorable (vocal AND language==en, n=282 prompts)
- Spearman by sigma: 0.9=0.0384, 0.8=0.2497, 0.7=0.5540
- Rising toward final (0.7 vs 0.9): True
- **Verdict: LATE_OBSERVABLE** (class=LATE_OBSERVABLE)

### (4) Is semantic_fit early / mid / late?
- Spearman by sigma (all): 0.9=0.1301, 0.8=0.2044, 0.7=0.3032
- **Class: LATE_OBSERVABLE**

### (5) Which axes must NOT drive early restart?
- Criterion: early (sigma=0.9) within-prompt Spearman < 0.30 at headline stratum
- **DO NOT drive early restart (low early-sigma predictiveness):**
  - common_robust_lcb (Spearman@0.9 = 0.2472)
  - aesthetic_pq (Spearman@0.9 = 0.2813)
  - aesthetic_cu (Spearman@0.9 = 0.2846)
  - semantic_fit (Spearman@0.9 = 0.1301)
  - lyric_intelligibility (Spearman@0.9 = 0.0384)
- Safe to drive early restart:
  - section_coherence (Spearman@0.9 = 0.3883)

---
Artifacts: `AXIS_OBSERVABILITY_MATRIX.{md,csv,json}`, `AXIS_OBSERVABILITY_heatmap_spearman.csv` (orbit-research/); `heatmap_spearman.csv` (adsr_phase1_20260604/).
