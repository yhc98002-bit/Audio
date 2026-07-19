# Exit-1 Evidence Outline

| Inventory field | Frozen value |
|---|---|
| Scope | Exit-1 experimental evidence in `analysis_exit1_v2/`, `orbit-research/adsr_phase2_20260604/paper_prep/autochain_20260712/`, `orbit-research/adsr_phase2_20260604/paper_prep/w2_execution_20260712/`, `analysis_exit1_v2/neutral_control/`, `orbit-research/adsr_phase2_20260604/paper_prep/validation_B_prime/`, `orbit-research/adsr_phase2_20260604/paper_prep/validation_A_prime/`, and `orbit-research/adsr_phase2_20260604/paper_prep/tier3_bolt_20260715/`; cross-model pilots retained at their stated tiers. |
| Supersession | `analysis_exit1_v2/` supersedes `analysis_exit1/`; promoted `or` is paper-primary; historical legacy-detector and historical-`and` results are sensitivity-only. |
| Instrument vocabulary | **promoted-OR** = Demucs `>= 0.03161777090281248` OR PANNs `>= 0.04403413645923138`; **legacy** = historical Demucs-energy or historical fixed-AND rule; **judge** = validated Qwen3-Omni automatic label; **proxy** = CLAP, Audiobox, PickScore, OWLv2, or composite proxy. |
| Provenance vocabulary | **PI** = `pi:Richard`; **judge** = automatic validated-judge supplement; **automatic** = deterministic instrument application without a new human rating. |
| Interval rule | Intervals are copied from the cited tracked artifact. `CI not reported` means no interval is present in the canonical artifact; no interval is derived here. |
| Run boundary | Evidence inventory only; no new experiment, model inference, or audio generation. |

## 1. Measurement & instrument validity

### 1.1 Legacy-detector falsification — A-prime

| Required field | Inventory |
|---|---|
| Status | **PRIMARY** |
| Claim-ready sentence | The frozen A-prime criteria falsified validation of the legacy Demucs-energy threshold-`0.1791` Label-A instrument (`FAIL_LEGACY_INSTRUMENT_NOT_VALIDATED`); this quantifies `demucs_missing` and is not an A-prime PASS. |
| Sample and unit | `690` provenance-enforced rating rows: `190` PI core rows plus `500` validated-judge rating IDs; unit = clip/rating row; the judge supplement contains `493` unique media hashes after deduplication. |
| Instrument / label provenance | Instrument = **legacy** automatic Demucs-energy detector; reference labels = **PI** for the core and **judge** for the supplemental rows. |
| Evidence / source commit | `orbit-research/adsr_phase2_20260604/paper_prep/validation_A_prime/A_PRIME_GATE_REPORT_20260713.md`; `orbit-research/adsr_phase2_20260604/paper_prep/validation_A_prime/A_PRIME_GATE_RESULT_20260713.json`; source commit `9723bcf869987e55024dc7081f511146c9f88852`. Cardinality: `orbit-research/adsr_phase2_20260604/paper_prep/validation_A_prime/A_PRIME_CARDINALITY_RECONCILIATION.csv`; source commit `a5a60232e24deeaa4152d77dc4e4e4b1f143eeb1`. |
| Applicable banned phrasing | `legacy detector validated`; `A-prime PASS`; `690 unique clips`; `human-only 690-row study`; `legacy rates are corrected`; any claim that A-prime validates or invalidates the request-conditional paper-primary endpoint. |

| Frozen A-prime bucket | Match count | Match rate | CI | Statistical unit / provenance | Evidence |
|---|---:|---:|---|---|---|
| Detector-disagreement core | `7/112` | `0.062500` | CI not reported | clip; PI | `orbit-research/adsr_phase2_20260604/paper_prep/validation_A_prime/A_PRIME_GATE_REPORT_20260713.md` @ `9723bcf869987e55024dc7081f511146c9f88852` |
| Rare basin | `16/47` decided (`48` nominal; `1` abstention) | `0.3404255` | CI not reported | decided clip; PI | same report/commit |
| Controls | `28/30` | `0.9333333` | CI not reported | clip; PI | same report/commit |
| Stratified global supplement | `124/493` unique hashes | `0.2515213` | CI not reported | unique media hash; judge | same report/commit; merged judge artifacts @ `65094d43d0e19777caa0626c31a266a2869b5911` |

### 1.2 T6 promoted-OR instrument

| Required field | Inventory |
|---|---|
| Status | **PRIMARY** |
| Claim-ready sentence | The train-selected Demucs-OR-PANNs rule passed its once-exposed, design-weighted held-out request-conditional promotion evaluation with balanced accuracy `0.9873081909`, sensitivity `1.0000000000`, specificity `0.9746163818`, and `20/20` PI hidden-repeat agreement for both Label A and Label B. |
| Sample and unit | Train: `60` presentations, `58` decided (`24` positive, `34` negative), `2` abstentions, `7,566` candidates searched. Heldout: `100` presentations, `98` decided (`31` positive, `67` negative), `2` abstentions, `14` design strata; unit = presentation/clip; `10,000` stratified-bootstrap replicates, seed `20260712`. Reliability: `20` repeat pairs; unit = hidden repeat pair. |
| Instrument / label provenance | Instrument = **promoted-OR** automatic rule; promotion and reliability reference labels = **PI**; selected family = `or`. |
| Evidence / source commit | `orbit-research/adsr_phase2_20260604/paper_prep/autochain_20260712/T6_PROMOTION_REPORT.md`; `orbit-research/adsr_phase2_20260604/paper_prep/autochain_20260712/T6_PROMOTION_RESULT.json`; `orbit-research/adsr_phase2_20260604/paper_prep/autochain_20260712/T6_RELIABILITY_REPORT.md`; `orbit-research/adsr_phase2_20260604/paper_prep/autochain_20260712/T6_RELIABILITY_RESULT.json`; mechanical result source commit `168d12f1e47f555c85b7b9085da947b5ef261835`, report closeout source commit `86103d466d54a8c6363c6060074bb90442fdd30f`. |
| Applicable banned phrasing | `A-prime PASS`; `legacy detector validated`; `ground-truth population rate`; `causal vocal-generation bias`; any historical-AND value as primary; conflating the T6 request-conditional arena with Label-A evaluator Panels A/B. |

| Heldout metric | Design-weighted point | Two-sided 95% CI | One-sided 95% LCB | Unweighted sensitivity check [95% CI; LCB] | Evidence |
|---|---:|---|---:|---|---|
| Balanced accuracy | `0.9873081908896325` | `[0.9696095931221910, 0.9973201842671885]` | `0.9722719830934438` | `0.9402985074626866` [`0.9142857142857144`, `0.9615384615384616`; `0.9202898550724637`] | T6 result/report @ `168d12f1e47f555c85b7b9085da947b5ef261835` |
| Sensitivity | `1.0000000000000000` | `[1.0000000000000000, 1.0000000000000000]` | `1.0000000000000000` | `1.0000000000000000` [`1.0000000000000000`, `1.0000000000000000`; `1.0000000000000000`] | same |
| Specificity | `0.9746163817792650` | `[0.9392191862443819, 0.9946403685343770]` | `0.9445439661868874` | `0.8805970149253731` [`0.8285714285714286`, `0.9230769230769231`; `0.8405797101449275`] | same |
| MCC | `0.9238358865662966` | CI not reported | N/A | not headline | same |

| T6 reliability / transport audit | Exact result | CI | Unit | Evidence |
|---|---|---|---|---|
| Label-A hidden repeats | `20/20`; agreement `1.0`; kappa `1.0`; reversals `0/20` | CI not reported | repeat pair | T6 reliability report/result @ `168d12f1e47f555c85b7b9085da947b5ef261835` |
| Label-B hidden repeats | `20/20`; agreement `1.0`; kappa `1.0`; reversals `0/20` | CI not reported | repeat pair | same |
| Transport overall | `20` rows; `19` decided; BA `0.9635302082`; heldout delta `-0.0237779827` | CI not reported | clip | T6 promotion result @ same commit |
| N2 transport | `7` rows; BA `0.9526269510`; delta `-0.0346812399`; correction flag `false` | CI not reported | clip | same |
| Stage-3 transport | `7` rows; `6` decided; BA `1.0000000000`; delta `0.0126918091`; correction flag `false` | CI not reported | clip | same |
| Batch-3-keep transport | `6` rows; BA `1.0000000000`; delta `0.0126918091`; correction flag `false` | CI not reported | clip | same |

### 1.3 Validated judge chain

| Required field | Inventory |
|---|---|
| Status | **REDUCED** |
| Claim-ready sentence | On `216` all-PI, hash-disjoint Label-A gold clips (`149` yes, `67` no), the frozen Qwen3-Omni judge passed validation with design-weighted balanced accuracy `0.9507049554`, sensitivity `0.9914210138`, specificity `0.9099888970`, and `0/216` abstentions. |
| Sample and unit | `216` PI-gold clips; `3` deterministic calls per clip; calls majority-voted before analysis; unit = gold clip, not call; inverse-inclusion weights; `10,000` bootstrap replicates, seed `20260713`. Unweighted confusion: TP `146`, TN `65`, FP `2`, FN `3`. |
| Instrument / label provenance | Instrument = **judge** model `Qwen/Qwen3-Omni-30B-A3B-Instruct`, served as `qwen3-omni-judge`; reference labels = **PI**; judge outputs remain automatic, not human ratings. |
| Evidence / source commit | `orbit-research/adsr_phase2_20260604/paper_prep/t7_judge_gold_20260713/judge_completion/POOLED_JUDGE_VALIDATION_REPORT.md`; `orbit-research/adsr_phase2_20260604/paper_prep/t7_judge_gold_20260713/judge_completion/POOLED_JUDGE_VALIDATION.json`; weighting/seed: `orbit-research/adsr_phase2_20260604/paper_prep/scripts/complete_t7_judge_aprime_20260713.py`; inclusion probabilities: `orbit-research/adsr_phase2_20260604/paper_prep/t7_judge_gold_20260713/judge_completion/POOLED_DISJOINT_GOLD_MANIFEST.csv`; source commit `65094d43d0e19777caa0626c31a266a2869b5911`. |
| Applicable banned phrasing | `judge outputs are human ratings`; `Label-B judge validation`; `648 independent samples`; merging judge and promoted-OR results into one headline; saying the pre-top-up validation passed. |

| Metric | Point | Two-sided 95% CI | One-sided 95% LCB | Evidence |
|---|---:|---|---:|---|
| Balanced accuracy | `0.9507049553608808` | `[0.9390758991937093, 0.9602832030325827]` | `0.9411129929699182` | pooled report/JSON @ `65094d43d0e19777caa0626c31a266a2869b5911` |
| Sensitivity | `0.9914210137502085` | `[0.9824364056373961, 1.0000000000000000]` | `0.9827425651131632` | same |
| Specificity | `0.9099888969715532` | `[0.8891985777197848, 0.9255422371441620]` | `0.8931217893349092` | same |
| MCC | `0.9461842088410681` | CI not reported | N/A | same |

| Judge-chain sensitivity history | Exact result | Status / boundary | Evidence |
|---|---|---|---|
| Earliest PI-gold smoke | `10` clips (`5` positive, `5` negative), `30` calls; sensitivity `1.000000`, specificity `0.600000`, BA `0.800000`, MCC `0.654654`; CI not reported | **SENSITIVITY_ONLY**; `PI_BLOCKED` | `orbit-research/adsr_phase2_20260604/paper_prep/pi_ratings_20260711/processed/PI_GOLD_JUDGE_VALIDATION_REPORT.md` @ `2a58eee0810012ea3affc150697619b16f36e6ff` |
| Earliest PI-gold heldout | `105` clips (`98` positive, `7` negative), `315` calls; sensitivity `1.000000`, specificity `0.714286`, BA `0.857143`, MCC `0.836660`; CI not reported | **SENSITIVITY_ONLY**; `PI_BLOCKED` | same |
| Pre-top-up disjoint T6 | `176` clips (`149` positive, `27` negative); BA `0.9479822191` CI `[0.8937421409, 0.9996692569]`, LCB `0.9003600682`; sensitivity `0.9914210138` CI `[0.9746451278, 1.0000000000]`, LCB `0.9757932693`; specificity `0.9045434244` CI `[0.8025644122, 1.0000000000]`, LCB `0.8132561744` | **SENSITIVITY_ONLY**; `BLOCKED_CLASS_COUNT_TOPUP_REQUIRED` because `27 < 50` negatives | `orbit-research/adsr_phase2_20260604/paper_prep/autochain_20260712/judge_aprime/JUDGE_LABEL_A_VALIDATION_REPORT.md` @ `168d12f1e47f555c85b7b9085da947b5ef261835` |

### 1.4 Evaluator-comparison panels

| Required field | Panel A inventory |
|---|---|
| Status | **POWER_LIMITED** |
| Claim-ready sentence | On PI-only held-out Label-A gold, every evaluator-comparison estimate is power-limited because only `9` decided negatives were available. |
| Sample and unit | `126` decided clips (`117` positive, `9` negative), `71` prompt clusters; percentile prompt-cluster bootstrap requested `10,000`, valid `9,988`, seed `2026071602`; unit = clip with prompt-cluster resampling. |
| Instrument / label provenance | Instruments = **legacy**, **promoted-OR**, and automatic **proxy** comparators; reference labels = **PI**. |
| Evidence / source commit | `analysis_exit1_v2/EVALUATOR_COMPARISON_TABLE.md`; `analysis_exit1_v2/EVALUATOR_COMPARISON_AUDIT.json`; source commit `026572302d0d31a491b2b40e100c3344bba37167`. |
| Applicable banned phrasing | `adequately powered specificity evidence`; treating Panel-A OR BA `0.5` as the T6 BA; population/generalization claims. |

| Panel A evaluator | Sensitivity [95% CI] | Specificity [95% CI] | Balanced accuracy [95% CI] | MCC [95% CI] | Evidence |
|---|---|---|---|---|---|
| Legacy Demucs | `0.2564102564` [`0.1596638655`, `0.3423423423`] | `0.4444444444` [`0.1666666667`, `1.0000000000`] | `0.3504273504` [`0.2045284353`, `0.6094233631`] | `-0.1720052290` [`-0.3197724150`, `0.0850593527`] | comparison table/audit @ `026572302d0d31a491b2b40e100c3344bba37167` |
| Promoted OR | `1.0000000000` [`1.0000000000`, `1.0000000000`] | `0.0000000000` [`0.0000000000`, `0.0000000000`] | `0.5000000000` [`0.5000000000`, `0.5000000000`] | `0.0000000000` [`0.0000000000`, `0.0000000000`] | same |
| PANNs-only | `0.9401709402` [`0.8765153352`, `0.9909090909`] | `0.7777777778` [`0.5000000000`, `1.0000000000`] | `0.8589743590` [`0.7295646537`, `0.9913043478`] | `0.5883484054` [`0.3687254268`, `0.8625994698`] | same |
| Whisper | `0.7435897436` [`0.6485800253`, `0.8490566038`] | `0.7777777778` [`0.5000000000`, `1.0000000000`] | `0.7606837607` [`0.6185715879`, `0.9086956522`] | `0.2948236330` [`0.0988964531`, `0.4538535117`] | same |
| AudioSet exact whitelist | `0.9316239316` [`0.8785046729`, `0.9760000000`] | `0.4444444444` [`0.1000000000`, `1.0000000000`] | `0.6880341880` [`0.5152367424`, `0.9732142857`] | `0.3299422652` [`0.0284415983`, `0.6907474068`] | same |

| Required field | Panel B inventory |
|---|---|
| Status | **SENSITIVITY_ONLY** |
| Claim-ready sentence | On merged PI plus held-out-validated-judge Label-A gold, Panel B supplies instrument-qualified supplemental precision and does not replace the PI-only panel. |
| Sample and unit | `451` decided rows (`416` positive, `35` negative), `133` prompt clusters; input provenance = `126` PI decided rows plus `325` validated-judge decided rows; prompt-cluster bootstrap `10,000/10,000`, seed `2026071602`; unit = clip. |
| Instrument / label provenance | Instruments = **legacy**, **promoted-OR**, and automatic **proxy** comparators; labels = **PI + judge**, never human-only. |
| Evidence / source commit | `analysis_exit1_v2/EVALUATOR_COMPARISON_TABLE.md`; `analysis_exit1_v2/EVALUATOR_COMPARISON_AUDIT.json`; source commit `026572302d0d31a491b2b40e100c3344bba37167`; input `analysis_exit1/EVALUATOR_INPUT_ROWS.csv` @ `5eaf24f2ffbe4efe2153114a69ceee4e271424da`. |
| Applicable banned phrasing | `Panel B is PI-only`; `Panel B is human-only`; `Panel B replaces Panel A`; `Panel B is the T6 promotion arena`; interpreting legacy BA `~0.515` as validation. |

| Panel B evaluator | Sensitivity [95% CI] | Specificity [95% CI] | Balanced accuracy [95% CI] | MCC [95% CI] | Evidence |
|---|---|---|---|---|---|
| Legacy Demucs | `0.2019230769` [`0.1530247193`, `0.2640023739`] | `0.8285714286` [`0.6666666667`, `0.9714285714`] | `0.5152472527` [`0.4359354202`, `0.5940443861`] | `0.0204139679` [`-0.0837552702`, `0.1271860607`] | comparison table/audit @ `026572302d0d31a491b2b40e100c3344bba37167` |
| Promoted OR | `1.0000000000` [`1.0000000000`, `1.0000000000`] | `0.6000000000` [`0.4000000000`, `0.8000000000`] | `0.8000000000` [`0.7000000000`, `0.9000000000`] | `0.7618826132` [`0.6148184472`, `0.8867151771`] | same |
| PANNs-only | `0.9687500000` [`0.9456190193`, `0.9882075472`] | `0.8571428571` [`0.7272727273`, `0.9629629630`] | `0.9129464286` [`0.8475058910`, `0.9682662396`] | `0.7523849300` [`0.6250637558`, `0.8750362511`] | same |
| Whisper | `0.4975961538` [`0.4292340739`, `0.5721277583`] | `0.8285714286` [`0.7083333333`, `0.9393939394`] | `0.6630837912` [`0.5954264407`, `0.7319894820`] | `0.1748007138` [`0.0981425208`, `0.2570580654`] | same |
| AudioSet exact whitelist | `0.9543269231` [`0.9302949062`, `0.9760011976`] | `0.7714285714` [`0.5652173913`, `0.9583333333`] | `0.8628777473` [`0.7598230845`, `0.9558036220`] | `0.6416003504` [`0.4689900204`, `0.8048917021`] | same |

### 1.5 AudioSet whitelist correction

| Required field | Inventory |
|---|---|
| Status | **REDUCED** |
| Claim-ready sentence | The AudioSet comparator uses an exact `54`-label human-voice whitelist; among `679` unique media rows, `671` retained their prior score and `8` were rescored because the prior superset maximum was an excluded class. |
| Sample, interval, and unit | `679` unique media hashes; `8` new inference rows; `0` new labels; `0` new music generations; count audit only, so CI = N/A. |
| Instrument / label provenance | Instrument = AudioSet **proxy** with exact whitelist; output provenance = **automatic**; panel reference provenance remains PI or PI+judge as listed above. |
| Evidence / source commit | `analysis_exit1_v2/EVALUATOR_AUDIOSET_HUMAN_VOICE_SCORES.csv`; `analysis_exit1_v2/EVALUATOR_AUDIOSET_HUMAN_VOICE_AUDIT.json`; `analysis_exit1_v2/exit1_evaluator_v2.py`; `tests/test_exit1_evaluator_v2.py`; source commit `026572302d0d31a491b2b40e100c3344bba37167`; final delivery commit `135d8a7ec75bf86e8272e8345d930e426b3557ad`. |
| Applicable banned phrasing | substring-based `speech/singing` whitelist; treating synthetic speech, synthetic singing, bird/whale vocalization, or singing bowl as human voice; `proxy score is human annotation`; `ground truth`. |

## 2. Corrected phenomenon map

### 2.1 Unconditional base rate v2

| Required field | Inventory |
|---|---|
| Status | **PRIMARY** |
| Claim-ready sentence | Across the frozen `256`-output unconditional set, the promoted-OR instrument marked `187/256` voice-present (`0.73046875`, Wilson 95% CI `[0.673003, 0.781120]`); empty-prompt outputs were `98/128` (`0.765625`, `[0.685165, 0.830606]`) and neutral-text outputs were `89/128` (`0.6953125`, `[0.610849, 0.768394]`). |
| Sample and unit | `256` clips: `128` empty-prompt and `128` neutral-text; unit = generated output/clip; the retained near-silent row remains in the denominator. |
| Instrument / label provenance | Instrument = **promoted-OR**; labels = **automatic**, with thresholds selected against PI ratings. |
| Evidence / source commit | `analysis_exit1_v2/UNCONDITIONAL_BASE_RATE_V2.md`; `analysis_exit1_v2/UNCONDITIONAL_BASE_RATE_V2.csv`; `analysis_exit1_v2/UNCONDITIONAL_BASE_RATE_V2_AUDIT.json`; source commit `026572302d0d31a491b2b40e100c3344bba37167`. |
| Applicable banned phrasing | `causal vocal-generation bias`; `generic population rate`; `ground truth`; historical-AND `66.8%` as primary; dropping the near-silent row. |

| Sensitivity-only historical-AND stratum | Count/rate | Wilson 95% CI | Status | Evidence |
|---|---|---|---|---|
| Overall | `171/256 = 0.66796875` | `[0.608170, 0.722801]` | **SENSITIVITY_ONLY** | unconditional v2 CSV/report @ `026572302d0d31a491b2b40e100c3344bba37167` |
| Empty prompt | `91/128 = 0.7109375` | `[0.627167, 0.782416]` | **SENSITIVITY_ONLY** | same |
| Neutral text | `80/128 = 0.6250000` | `[0.538640, 0.704076]` | **SENSITIVITY_ONLY** | same |

### 2.2 Spine and N2 prevalence by request direction

| Required field | Inventory |
|---|---|
| Status | **PRIMARY** |
| Claim-ready sentence | Under the PI-calibrated promoted-OR instrument on the audited frozen design, calibrated violation prevalence in the `4,096`-row spine was `0.3864850388` (joint 95% interval `[0.3226333521, 0.4738123424]`) for instrumental requests and `0.0023106921` (`[0.0003519248, 0.0039046398]`) for vocal requests; N2 was `0.3924254409` (`[0.3038964064, 0.5061913344]`) and `0.0082957155` (`[0.0003585072, 0.0112000345]`), respectively. |
| Sample and unit | Spine = `1,568` instrumental rows / `196` prompts plus `2,528` vocal rows / `316` prompts; N2 = `6,016` instrumental rows / `47` prompts plus `10,368` vocal rows / `81` prompts; unit = output row; intervals = Wilson for direct instrument and nested prompt/calibration bootstrap for M2. |
| Instrument / label provenance | Paper-primary publication estimate = **promoted-OR** with PI-calibrated M2, trained on `58` decided PI calibration rows (`2` abstentions); direct promoted-OR hard rates are retained as mechanical instrument readouts; provenance = automatic application + PI calibration. |
| Evidence / source commit | `orbit-research/adsr_phase2_20260604/paper_prep/autochain_20260712/recompute/CORRECTED_PUBLICATION_RATES.csv`; `orbit-research/adsr_phase2_20260604/paper_prep/autochain_20260712/recompute/CORRECTED_RECOMPUTE_REPORT.md`; `orbit-research/adsr_phase2_20260604/paper_prep/autochain_20260712/recompute/CALIBRATION_MODEL_AUDIT.json`; source commit `168d12f1e47f555c85b7b9085da947b5ef261835`. |
| Applicable banned phrasing | `ground-truth prevalence`; `generic population rate`; `causal vocal-generation bias`; legacy apparent rate as corrected; calibrated M2 as a direct OR count. |

| Cohort / direction | Rows; prompts | Legacy apparent rate [95% CI] | Promoted-OR direct instrument readout [95% CI] | **PRIMARY** calibrated M2 publication rate [nested 95% interval] | Evidence |
|---|---|---|---|---|---|
| Spine / instrumental | `1,568`; `196` | `0.2595663265` [`0.2384733655`, `0.2818344902`] | `0.5235969388` [`0.4988487218`, `0.5482298176`] | `0.3864850388` [`0.3226333521`, `0.4738123424`] | corrected publication CSV/report @ `168d12f1e47f555c85b7b9085da947b5ef261835` |
| Spine / vocal | `2,528`; `316` | `0.2120253165` [`0.1965349065`, `0.2283895907`] | `0.0023734177` [`0.0010881985`, `0.0051686936`] | `0.0023106921` [`0.0003519248`, `0.0039046398`] | same |
| N2 / instrumental | `6,016`; `47` | `0.2388630319` [`0.2282572487`, `0.2498020953`] | `0.5164561170` [`0.5038218080`, `0.5290694236`] | `0.3924254409` [`0.3038964064`, `0.5061913344`] | same |
| N2 / vocal | `10,368`; `81` | `0.5986689815` [`0.5891990391`, `0.6080658351`] | `0.0125385802` [`0.0105700934`, `0.0148681531`] | `0.0082957155` [`0.0003585072`, `0.0112000345`] | same |

### 2.3 Stage-3 corrected rates

| Required field | Inventory |
|---|---|
| Status | **PRIMARY** |
| Claim-ready sentence | Across frozen Stage-3 rows, PI-calibrated promoted-OR violation rates were `0.9321526783` (`instr_both`), `0.7862971293` (`instr_sampler`), `0.8071731419` (`instr_text`), `0.0017096743` (`vocal_both`), `0.0006784739` (`vocal_guidance`), and `0.0190417226` (`vocal_hints`). |
| Sample and unit | Instrumental cells: `960` outputs and `15` prompts each; vocal cells: `1,088` outputs and `17` prompts each; unit = output row. |
| Instrument / label provenance | Paper-primary publication estimate = **promoted-OR** with PI-calibrated M2; direct hard-rate column = mechanical promoted-OR instrument readout; calibration labels = PI. |
| Evidence / source commit | `orbit-research/adsr_phase2_20260604/paper_prep/autochain_20260712/recompute/CORRECTED_PUBLICATION_RATES.csv`; source commit `168d12f1e47f555c85b7b9085da947b5ef261835`. |
| Applicable banned phrasing | `causal effect`; `population rate`; clean-rate/violation-rate complement left unlabeled; historical apparent value as primary. |

| Stage-3 condition | Rows; prompts | Promoted-OR direct instrument readout [95% CI] | **PRIMARY** calibrated M2 publication rate [nested 95% interval] | Evidence |
|---|---|---|---|---|
| `instr_both` | `960`; `15` | `0.9843750000` [`0.9743804711`, `0.9905085068`] | `0.9321526783` [`0.8524668538`, `0.9804224551`] | corrected publication CSV @ `168d12f1e47f555c85b7b9085da947b5ef261835` |
| `instr_sampler` | `960`; `15` | `0.8333333333` [`0.8084396544`, `0.8555699648`] | `0.7862971293` [`0.7259390743`, `0.8414578402`] | same |
| `instr_text` | `960`; `15` | `0.8677083333` [`0.8448032670`, `0.8876823442`] | `0.8071731419` [`0.7343702016`, `0.8771558640`] | same |
| `vocal_both` | `1,088`; `17` | `0.0027573529` [`0.0009381823`, `0.0080754513`] | `0.0017096743` [`0.0002115864`, `0.0040843820`] | same |
| `vocal_guidance` | `1,088`; `17` | `0.0000000000` [`0.0000000000`, `0.0035183302`] | `0.0006784739` [`0.0002115902`, `0.0017358496`] | same |
| `vocal_hints` | `1,088`; `17` | `0.0349264706` [`0.0255505590`, `0.0475749467`] | `0.0190417226` [`0.0002955138`, `0.0298391109`] | same |

### 2.4 Difficulty-continuum artifacts

| Required field | Inventory |
|---|---|
| Status | **PRIMARY** for the calibrated publication continuum and its direct promoted-OR instrument readout; **SENSITIVITY_ONLY** for legacy apparent and retired bins. |
| Claim-ready sentence | The corrected difficulty evidence is a continuous prompt-level ECDF with `876` cohort-direction prompt units and `2,628` metric records, not a retrospectively rebinned easy/recoverable/low/rare taxonomy. |
| Sample and unit | Unit = prompt within cohort/direction; `876` prompt-rate rows; `2,628 = 876 x 3` ECDF records for apparent, corrected direct, and calibrated metrics; no row-level inferential CI reported. |
| Instrument / label provenance | Publication metric = **promoted-OR** with PI-calibrated M2; direct promoted-OR = mechanical instrument readout; apparent = **legacy** sensitivity; calibration labels = PI. |
| Evidence / source commit | `orbit-research/adsr_phase2_20260604/paper_prep/autochain_20260712/recompute/CORRECTED_PROMPT_RATES.csv`; `orbit-research/adsr_phase2_20260604/paper_prep/autochain_20260712/recompute/CORRECTED_PROMPT_ECDFS.csv`; source commit `168d12f1e47f555c85b7b9085da947b5ef261835`. Retired bins: `orbit-research/adsr_phase2_20260604/paper_prep/analysis_v2/PUBLICATION_STATS_V2_REPORT.md` @ `5469f6c5e11d94b9b2bf4efc937db94fb5916bd2`. |
| Applicable banned phrasing | `retrospective hard difficulty bins`; `impossible to retry`; `1/mean(p)` as expected draws; generic-population taxonomy. |

| Cohort/direction prompt continuum | Prompt units | Direct promoted-OR minimum–maximum | PI-calibrated M2 minimum–maximum | Evidence |
|---|---:|---|---|---|
| Spine instrumental | `196` | `0–1` | `9.27439335543e-09–0.999737660568` | corrected prompt rates/ECDF @ `168d12f1e47f555c85b7b9085da947b5ef261835` |
| Spine vocal | `316` | `0–0.125` | `4.16893759144e-05–0.124386567197` | same |
| N2 instrumental | `47` | `0.078125–0.953125` | `0.0122958768412–0.920127344851` | same |
| N2 vocal | `81` | `0–0.15625` | `0.000184114282099–0.0626216827741` | same |
| Stage-3 instrumental | `15` | `0.776041666667–0.96875` | `0.676374922373–0.924588541306` | same |
| Stage-3 vocal | `17` | `0–0.046875` | `0.000671445025583–0.0302630323483` | same |
| Batch-3 instrumental | `85` | `0–1` | `2.51176605967e-09–0.999744513406` | same |
| Batch-3 vocal | `119` | `0–0` | `4.2036859825e-05–0.0111034528948` | same |

### 2.5 Cross-model pilot — ACE-Step v1.5

| Required field | Inventory |
|---|---|
| Status | **REDUCED** |
| Claim-ready sentence | On the selected difficult/stratified ACE-Step v1.5 set, vocal-request failures remained severe and the focused reconditioning lift was small and uncertain. |
| Exact numbers / unit | Smoke `2/2`; prevalence `1,024/1,024` outputs, `128` prompts x `8` seeds, per-draw type-correct `0.448242`, vocal/instrumental prompt means `0.169753/0.928191`; retry `512/512`, `16` prompts x `32` seeds, prompt mean `0.500000`, zero-clean `8/16`; intervention `256/256`, `128` matched pairs, prompt-mean delta `+0.054688`, prompt-bootstrap 95% CI `[0.000000, 0.132812]`, vocal `+0.078125`, instrumental `+0.031250`. CIs are not reported for smoke, prevalence, retry, or direction-specific intervention points. |
| Instrument / label provenance | Instrument = **legacy** automatic Demucs `0.1791`; provenance = automatic; no promoted-OR rescoring. |
| Evidence / source commit | `orbit-research/adsr_phase2_20260604/paper_prep/v15_replication_20260709/V15_FINAL_REPLICATION_REPORT.md`; `orbit-research/adsr_phase2_20260604/paper_prep/v15_replication_20260709/V15_ATTEMPT_AUDIT.csv`; source commit `8cba0f5882f51b010e912e3f54d15f2246f6e695`. |
| Applicable banned phrasing | `generic population`; `broad v1.5 intervention success`; pooling v1.5 with frozen v1; promoted-OR result; inferring an unreported prevalence numerator. |

### 2.6 Cross-model pilot — Stable Audio 3 Medium

| Required field | Inventory |
|---|---|
| Status | **REDUCED** |
| Claim-ready sentence | The Stable Audio 3 Medium pilot produced a guide-scale automatic-label prevalence map and a focused matched vocal-boost response, but it did not pass the frozen second-backbone promotion rule. |
| Exact numbers / unit | Prevalence: `4,000` clips = `500` prompts x `8`; correct `2,172/4,000 = 0.543000`, Wilson 95% CI `[0.527528, 0.558389]`; instrumental `1,512` clips, `0.991402` [`0.985345`, `0.994969`]; vocal `2,488`, `0.270498` [`0.253407`, `0.288298`]; vocal misses `1,815`, leaks `13`; best-of-8 `325/500 = 0.650000` [`0.607192`, `0.690521`]. Focused intervention: `32` vocal prompts x `8 = 256` matched pairs; baseline `14/256 = 0.054688`; boost `191/256 = 0.746094`; paired prompt-cluster lift `+0.691406`, 95% CI `[0.578125, 0.796875]`; fail-to-clean `177`, reverse `0`. |
| Instrument / label provenance | Instrument = **legacy** htdemucs `0.1791`, automatic; PI calibration bundle = `60` rows, `56` decided, TP `15`, TN `25`, FP `11`, FN `5`, sensitivity `0.75`, specificity `0.694444`, BA `0.722222`; calibration-metric CIs not reported; no promoted-OR rescoring. |
| Evidence / source commit | `orbit-research/adsr_phase2_20260604/paper_prep/sao/stable_audio_3_medium/prevalence_full500/SA3_PREVALENCE_REPORT.md`; `orbit-research/adsr_phase2_20260604/paper_prep/sao/stable_audio_3_medium/intervention/SA3_INTERVENTION_REPORT.md` @ `d84970bb611ac60976278e59308e31b2ca38e732`; paired CI: `orbit-research/adsr_phase2_20260604/paper_prep/sao/stable_audio_3_medium/intervention_fidelity/SA3_INTERVENTION_FIDELITY_REPORT.md` @ `1f7fa915517f15445a0bd82b6366d488bc89fbef`; calibration: `orbit-research/adsr_phase2_20260604/paper_prep/pi_ratings_20260712/processed/SA3_LABEL_CALIBRATION_REPORT_20260712.md` @ `e30f40f9f9ee14ff07557f6b17e205fb174dfcb8`. |
| Applicable banned phrasing | `full second-backbone robustness`; `human-validated SA3 prevalence`; `D7 promotion`; `full SA3 ADSR validation`; `superior early observability`; promoted-OR result. |

| SA3 observability addendum | Exact result | Status / boundary | Evidence |
|---|---|---|---|
| True-intermediate pilot | `96` prompts; `48/48` development/test; heldout same-trajectory step-1 BA `1.000000`, equal to independent-low-step BA `1.000000`; final replay agreement `95/96`; no superiority | **EXPLORATORY**; promotion `false` | `orbit-research/adsr_phase2_20260604/paper_prep/sao/stable_audio_3_medium/true_intermediate/SA3_INTERMEDIATE_REPORT.md`; `orbit-research/adsr_phase2_20260604/paper_prep/sao/stable_audio_3_medium/true_intermediate/SA3_INTERMEDIATE_METRICS.csv` @ `1f7fa915517f15445a0bd82b6366d488bc89fbef` |
| Intervention fidelity diagnostics | CLAP-to-original-prompt delta `-0.028321`, 95% CI `[-0.063965, 0.008950]`; loudness delta `-0.677559 dBFS` [`-1.417210`, `0.084518`]; within-prompt embedding-diversity delta `+0.046238` [`0.014146`, `0.078150`]; near-silent baseline/intervention `0/0` | **EXPLORATORY** proxies; not quality preservation | `orbit-research/adsr_phase2_20260604/paper_prep/sao/stable_audio_3_medium/intervention_fidelity/SA3_INTERVENTION_FIDELITY_REPORT.md` @ `1f7fa915517f15445a0bd82b6366d488bc89fbef` |

### 2.7 Cross-modal pilot — SDXL

| Required field | Inventory |
|---|---|
| Status | **EXPLORATORY** |
| Claim-ready sentence | The SDXL diagnostic reproduced prevalence, early-predictability, and compute-frontier signatures, while the probe-restart policy did not beat the fixed frontier. |
| Exact numbers / unit | Heldout pool = `2,000` images from `250` prompts x `8`; direction-specific image Ns are not reported. Image-level violation `0.287`, presence-request rate `0.218`, absence-request rate `0.356`. PickScore top-1 = `250` prompt-selected outputs, violation `0.248`. Probe AUROC at steps `6/10/14/16/20 = 0.6951/0.7624/0.7888/0.8007/0.8152`, `2,000` images per step. Frontier unit = `250` prompt-selected outputs; compute/type-error: BoN2 `0.25/0.156`, BoN4 `0.5/0.092`, BoN6 `0.75/0.064`, BoN8 `1.0/0.056`, step-20 probe restart `0.62/0.096`; CIs not reported. |
| Instrument / label provenance | Instrument = OWLv2 `0.1967`, PickScore, and probe **proxies**; provenance = automatic; cross-modal, not audio Label A/B. |
| Evidence / source commit | `orbit-research/adsr_phase2_20260604/t2i/T2I_SIGNATURES.md`; `orbit-research/adsr_phase2_20260604/t2i/T2I_SIGNATURES.json`; source commit `d84970bb611ac60976278e59308e31b2ca38e732`. |
| Applicable banned phrasing | `method efficacy`; `full cross-modal robustness`; `audio replication`; `probe restart beat frontier`; inventing CIs. |

### 2.8 Retained pre-W2 phenomenon and retry evidence

| Evidence item | Status | Claim-ready sentence | Exact numbers, CI, N, and unit | Instrument / label provenance | Evidence path / source commit | Applicable banned phrasing |
|---|---|---|---|---|---|---|
| Legacy candidate/survivor prevalence | **SENSITIVITY_ONLY** | Under the legacy threshold, common-score survivor selection reduced but did not eliminate apparent request-conditional type errors. | Candidate rows `4,096`: rate `0.2300`, vocal-request miss count `533`, instrumental-request leak count `409`; prompt affected rate `0.6367`; selected top-1 across `512` prompts `0.1992` (vocal `0.1867`, instrumental `0.2194`); ambiguous near threshold `557 = 13.6%`; CIs not reported. Unit = output for candidate rate and prompt-selected output for top-1. | **legacy** Demucs `0.1791`; automatic | `orbit-research/adsr_phase2_20260604/VOCAL_TYPE_ERROR_PREVALENCE.md` @ `d84970bb611ac60976278e59308e31b2ca38e732` | corrected prevalence; human-validated truth; generic population; selection fixes all violations |
| Free-filter frontier | **SENSITIVITY_ONLY** | Under the legacy detector on heldout prompts, a free final gate saturated the easy cases while retaining a nonzero all-seeds-fail floor. | Heldout `n=256` prompts: bon8-gated type error `0.0117` [95% CI `0.0000`, `0.0273`], equal to all-8-fail floor `0.0117`; bon4-gated `0.0391` [`0.0195`, `0.0625`]; gated EVPD-k4 `0.0195`, oracle-k4/unconstrained `0.0117`; oracle-probe efficiency upper bound `+14.9%`. CIs are not reported for gated EVPD-k4, oracle-k4/unconstrained, or the efficiency upper bound. Unit = prompt-selected output. | **legacy** automatic detector + oracle **proxy** | `orbit-research/adsr_phase2_20260604/phase0/P0_1_GATED_FRONTIER.json`; `orbit-research/adsr_phase2_20260604/phase0/P0_2_ORACLE_DECOMP.json`; `orbit-research/adsr_phase2_20260604/GATE_B_FINAL_REPORT.md` @ `d84970bb611ac60976278e59308e31b2ca38e732` | impossible to retry; detector-independent truth; promoted-OR result; deployable oracle |
| Legacy seed recoverability | **SENSITIVITY_ONLY** | On the selected difficult test set, fresh-seed clean probability was lower for vocal-hard than instrumental-hard prompts under the legacy detector. | Baseline vocal-hard mean/median `0.088120/0.064453`; instrumental-hard `0.359115/0.361328`; frozen allowed denominator pending reconciliation = `8,192` draws (`32` prompts x `256` tries); `0/32` prompts were zero-clean at `N=256`; no CIs reported for these summaries. Unit = prompt clean-rate estimate. | **legacy** automatic detector | `orbit-research/adsr_phase2_20260604/paper_prep/analysis/efficiency_claims.md`; `orbit-research/adsr_phase2_20260604/paper_prep/analysis/expected_draws_metrics.csv` @ `d84970bb611ac60976278e59308e31b2ca38e732`; frozen denominator constraint in `orbit-research/adsr_phase2_20260604/paper_prep/CLAIMS.md` @ `00fe296cabcf25f96b35d21bef7b507d42418085` | generic population; impossible; `1/mean(p)` expected draws; corrected bins; unreconciled `16,384` total |
| Limited-draw reconditioning | **SENSITIVITY_ONLY** | On the selected difficult test set at `N=4`, legacy-label reconditioning strongly changed vocal-hard deployment success and was near-null for instrumental-hard prompts. | Vocal baseline `S_N = 0.291566` versus V3 `0.988660`, prompt-paired delta `+0.697094`, cluster-bootstrap 95% CI `[0.611728, 0.777974]`, `17` prompts x `128` intervention seeds; instrumental baseline `0.806827` versus I-strong `0.805932`, delta `-0.000896`, CI `[-0.076656, 0.065956]`, `15` prompts x `128` intervention seeds; bootstrap `10,000`; unit = prompt. | **legacy** automatic detector; no human quality label | `orbit-research/adsr_phase2_20260604/paper_prep/analysis_v2/deployment_success_metrics.csv`; `orbit-research/adsr_phase2_20260604/paper_prep/analysis_v2/deployment_success_paired_deltas.csv`; `orbit-research/adsr_phase2_20260604/paper_prep/analysis_v2/PUBLICATION_STATS_V2_REPORT.md` @ `5469f6c5e11d94b9b2bf4efc937db94fb5916bd2` | corrected/paper-primary endpoint; generic population; universal repair; quality preservation |

## 3. Interventions

### 3.1 Factorial six-condition result

| Required field | Inventory |
|---|---|
| Status | **PRIMARY** for direct promoted-OR Label-B satisfaction; **EXPLORATORY** for calibrated M2 and quality diagnostics. |
| Claim-ready sentence | Under the promoted-OR primary endpoint, satisfaction was highest in the positive-sampler cell (`0.568359375`) among the six preregistered factorial cells; its direct-primary prompt-cluster CI is not reported in the tracked artifact. |
| Sample and unit | `3,072` clips total; `6` conditions x `32` prompt clusters x `16` common-random-number seeds = `512` clips/cell; unit = output with prompt-cluster bootstrap. |
| Instrument / label provenance | Primary instrument = **promoted-OR** automatic Label-B violation/satisfaction; calibrated M2 is secondary and uses PI calibration labels; quality columns = automatic **proxy** diagnostics. |
| Evidence / source commit | `orbit-research/adsr_phase2_20260604/paper_prep/autochain_20260712/factorial/FACTORIAL_SCORING_REPORT.md`; `orbit-research/adsr_phase2_20260604/paper_prep/autochain_20260712/factorial/FACTORIAL_CONDITION_RESULTS.csv`; source commit `168d12f1e47f555c85b7b9085da947b5ef261835`; corrected positive cohorts: `orbit-research/adsr_phase2_20260604/paper_prep/w2_execution_20260712/factorial/FACTORIAL_POSITIVE_CORRECTION_ADDENDUM.md`. |
| Applicable banned phrasing | `causal bias`; `generic population`; `ground truth`; `proved no loss`; `no quality degradation`; `universal winner`; using the invalid initial positive cohort as primary. |

| Condition | Clips; prompts | **PRIMARY** direct promoted-OR satisfaction (CI not reported) | Secondary calibrated satisfaction [95% prompt-bootstrap CI] | Evidence |
|---|---|---:|---|---|
| `plain_baseline` | `512`; `32` | `0.339843750` | `0.4384056893` [`0.3542909483`, `0.5254340453`] | factorial condition CSV/report @ `168d12f1e47f555c85b7b9085da947b5ef261835` |
| `negative_text` | `512`; `32` | `0.263671875` | `0.3876462148` [`0.3164786460`, `0.4574563351`] | same |
| `positive_text` | `512`; `32` | `0.552734375` | `0.6608059215` [`0.5668142543`, `0.7477994554`] | same |
| `sampler_only` | `512`; `32` | `0.359375000` | `0.4584383393` [`0.3583265767`, `0.5607083483`] | same |
| `negative_sampler` | `512`; `32` | `0.269531250` | `0.4001858853` [`0.3221368052`, `0.4796390705`] | same |
| `positive_sampler` | `512`; `32` | `0.568359375` | `0.6797944307` [`0.5826621722`, `0.7687567182`] | same |

| Interaction contrast | Point | CI | Status | Evidence |
|---|---:|---|---|---|
| Negative | `-0.0074929796` | CI not reported | **EXPLORATORY** | `orbit-research/adsr_phase2_20260604/paper_prep/autochain_20260712/factorial/FACTORIAL_INTERACTION_CONTRASTS.csv` @ `168d12f1e47f555c85b7b9085da947b5ef261835` |
| Positive | `-0.0010441408` | CI not reported | **EXPLORATORY** | same |

| Quality-proxy diagnostic by cell | CLAP prompt similarity mean | Audiobox aesthetic PQ mean | Near-silence rate | MFCC pairwise cosine distance | Interval / evidence |
|---|---:|---:|---:|---:|---|
| `plain_baseline` | `0.2982200536` | `6.8403616901` | `0.001953125` | `0.3248948634` | CIs not reported; factorial condition CSV @ `168d12f1e47f555c85b7b9085da947b5ef261835` |
| `negative_text` | `0.2702658337` | `6.6922578411` | `0` | `0.3336703732` | CIs not reported; same |
| `positive_text` | `0.3060680256` | `6.9063778599` | `0` | `0.3437031111` | CIs not reported; same |
| `sampler_only` | `0.3141919871` | `6.9250977635` | `0.001953125` | `0.3221517642` | CIs not reported; same |
| `negative_sampler` | `0.2826126021` | `6.7248076648` | `0` | `0.3323261299` | CIs not reported; same |
| `positive_sampler` | `0.3157793641` | `6.9775664508` | `0` | `0.3414291930` | CIs not reported; same |

| Invalid first-positive implementation sensitivity | Invalid cohort N / candidate violation | Corrected positive-only candidate violation [95% prompt-bootstrap CI] | Status / evidence |
|---|---|---|---|
| `positive_text` | `512`; `0.435547` | `0.353516` [`0.263672`, `0.443359`] | **SENSITIVITY_ONLY**; `orbit-research/adsr_phase2_20260604/paper_prep/w2_execution_20260712/factorial/FACTORIAL_CANONICAL_READOUT.md`; `orbit-research/adsr_phase2_20260604/paper_prep/w2_execution_20260712/factorial/FACTORIAL_POSITIVE_CORRECTION_ADDENDUM.md` @ `25a4853e7e5f0894cac0d551c2ef9ce422fea594` |
| `positive_sampler` | `512`; `0.406250` | `0.332031` [`0.230469`, `0.435547`] | **SENSITIVITY_ONLY**; same |

### 3.2 Neutral-control four-cell result

| Required field | Inventory |
|---|---|
| Status | **EXPLORATORY** |
| Claim-ready sentence | The prompt-paired 95% CI includes zero, so this cell does not rule out the matched-length/neutral-descriptor explanation within the selected subset. |
| Sample and unit | `24` risk-ranked prompt clusters x `8` seeds = `192` outputs per cell; `10,000` deterministic prompt-cluster bootstrap replicates; paired comparison unit = `24` prompts; sign-flip test `100,000` draws. |
| Instrument / label provenance | Instrument = **promoted-OR** automatic; thresholds selected/calibrated against PI labels. |
| Frozen design qualifications | Single studio-descriptor neutral phrase assumed vocally inert; exact token-count matching is not semantic equivalence; neutral-cell seeds are independent and paired only by prompt, not noise; positive contextual rows replace source negative wording and are not a pure same-base control. |
| Evidence / source commit | `analysis_exit1_v2/neutral_control/NEUTRAL_CONTROL_REPORT.md` @ `d96f33999be1921bc370e5b6b8d02f0256fc8ccb`; `analysis_exit1_v2/neutral_control/FOUR_CELL_RESULTS.csv`; `analysis_exit1_v2/neutral_control/FOUR_CELL_RESULTS.json` @ `fd9cba693dd9f7cadd0fc9d80e38e4a19392c23d`. |
| Applicable banned phrasing | `negative wording has no effect`; `neutral rules out dilution`; `negation causes more violations`; generalizing the selected `24/32` risk-ranked prompts. |

| Cell | Outputs; prompts | Violation rate [95% prompt-bootstrap CI] | Evidence |
|---|---|---|---|
| Plain | `192`; `24` | `0.7447916667` [`0.6614583333`, `0.8229166667`] | four-cell CSV/report @ `fd9cba693dd9f7cadd0fc9d80e38e4a19392c23d` / `d96f33999be1921bc370e5b6b8d02f0256fc8ccb` |
| Neutral-matched | `192`; `24` | `0.7968750000` [`0.7135416667`, `0.8697916667`] | same |
| Negative | `192`; `24` | `0.8229166667` [`0.7447916667`, `0.8958333333`] | same |
| Positive | `192`; `24` | `0.5260416667` [`0.4114583333`, `0.6354166667`] | same |
| Neutral minus negative | `24` paired prompts | delta `-0.0260416667` [`-0.1093750000`, `0.0520833333`]; two-sided sign-flip `p = 0.6377536225` | same |

### 3.3 Recipe curves v2

| Required field | Inventory |
|---|---|
| Status | **EXPLORATORY**; quality endpoint demoted to `PROXY_QUALIFIED_SUCCESS`. |
| Claim-ready sentence | At equal generation compute, both positive recipes first reached the lowest observed promoted-OR violation rate at `N=4` (`3/32 = 0.09375`, 95% prompt-bootstrap CI `[0, 0.1875]`) versus plain `8/32 = 0.25` [`0.125, 0.40625`], paired delta `-0.15625` [`-0.28125, -0.03125`], with no deployment recommendation. |
| Sample and unit | `32` prompt clusters; `16` common-random-number attempts per condition; gate-first selection at `N=1,2,4,8`; `10,000` prompt-cluster bootstrap replicates; unit = selected prompt output. |
| Instrument / label provenance | Violation = **promoted-OR** automatic; quality = CLAP + Audiobox **proxy**; PI provenance only through T6 calibration. |
| Evidence / source commit | `analysis_exit1_v2/RECIPE_CURVES_V2.md`; `analysis_exit1_v2/RECIPE_CURVES_V2.csv`; `analysis_exit1_v2/RECIPE_CURVES_V2_AUDIT.json`; source commit `026572302d0d31a491b2b40e100c3344bba37167`. |
| Applicable banned phrasing | `deployable`; `best operating point`; `genuine qualified success`; `quality preserved`; `no quality loss`; `N=8 is the v2 optimum`. |

| N | Plain violation [95% CI] | Positive-text violation [95% CI]; delta [95% CI] | Positive-sampler violation [95% CI]; delta [95% CI] | Evidence |
|---:|---|---|---|---|
| `1` | `23/32 = 0.71875` [`0.5625`, `0.875`] | `16/32 = 0.5` [`0.3125`, `0.65625`]; `-0.21875` [`-0.375`, `-0.09375`] | `16/32 = 0.5` [`0.3125`, `0.6875`]; `-0.21875` [`-0.375`, `-0.09375`] | recipe v2 CSV @ `026572302d0d31a491b2b40e100c3344bba37167` |
| `2` | `12/32 = 0.375` [`0.21875`, `0.53125`] | `8/32 = 0.25` [`0.12421875`, `0.40625`]; `-0.125` [`-0.25`, `-0.03125`] | `8/32 = 0.25` [`0.125`, `0.40625`]; `-0.125` [`-0.25`, `-0.03125`] | same |
| `4` | `8/32 = 0.25` [`0.125`, `0.40625`] | `3/32 = 0.09375` [`0`, `0.1875`]; `-0.15625` [`-0.28125`, `-0.03125`] | `3/32 = 0.09375` [`0`, `0.1875`]; `-0.15625` [`-0.28125`, `-0.03125`] | same |
| `8` | `6/32 = 0.1875` [`0.0625`, `0.34375`] | `3/32 = 0.09375` [`0`, `0.21875`]; `-0.09375` [`-0.21875`, `0`] | `3/32 = 0.09375` [`0`, `0.21875`]; `-0.09375` [`-0.21875`, `0`] | same |

| Quality-proxy diagnostic | Plain | Positive text | Positive sampler | Evidence / boundary |
|---|---|---|---|---|
| `N=1` qualified-success | `8/32 = 0.25` [`0.09375`, `0.40625`] | `9/32 = 0.28125` [`0.125`, `0.4375`] | `10/32 = 0.3125` [`0.15625`, `0.46875`] | recipe v2 CSV; **EXPLORATORY** proxy |
| `N=2` qualified-success | `14/32 = 0.4375` [`0.28125`, `0.59375`] | `19/32 = 0.59375` [`0.40625`, `0.75`] | `22/32 = 0.6875` [`0.53125`, `0.84375`] | same |
| `N=4` qualified-success | `17/32 = 0.53125` [`0.34375`, `0.6875`] | `25/32 = 0.78125` [`0.625`, `0.90625`]; delta `0.25` [`0.09375`, `0.40625`] | `25/32 = 0.78125` [`0.625`, `0.90625`]; delta `0.25` [`0.09375`, `0.40625`] | same; `quality_primary = 0` |
| `N=8` qualified-success | `23/32 = 0.71875` [`0.5625`, `0.875`] | `29/32 = 0.90625` [`0.8125`, `1.0`] | `29/32 = 0.90625` [`0.8125`, `1.0`] | same; `quality_primary = 0` |

### 3.4 Live confirmation — four frozen policies

| Required field | Inventory |
|---|---|
| Status | **REDUCED** |
| Claim-ready sentence | Under the promoted corrected instrument, the bounded live confirmation did not support probe-routed direction-specific action; always applying the direction-specific conditioning had the lowest observed violation rate. |
| Sample and unit | `128` outputs/policy = `64` prompt clusters x `2` replicates (`96` instrumental-risk, `32` vocal-sanity); unit = output with prompt-cluster bootstrap; frozen contrasts use `20,000` replicates. |
| Instrument / label provenance | Instrument = **promoted-OR** automatic; PI-calibrated thresholds; missing selected output conservatively coded violation. |
| Evidence / source commit | `orbit-research/adsr_phase2_20260604/paper_prep/w2_execution_20260712/live_confirmation_20260713/LIVE_CONFIRM_REPORT.md`; `orbit-research/adsr_phase2_20260604/paper_prep/w2_execution_20260712/live_confirmation_20260713/LIVE_CONFIRM_RESULTS.csv`; `orbit-research/adsr_phase2_20260604/paper_prep/w2_execution_20260712/live_confirmation_20260713/LIVE_CONFIRM_AUDIT.json`; source commit `86103d466d54a8c6363c6060074bb90442fdd30f`. |
| Applicable banned phrasing | `live PASS`; `router win`; `probe-routed policy won`; `actual-step post-hoc PASS`; `abort savings were rolled over`; `rollover fixed the live failure`. |

| Policy | N | Violation rate | No-completed-output rate | Mean actual / nominal steps | Point CI | Evidence |
|---|---:|---:|---:|---:|---|---|
| `no_probe_reseed` | `128` | `0.265625` | `0` | `60.00000 / 60` | CI not reported | live results/report @ `86103d466d54a8c6363c6060074bb90442fdd30f` |
| `corrected_probe_abort_reseed` | `128` | `0.4921875` | `0.390625` (`50/128`) | `38.90625 / 60` | CI not reported | same |
| `always_direction_condition` | `128` | `0.1640625` | `0` | `60.00000 / 60` | CI not reported | same |
| `corrected_probe_direction_action` | `128` | `0.3125000` | `0` | `45.93750 / 60` | CI not reported | same |

| Frozen live contrast | Point / bound | Decision | Evidence |
|---|---|---|---|
| Policy 4 versus policy 1 violation reduction (`policy 1 - policy 4`) | median `-0.046875`; one-sided 95% LCB `-0.109375` | primary criterion failed | live audit @ `86103d466d54a8c6363c6060074bb90442fdd30f` |
| Policy 4 minus policy 3 violation | median `0.1484375`; one-sided 95% UCB `0.203125` | noninferiority criterion failed | same |
| Frozen gate | `CRITERIA_NOT_ALL_MET` | nominal-compute and vocal-sanity criteria passed; primary and noninferiority criteria failed | same |
| Budget-discard caveat | Frozen two-slot accounting leaves abort savings unused; `50/128` policy-2 no-output slots remain conservative violations | no post-hoc reinterpretation | same |

### 3.5 Rollover replay status

| Required field | Inventory |
|---|---|
| Status | **EXPLORATORY** |
| Claim-ready sentence | In the frozen development-pilot static replay, true rollover completed within the global budget but did not exceed the frozen W2 two-slot static program. |
| Exact numbers / unit | `true_rollover_corrected_evpd`: design-weighted CQS@60 `0.6289746544`, equal-prompt `0.4583333333`, completion `1.0`, mean NFE `87.7923195`, max NFE `90`, infeasible `0`, quality-floor failures `26`; frozen W2 two-slot: `0.7451996928`, `0.6875`, completion `1.0`, mean NFE `83.3769585`, max `90`, failures `14`. Unit = `48` development prompts/static-program outcome. CI not reported for this table. |
| Instrument / label provenance | Composite CQS = promoted W2 automatic Label-B constraint + robust-LCB/CLAP **proxy** floors + valid output/completion; no new human labels; development replay only. |
| Evidence / source commit | `orbit-research/adsr_phase2_20260604/paper_prep/tier3_bolt_20260715/BOLT_STATIC_PROGRAM_TABLE.csv`; source commit `bc4e9444297efecddf88a225301a016b1d9c8a38`; integrated on main by merge commit `758faae3c67c2137ad81b345ade9cc7530227e24`. |
| Applicable banned phrasing | `live rollover reanalysis`; `rollover fixed the live failure`; `prospective confirmation`; `deployment result`; `oracle achieved`. |

### 3.6 Historical conditioned-respawn confirmation

| Required field | Inventory |
|---|---|
| Status | **SENSITIVITY_ONLY** after legacy-instrument falsification and promoted-OR live confirmation. |
| Claim-ready sentence | In the frozen pre-W2 legacy-detector tail experiment, conditioned respawn increased per-draw clean rate at equal nominal compute, but this result is not the promoted-OR live-confirmation outcome. |
| Exact numbers / unit | Frozen `n=32` tail: restart2+ arm6 minus arm4 per-draw clean-rate delta `+0.4299`, 95% CI `[0.2730, 0.5788]`; selected type error arm6 `0.0098` versus arm1 `0.1146`; clean yield `3.7108` versus `2.8614` (`+29.7%`); process ledger `3,648` units / `22,825` attempts; `0` validation violations. Unit = frozen tail prompt/output according to endpoint; legacy aggregate source rounds the primary contrast to `+0.43` [`0.27`, `0.58`]. |
| Instrument / label provenance | **legacy** automatic detector + automatic quality proxies; no human quality validation. |
| Evidence / source commit | `orbit-research/adsr_phase2_20260604/GATE_B_FINAL_REPORT.md` @ `d84970bb611ac60976278e59308e31b2ca38e732`; exact frozen ledger summary retained in `orbit-research/adsr_phase2_20260604/paper_prep/CLAIMS.md`. The detailed online result/ledger paths named there are absent at current HEAD and therefore are not cited as primary evidence files. |
| Applicable banned phrasing | `current live confirmation PASS`; promoted-OR result; human quality validated; confirmed deployability; unconstrained/rolled-over budget. |

## 4. Honest negatives

### 4.1 B-prime noninferiority gate

| Required field | Inventory |
|---|---|
| Status | **REDUCED** |
| Claim-ready sentence | no statistically significant quality preference in either direction (method preferred in `42%` of decided pairs; one-sided `p = 0.156`); the pre-registered non-inferiority bound (`LCB > 0.40`) was NOT met, so no-quality-degradation is reported as unconfirmed, not established. |
| Sample and unit | Primary first presentations: `80` T3 pairs; unit = PI-rated pair; `24` T4 reversals excluded from the primary gate because of the same-session protocol deviation. |
| Instrument / label provenance | Instrument = blinded paired **PI** rating; single expert `pi:Richard`; no judge or automatic replacement. |
| Evidence / source commit | `orbit-research/adsr_phase2_20260604/paper_prep/validation_B_prime/B_PRIME_GATE_REPORT_20260712.md`; `orbit-research/adsr_phase2_20260604/paper_prep/validation_B_prime/B_PRIME_GATE_RESULT_20260712.json`; `orbit-research/adsr_phase2_20260604/paper_prep/pi_ratings_20260712/processed/T3_B_PRIME_PRIMARY_OFFICIAL.csv`; source commit `c682212c5039582e62d9ec4493822f42fe578d57`. |
| Applicable banned phrasing | `no quality loss`; `no degradation`; `quality preserved`; `noninferiority passed`; `multiple independent raters`. |

| Endpoint | Method / baseline / ties / abstain | Decided; method rate | Score one-sided 95% LCB | Exact one-sided 95% LCB | One-sided p | Evidence |
|---|---|---|---:|---:|---:|---|
| Quality | `20 / 28 / 32 / 0` | `48`; `0.416667` | `0.307145` | `0.295877` | `0.156163` | B-prime report/result @ `c682212c5039582e62d9ec4493822f42fe578d57` |
| Overall | `18 / 27 / 35 / 0` | `45`; `0.400000` | `0.288866` | `0.276826` | `0.116347` | same |
| Constraint | `15 / 26 / 39 / 0` | `41`; `0.365854` | `0.254029` | `0.240809` | `0.058638` | same |

| Mandatory B-prime limitation | Exact inventory fact | Evidence |
|---|---|---|
| Rater | Single expert rater | B-prime report @ `c682212c5039582e62d9ec4493822f42fe578d57` |
| Tie rate | `32/80 = 40%` on the primary quality endpoint | same |
| Pair selection | Pairs selected under the pre-W2 detector | same |
| Reverse block | T4 completed in the same session; later-day protocol violated; agreement is an upper bound | same; `orbit-research/adsr_phase2_20260604/paper_prep/pi_ratings_20260712/processed/T4_ORDER_BIAS_AND_RELIABILITY_REPORT_20260712.md` |

### 4.2 A-prime legacy falsification framing

| Required field | Inventory |
|---|---|
| Status | **REDUCED** as an honest-negative framing of Section 1.1. |
| Claim-ready sentence | A-prime measures Label A (perceived voice presence), while the signed amendment's paper-primary endpoint is Label B (request-conditional constraint satisfaction); A-prime therefore does not validate or invalidate the paper-primary endpoint. |
| Exact numbers / unit | `7/112`, `16/47` decided, `28/30`, and `124/493`; CIs not reported; `690` rows = `190` PI + `500` judge-supplement rating IDs; unit/provenance as in Section 1.1. |
| Instrument / label provenance | Tested instrument = **legacy**; Label-A reference = PI core + validated **judge** supplement. |
| Evidence / source commit | `orbit-research/adsr_phase2_20260604/paper_prep/validation_A_prime/A_PRIME_GATE_REPORT_20260713.md`; source commit `9723bcf869987e55024dc7081f511146c9f88852`; frozen scope also recorded in `orbit-research/adsr_phase2_20260604/paper_prep/CLAIMS.md`. |
| Applicable banned phrasing | `A-prime PASS`; `legacy validated`; `paper-primary endpoint failed A-prime`; `judge rows are human`; `legacy apparent rates are corrected`. |

### 4.3 Gate 1.5A state-adaptive null

| Required field | Inventory |
|---|---|
| Status | **REDUCED** |
| Claim-ready sentence | In the frozen `48`-prompt development pilot, prompt+state and prompt-only policies had identical CQS `0.783717358` (paired increment `0`, 95% interval `[0, 0]`), mechanically stopping this axis. |
| Exact scope wording | This analysis uses only the frozen 48-prompt BOLT pilot, its 96 roots, 288 persisted checkpoint tensors, and 1,440 action outcomes. It tests whether checkpoint-state information adds cross-fitted policy value beyond prompt-only information. It does not train a production controller, collect new action outcomes, use held-out prompts, start Gate 1.5B, or start Gate 2. |
| Sample and unit | `48` development prompts; `96` roots; `288` persisted states; `1,440` action outcomes; `6` prompt-grouped folds; `10,000` clustered-bootstrap replicates; policy-value unit = prompt/design-weighted persisted state. |
| Instrument / label provenance | CQS = promoted W2 automatic Label-B satisfaction + common robust-LCB and CLAP-to-original-prompt **proxy** floors + valid output/completion; no new human label; development pilot only. |
| Evidence / source commit | Scope: `orbit-research/adsr_phase2_20260604/paper_prep/tier3_bolt_20260715/BOLT_GATE15A_PREREG.md`; results: `orbit-research/adsr_phase2_20260604/paper_prep/tier3_bolt_20260715/BOLT_GATE15A_REPORT.md`, `orbit-research/adsr_phase2_20260604/paper_prep/tier3_bolt_20260715/BOLT_GATE15A_METRICS.json`, `orbit-research/adsr_phase2_20260604/paper_prep/tier3_bolt_20260715/BOLT_GATE15A_BOOTSTRAP.csv`, `orbit-research/adsr_phase2_20260604/paper_prep/tier3_bolt_20260715/BOLT_GATE15A_CROSSFIT_PREDICTIONS.csv`; source commit `a8c41822c5f451b8e64a3bb03f3a420431e4dfe4`; integrated by merge `758faae3c67c2137ad81b345ade9cc7530227e24`. |
| Applicable banned phrasing | `production controller`; `heldout validation`; `state is globally useless`; `oracle achieved`; `Gate 1.5B started`; `Gate 2 started`; `deployment result`. |

| Gate 1.5A statistic | Point | 95% interval | Unit / evidence |
|---|---:|---|---|
| Best static CQS | `0.776084869` | `[0.636819616, 0.890066433]` | prompt-cluster crossfit; Gate 1.5A report/metrics @ `a8c41822c5f451b8e64a3bb03f3a420431e4dfe4` |
| Prompt-only CQS | `0.783717358` | `[0.644032698, 0.897684730]` | same |
| Prompt+state CQS | `0.783717358` | `[0.644032698, 0.897684730]` | same |
| Prompt+state increment | `0.000000000` | `[0.000000000, 0.000000000]` | same |
| Nonstatic action share | `0.103913850` | CI not reported | `288` persisted states; same |
| Outcome-aware oracle upper bound | `0.931451613` | CI not reported here | development-only upper bound; same |
| Different selected actions | `25/288` | CI not reported | state unit; same |
| NFE changes without CQS changes | `16/288`; CQS changes `0/288` | CI not reported | state unit; same |
| Conditioning harmful | `13/48`; design-weighted `0.541186636` | `[0.381211547, 0.671261465]` | prompt unit; `orbit-research/adsr_phase2_20260604/paper_prep/tier3_bolt_20260715/BOLT_GATE15A_STRUCTURAL_REVERIFY.csv` @ same commit |
| Switch beats both restarts | `19/288`; design-weighted `0.041775474` | `[0.021582983, 0.067513571]` | state unit; same |

### 4.4 Probe and budget autopsy

| Required field | Inventory |
|---|---|
| Status | **EXPLORATORY** |
| Claim-ready sentence | The pre-W2 probe evidence was offline-positive but online-unconfirmed, and the tracked wall-clock headlines conflict; probe overhead is budget-material but no wall-clock headline is usable until cost accounting is pinned. |
| Exact numbers / unit | Music EVPD sigma-`0.8` heldout AUC `0.916` (paper-rounded `0.92`) with val-tuned threshold `0.728`; mel-summary AUC curve `0.872 → 0.916 → 0.940` at sigma `0.9 → 0.8 → 0.7`; lyrics correlation `0.06 → 0.68`; CIs not reported for these specific points. Offline winners: probe-on-evidence `-7%` and portfolio `-6%` steps/clean; online confirmation `78.9` versus `77.8` steps/clean; CIs are not reported for these steps-per-clean summaries. Process ledger `3,648` units / `22,825` attempts with `0` validation violations; non-probing arms were within `3–8.6%` of nominal compute. Gate-B timing says approximately `0.9 s/probe` versus `52 s/probe` and arm-3 `52 h` actual versus `2.7 h` nominal; CLAIMS notes a conflicting approximately `0.3/40 s` source. |
| Instrument / label provenance | Historical rows = pre-W2 **legacy** automatic detector + EVPD/quality **proxies**; Tier-3 structural rows = promoted-W2 automatic Label-B constraint + common robust-LCB and CLAP-to-original-prompt **proxy** floors + valid output/completion; no new human labels. |
| Evidence / source commit | `orbit-research/adsr_phase2_20260604/EVPD_MODEL_CARD.md`; `orbit-research/adsr_phase2_20260604/EVPD_RESULTS.json`; `orbit-research/adsr_phase2_20260604/GATE_B_FINAL_REPORT.md` @ `d84970bb611ac60976278e59308e31b2ca38e732`; conflict register `orbit-research/adsr_phase2_20260604/paper_prep/CLAIMS.md`; current live budget evidence `orbit-research/adsr_phase2_20260604/paper_prep/w2_execution_20260712/live_confirmation_20260713/LIVE_CONFIRM_REPORT.md` @ `86103d466d54a8c6363c6060074bb90442fdd30f`. |
| Applicable banned phrasing | `confirmed efficiency`; `cheap probe`; `free probe`; `broad deployability`; selecting either contested wall-clock number; treating nominal two-slot savings as rolled over. |

#### Gate-1 action-value-learning gate

| Required field | Inventory |
|---|---|
| Status | **EXPLORATORY** development-only gate. |
| Claim-ready sentence | In the frozen `48`-prompt development pilot, the outcome-aware tree oracle exceeded the best feasible static program, triggering `BOLT_GATE1 = GO_ACTION_VALUE_LEARNING` without establishing a learned or prospective policy result. |
| Exact numbers / unit | `48` prompts; `96` roots; `288` checkpoint states; `1,440` action outcomes; `1,248` unique decoded media; integrity errors `0`; best static CQS@60 `0.745199693` [95% CI `0.578804057`, `0.885492285`]; oracle `0.931451613` [`0.804382896`, `1.000000000`]; headroom `0.186251920`, one-sided 95% LCB `0.096069007`; matched-CQS compute saving `0.342115277`, LCB `0.275409155`; nonstatic prompt share `1.0` (CI not reported). Unit = development prompt/design-weighted outcome tree; `10,000` prompt-bootstrap replicates. |
| Instrument / label provenance | Constraint = promoted W2 automatic Label B; quality eligibility = automatic common robust-LCB and CLAP-to-original-prompt **proxy** floors + valid output/completion; oracle is outcome-aware; no new human labels. |
| Evidence / source commit | `orbit-research/adsr_phase2_20260604/paper_prep/tier3_bolt_20260715/BOLT_GATE1_REPORT.md`; `orbit-research/adsr_phase2_20260604/paper_prep/tier3_bolt_20260715/BOLT_ORACLE_HEADROOM_REPORT.md`; `orbit-research/adsr_phase2_20260604/paper_prep/tier3_bolt_20260715/BOLT_ORACLE_BOOTSTRAP.csv`; source commit `bc4e9444297efecddf88a225301a016b1d9c8a38`; integrated by merge `758faae3c67c2137ad81b345ade9cc7530227e24`. |
| Applicable banned phrasing | `learned controller`; `prospective policy`; `heldout validation`; `oracle achieved in deployment`; `Gate 2 started`; scientific efficacy. |

| Current structural autopsy | Exact result | Status / boundary | Evidence |
|---|---|---|---|
| Gate-1 static-to-oracle headroom | Best static CQS `0.745199693`, 95% CI `[0.578804057, 0.885492285]`; oracle upper `0.931451613` [`0.804382896, 1.000000000`]; headroom `0.186251920`, one-sided 95% LCB `0.096069007`; compute saving `0.342115277`, LCB `0.275409155`; nonstatic share `1.0` (CI not reported) | **EXPLORATORY** outcome-aware development upper bound | `orbit-research/adsr_phase2_20260604/paper_prep/tier3_bolt_20260715/BOLT_ORACLE_HEADROOM_REPORT.md`; `orbit-research/adsr_phase2_20260604/paper_prep/tier3_bolt_20260715/BOLT_ORACLE_BOOTSTRAP.csv` @ `bc4e9444297efecddf88a225301a016b1d9c8a38` |
| Gate-1.5A realizable state value | Prompt-only and prompt+state CQS both `0.783717358`; increment `0` [`0`, `0`] | **REDUCED** null; no production controller | Gate 1.5A report/metrics @ `a8c41822c5f451b8e64a3bb03f3a420431e4dfe4` |
| Live budget discard | Abort policy mean actual steps `38.90625` but frozen nominal budget `60`; unused savings not reassigned | **REDUCED** frozen failure | live results/report @ `86103d466d54a8c6363c6060074bb90442fdd30f` |
| Rollover static replay | True-rollover CQS `0.6289746544` versus frozen two-slot `0.7451996928` | **EXPLORATORY**; no prospective rerun | BOLT static table @ `bc4e9444297efecddf88a225301a016b1d9c8a38` |

### 4.5 CLAP prompt-fidelity diagnostic

| Required field | Inventory |
|---|---|
| Status | **REDUCED** |
| Claim-ready sentence | No clear CLAP prompt-fidelity drop was detected on average, but the prompt-bootstrap interval crossed zero and semantic preservation was not established. |
| Exact numbers / unit | Overall `256` prompts: arm6 minus arm1 mean `+0.005996`, median `+0.002001`, bootstrap 95% CI `[-0.003375, 0.015661]`; rare-basin `5` prompts: `-0.037730` [`-0.102102`, `0.026642`]; instrumental `97` prompts: `+0.004918` [`-0.005218`, `0.015662`]; vocal `159`: `+0.006654` [`-0.007347`, `0.020539`]. Unit = prompt; prompt bootstrap. |
| Instrument / label provenance | CLAP **proxy**, automatic; arm labels from legacy online evidence; no human quality label. |
| Evidence / source commit | `orbit-research/adsr_phase2_20260604/paper_prep/clap_fidelity/CLAP_FIDELITY_EXPANDED_REPORT.md`; `orbit-research/adsr_phase2_20260604/paper_prep/clap_fidelity/CLAP_FIDELITY_EXPANDED_RESULTS.csv`; source commit `d84970bb611ac60976278e59308e31b2ca38e732`. |
| Applicable banned phrasing | `semantic preservation proved`; `quality preserved`; `no quality loss`; CLAP as a human rating. |

### 4.6 Router replay negative

| Required field | Inventory |
|---|---|
| Status | **REDUCED** |
| Claim-ready sentence | Cross-validated offline replay did not support a deployable router because the selected threshold policy did not beat always-recondition with a positive interval. |
| Exact numbers / unit | Five deterministic folds; prompt bootstrap. Oracle upper `0.986547` [95% CI `0.975618`, `0.994350`], delta versus always `0.012092` [`0.002834`, `0.023730`]; always-recondition `0.974455` [`0.955013`, `0.989659`]; CV threshold `0.970018` [`0.950094`, `0.985903`], delta `-0.004437` [`-0.011659`, `0.002068`]; CV direction threshold `0.966294` [`0.944872`, `0.984116`], delta `-0.008161` [`-0.019007`, `0.000721`]. Unit = heldout prompt within cross-validation. |
| Instrument / label provenance | Offline replay using **legacy** automatic clean labels and policy **proxies**; no live deployment or human labels. |
| Evidence / source commit | `orbit-research/adsr_phase2_20260604/paper_prep/router_replay/ROUTER_REPLAY_CV_REPORT.md`; `orbit-research/adsr_phase2_20260604/paper_prep/router_replay/ROUTER_REPLAY_CV_RESULTS.csv`; source commit `d84970bb611ac60976278e59308e31b2ca38e732`. |
| Applicable banned phrasing | `deployable router`; `live router validation`; `router beats always-recondition`; `oracle achieved`; promoted-OR live result. |

## 5. Reproducibility & governance assets

### 5.1 Bit-exact spine regeneration

| Required field | Inventory |
|---|---|
| Status | **PRIMARY** reproducibility asset. |
| Claim-ready sentence | In the pinned torch/torchaudio `2.5.1+cu121` recovery environment, all `4,096` spine tasks were regenerated and scored with no missing, invalid, or near-silent outputs; decoded-audio equality was `1/1` for the surviving target and `50/50` controls. |
| Exact numbers / unit | Manifest `4,096`; reconstructed missing `4,095` plus `1` survivor; generated/scored `4,096`; missing/invalid/near-silent `0/0/0`; sample rate `48,000 Hz`; duration range `29.907312–74.675375 s`; legacy-label flips `15/4,096`; equality comparisons `51`. CI = N/A, deterministic audit. |
| Instrument / label provenance | Regeneration identity = decoded-audio hash; scoring = **legacy** historical label comparison; automatic provenance. |
| Evidence / source commit | `orbit-research/adsr_phase2_20260604/paper_prep/w2_execution_20260712/spine_reconstruction_torch251_recovery/SPINE_RECONSTRUCTION_AUDIT.md`; `orbit-research/adsr_phase2_20260604/paper_prep/w2_execution_20260712/spine_reconstruction_torch251_recovery/SPINE_RECONSTRUCTION_AUDIT.json`; source commit `a332581f511acbeb9b292fca839295d0503fe72f`; fidelity probe `orbit-research/adsr_phase2_20260604/paper_prep/w2_execution_20260712/spine_torch251_fidelity_probe/SPINE_TORCH251_FIDELITY_REPORT.md`. |
| Applicable banned phrasing | `bit-exact across environments`; `independent samples`; `old torch package equivalent`; hiding the `15/4,096` historical-label flips. |

### 5.2 Tier-3 BOLT Gate 0 primitive validation

| Required field | Inventory |
|---|---|
| Status | **PRIMARY** reproducibility/engineering asset; no scientific-efficacy claim. |
| Claim-ready sentence | The Tier-3 BOLT Gate 0 deterministic controls passed environment parity, resume, condition switch, fork, actual-NFE, true-rollover, completion-reserve, and zero-score-selection checks. |
| Exact numbers / unit | Standard-generation NFE `45`; pilot budget NFE `90`; resume controls `48/48`; Label-B flips `0`; quality-floor flips `0`; true-rollover remaining-budget trace `73 → 56 → 11`, total NFE `90`, valid completed candidates `1`; scheduler-equivalent trace `60 → 48 → 36 → 30`; fork eta `0.025`. CI = N/A for deterministic engineering controls. |
| Instrument / label provenance | Constraint checks = promoted-W2 automatic Label B; quality eligibility = automatic common robust-LCB and CLAP-to-original-prompt **proxy** floors + valid output/completion; no new human labels. |
| Evidence / source commit | `orbit-research/adsr_phase2_20260604/paper_prep/tier3_bolt_20260715/BOLT_GATE0_REPORT.md`; `orbit-research/adsr_phase2_20260604/paper_prep/tier3_bolt_20260715/BOLT_RESUME_EQUIVALENCE.csv`; `orbit-research/adsr_phase2_20260604/paper_prep/tier3_bolt_20260715/BOLT_FORK_CALIBRATION.csv`; source commit `bc302b6feb6ebf72732a7312c5bd710bc03b51f8`; integrated by merge `758faae3c67c2137ad81b345ade9cc7530227e24`. |
| Applicable banned phrasing | scientific efficacy; heldout validation; deployment readiness; production controller; `rollover rescued live confirmation`; independent samples. |

### 5.3 Seed registries

| Required field | Inventory |
|---|---|
| Status | **PRIMARY** governance asset. |
| Claim-ready sentence | Frozen seed allocations are recorded in the append-only project and Tier-3 registries with collision checks; run reports, not freeze-time reservation labels, determine completion status. |
| Exact registry ranges / unit | T2 replay `2026052700–2026563707`; T8 SA3 replay `2026070800–2026120707`, selection seed `20260709`; T10 tail base `2031000000` and warm-restart base `2032000000`, both `RESERVED`; v1.5 prevalence `2033000000–2033001023`, retry `2033010000–2033010511`, intervention `2033020000–2033020127`, smoke `2033090000–2033090001`; W2 factorial `2034000000–2034031015`; live `2035000000–2035006301`; unconditional `2036000000–2036000255`; Tier-3 requested base `2040000000` rejected, `[2050000000, 2060000000)` occupied, selected base `2060000000`, pilot seeds below `2065000000`, Gate-0 engineering `2069000000`, fork calibration `2069500000`; neutral `2071000000–2071023007`; v1.5 rescue `2072000000–2072000063`, used suffixes `16–17`; unit = deterministic seed ID. CI = N/A. |
| Instrument / label provenance | Governance metadata only; no label. |
| Evidence / source commit | `orbit-research/adsr_phase2_20260604/paper_prep/SEED_REGISTRY.md` @ `788e366626f830fbd4a2bf1be67848095e160074`; v1.5 used suffixes: `orbit-research/adsr_phase2_20260604/paper_prep/rescue_v15_gate0_20260717/V15_RUN_MANIFEST.json` @ `24af75fb0eaeab96d13689e3ab12d017fc4a1f5a`; `orbit-research/adsr_phase2_20260604/paper_prep/tier3_bolt_20260715/BOLT_SEED_REGISTRY.md`; `orbit-research/adsr_phase2_20260604/paper_prep/tier3_bolt_20260715/BOLT_SEED_COLLISION_AUDIT.json` @ Tier-3 source tip `03c132592d54baac0feee8be7c5f49c39b910d5a`; integrated by merge `758faae3c67c2137ad81b345ade9cc7530227e24`. |
| Applicable banned phrasing | freeze-time `RESERVED` status as current run status; seed range as evidence of completion; unregistered seed substitution. |

### 5.4 Preregistrations and freezes

| Required field | Shared inventory |
|---|---|
| Status | **PRIMARY** governance assets. |
| Claim-ready sentence | The tracked preregistrations and runtime freezes pin inputs, estimands, policies, seeds, and engineering contracts before their corresponding readouts. |
| Exact numbers / unit | Unit = one tracked freeze artifact; CI = N/A; experiment-specific sample counts remain attached to the corresponding evidence items in Sections 2–4. |
| Instrument / label provenance | Governance metadata; no new label. Instrument and label provenance remain those frozen in each asset. |
| Evidence / source commit | Per-asset paths and source commits below. |
| Applicable banned phrasing | `retrospective preregistration`; `post-hoc primary`; treating a freeze as evidence that a run completed or passed. |

| Status | Frozen asset | Evidence path / source commit | Applicable banned phrasing |
|---|---|---|---|
| **PRIMARY** governance | Unconditional base-rate inputs reused by v2 | `analysis_exit1/UNCONDITIONAL_PREREGISTRATION.json` @ `3e391303464d10e0f7eaafbd840d615e49da6a4c` | `v2 inputs selected post-hoc`; historical AND rule as primary |
| **PRIMARY** governance | Population retry | `orbit-research/adsr_phase2_20260604/paper_prep/POPULATION_RETRY_PREREG_20260707.md` @ `d84970bb611ac60976278e59308e31b2ca38e732` | `retrospective design` |
| **PRIMARY** governance | Stage-3 intervention | `orbit-research/adsr_phase2_20260604/paper_prep/STAGE3_INTERVENTION_PREREG_20260707.md` @ `d84970bb611ac60976278e59308e31b2ca38e732` | `post-hoc primary endpoint` |
| **PRIMARY** governance | Human-study frozen criteria | `orbit-research/adsr_phase2_20260604/paper_prep/HUMAN_STUDY_CRITERIA_FROZEN.md` @ `d84970bb611ac60976278e59308e31b2ca38e732` | post-hoc A-prime/B-prime gate wording |
| **PRIMARY** governance | Human-study signed amendment and signature record | `orbit-research/adsr_phase2_20260604/paper_prep/HUMAN_STUDY_CRITERIA_AMENDMENT_20260709.md` @ `41d130cc300fb9e650f1a7ca8ff2e12e96e1d444`; `orbit-research/adsr_phase2_20260604/paper_prep/HUMAN_STUDY_CRITERIA_AMENDMENT_SIGNATURE_20260710.md` @ `cd0d24ecdcd52b79c6f5d5bf55fbe85db7cc7093` | unsigned criteria; omitting amendment provenance |
| **PRIMARY** governance | Human-study T4 deviation appendix | `orbit-research/adsr_phase2_20260604/paper_prep/HUMAN_STUDY_CRITERIA_AMENDMENT_20260709_APPENDIX_20260712.md` @ `e30f40f9f9ee14ff07557f6b17e205fb174dfcb8` | T4 as later-day independent reliability |
| **PRIMARY** governance | Dispatch-A evaluator amendment | `analysis_exit1_v2/DISPATCH_A_AMENDMENTS.md` @ `1af4a8a90666c43451dcc27b40af7396693c6bf7`; corrected v2 evaluator artifacts supersede the first v2 attempt | first v2 attempt as canonical; fixed-AND primary |
| **PRIMARY** governance | W2 amendment | `orbit-research/adsr_phase2_20260604/paper_prep/W2_AMENDMENT_20260712.md` @ `86103d466d54a8c6363c6060074bb90442fdd30f` | `unsigned amendment`; obsolete signature gating after D-001/D-002 |
| **PRIMARY** governance | Factorial | `orbit-research/adsr_phase2_20260604/paper_prep/w2_execution_20260712/factorial/FACTORIAL_PREREGISTRATION.md` @ `efd4dbec615eef7453405890e388fabfae6d5cde` | invalid positive cohort as primary |
| **PRIMARY** governance | Neutral control | `analysis_exit1_v2/neutral_control/NEUTRAL_PREREGISTRATION.json` @ neutral-control history ending `d96f33999be1921bc370e5b6b8d02f0256fc8ccb` | generalization beyond frozen subset |
| **PRIMARY** governance | Live policy freeze | `orbit-research/adsr_phase2_20260604/paper_prep/w2_execution_20260712/evpd_liveconfirm_torch251_recovery/LIVE_CONFIRM_POLICY_FREEZE.json` @ `a332581f511acbeb9b292fca839295d0503fe72f` | post-hoc live PASS |
| **PRIMARY** governance | Tier-3 Gates 0/1 | `orbit-research/adsr_phase2_20260604/paper_prep/tier3_bolt_20260715/BOLT_GATE01_PREREG.md` @ Tier-3 source tip `03c132592d54baac0feee8be7c5f49c39b910d5a` | heldout/deployment claim |
| **PRIMARY** governance | Tier-3 fork contract | `orbit-research/adsr_phase2_20260604/paper_prep/tier3_bolt_20260715/BOLT_FORK_FREEZE.json` @ `bc302b6feb6ebf72732a7312c5bd710bc03b51f8` | changing the passing fork contract after Gate 0 |
| **PRIMARY** governance | Tier-3 runtime contract | `orbit-research/adsr_phase2_20260604/paper_prep/tier3_bolt_20260715/BOLT_RUNTIME_FREEZE.json` @ `bc302b6feb6ebf72732a7312c5bd710bc03b51f8` | cross-environment equivalence without validation |
| **PRIMARY** governance | Tier-3 Gate 1.5A | `orbit-research/adsr_phase2_20260604/paper_prep/tier3_bolt_20260715/BOLT_GATE15A_PREREG.md` @ `a8c41822c5f451b8e64a3bb03f3a420431e4dfe4` | expanded scope or later-gate claim |
| **PRIMARY** governance | v1.5 Gate 0 | `orbit-research/adsr_phase2_20260604/paper_prep/rescue_v15_gate0_20260717/V15_GATE0_PREREGISTRATION.json` @ `24af75fb0eaeab96d13689e3ab12d017fc4a1f5a` | scientific result from failed engineering gate |

### 5.5 Human-rating inventory

| Required field | Inventory |
|---|---|
| Status | **PRIMARY** provenance inventory; legacy CXY rows are **SENSITIVITY_ONLY**. |
| Claim-ready sentence | The human evidence is a set of explicitly provenance-labeled PI bundles from a single expert rater; validated-judge supplements remain automatic and are not counted as human ratings. |
| Unit / interval | Unit = rating presentation or pair as specified per bundle; counts only, CI = N/A. |
| Instrument / label provenance | Human bundles = PI `pi:Richard`; legacy inventory = `human:CXY`; judge supplement = automatic **judge**. |
| Evidence / source commit | Bundle construction: `orbit-research/adsr_phase2_20260604/paper_prep/rater_bundles_20260711/BUNDLE_JOB_REPORT_20260711.md`; `orbit-research/adsr_phase2_20260604/paper_prep/rater_bundles_20260711/BUNDLE_AUDIT.json` @ `b093462f4a12f5dec68de93098393e8e6fb68128`; ingestion audits listed below. |
| Applicable banned phrasing | `multiple independent human raters`; `judge labels are human`; `500 human supplemental ratings`; combining CXY and PI without provenance; treating staged/unscored bundle as completed. |

| Bundle / provenance | Count and composition | Evidence / source commit | Status |
|---|---|---|---|
| T1 decisive v2 / PI | `42` rating rows/media; `12` amended | `orbit-research/adsr_phase2_20260604/paper_prep/pi_ratings_20260711/processed/PI_RATING_INGEST_AUDIT.json` @ `2a58eee0810012ea3affc150697619b16f36e6ff` | **PRIMARY** |
| T2 A-prime core / PI | `190` ratings = `112` disagreement + `48` rare + `30` controls; Label A `177` yes / `12` no / `1` unsure | same audit/commit | **PRIMARY** |
| T3 B-prime primary v2 / PI | `80` rows / `160` media | `orbit-research/adsr_phase2_20260604/paper_prep/pi_ratings_20260712/processed/DROP2_INGEST_AUDIT.json` @ `e30f40f9f9ee14ff07557f6b17e205fb174dfcb8` | **PRIMARY** |
| T4 B-prime reverse v2 / PI | `24` rows / `48` media; same-session deviation | same audit/commit | **SENSITIVITY_ONLY** |
| T5 SA3 calibration / PI | `60/60` ratings; `59` optional-confidence blanks | same audit/commit | **REDUCED** |
| T6 / PI | `201` presentations = train `60` + heldout `100` + repeats `20` + transport `20` + appendix `1`; `180` unique + `20` repeats + appendix | `orbit-research/adsr_phase2_20260604/paper_prep/autochain_20260712/T6_INGEST_AUDIT.json` @ `168d12f1e47f555c85b7b9085da947b5ef261835` | **PRIMARY** |
| T7 / PI | `40` blinded unique instrumental clips; Label A all `no`; optional Label-B blanks `2`; confidence blanks `40`; minimum-negative-count top-up manifest consumed `23` and left `17`, while final pooled validation used all `40` T7 negatives | `orbit-research/adsr_phase2_20260604/paper_prep/t7_judge_gold_20260713/ratings_ingest/T7_RATINGS_INGEST_AUDIT.json`; `orbit-research/adsr_phase2_20260604/paper_prep/t7_judge_gold_20260713/judge_completion/POOLED_DISJOINT_GOLD_MANIFEST.csv` @ `65094d43d0e19777caa0626c31a266a2869b5911` | **PRIMARY** |
| Pooled judge gold / PI reference, judge output | `216` PI-gold clips = `149` yes + `67` no; `3` automatic calls/clip | pooled judge report @ `65094d43d0e19777caa0626c31a266a2869b5911` | **REDUCED** automatic judge |
| A-prime judge supplement / judge | `500` rating IDs; `493` unique media hashes | A-prime report/merged audit @ `65094d43d0e19777caa0626c31a266a2869b5911` | **REDUCED** automatic judge |
| Legacy CXY | `282` nonprimary rows = `80` AB + `112` adjudication + `60` rare + `30` spotcheck; judge gold `176`, heldout `37` | `orbit-research/adsr_phase2_20260604/paper_prep/legacy_human_results_20260710/LEGACY_INGEST_AUDIT.json` @ `7f96712a3392ae72e829c2364029421b632741fd` | **SENSITIVITY_ONLY** |
| Factorial PI spotcheck | `20` pairs staged; `0` scored | `orbit-research/adsr_phase2_20260604/paper_prep/w2_execution_20260712/factorial/FACTORIAL_PI_SPOTCHECK_MANIFEST.csv` @ `25a4853e7e5f0894cac0d551c2ef9ce422fea594` | **EXPLORATORY** / open |
| SA3 intervention-fidelity pairs / intended PI | `20` pairs staged; `0` scored; no obtained PI labels | `orbit-research/adsr_phase2_20260604/paper_prep/sao/stable_audio_3_medium/intervention_fidelity/blinded_pairs/SA3_INTERVENTION_PAIRS_RATINGS.csv` @ `1f7fa915517f15445a0bd82b6366d488bc89fbef` | **EXPLORATORY** / open |

### 5.6 Governance closeout and append-only records

| Required field | Inventory |
|---|---|
| Status | **PRIMARY** governance asset. |
| Claim-ready sentence | Governance closeout retired signature rounds while retaining frozen preregistration, supersede-don't-overwrite, and provenance-label rules, and W2 adoption was executed under Chief-Scientist authority. |
| Exact status / unit | `D-001 = EXECUTED`; `D-002 = EXECUTED`; `W2_ADOPTION = EXECUTED`; `PLAN_CLAIMS_SUPERSESSION = APPLIED`; unit = append-only decision entry; CI = N/A. |
| Instrument / label provenance | Governance metadata; authority labels = PI and Chief-Scientist. |
| Evidence / source commit | `orbit-research/adsr_phase2_20260604/paper_prep/DECISIONS.md`; `orbit-research/adsr_phase2_20260604/paper_prep/autochain_20260712/T6_PROMOTION_ESCALATION.md`; `orbit-research/adsr_phase2_20260604/paper_prep/PLAN.md`; `orbit-research/adsr_phase2_20260604/paper_prep/CLAIMS.md`; closeout commit `00fe296cabcf25f96b35d21bef7b507d42418085`. Applied drafts: `orbit-research/adsr_phase2_20260604/paper_prep/autochain_20260712/recompute/PLAN_UPDATE_DRAFT.md` and `orbit-research/adsr_phase2_20260604/paper_prep/autochain_20260712/recompute/CLAIMS_UPDATE_DRAFT.md` @ `168d12f1e47f555c85b7b9085da947b5ef261835`. |
| Applicable banned phrasing | `awaiting signature`; `W2 adoption blocked`; deleting historical blockers; provenance-free relabeling; overwriting frozen reports. |

### 5.7 Release-asset inventory

| Required field | Inventory |
|---|---|
| Status | **REDUCED** |
| Claim-ready sentence | The release keep manifest tracks `1,342` retained FLAC rows and the tracked secret-hygiene audit records `SECRET_STATUS = CLEAN`; final hosting and package assembly are incomplete. |
| Exact numbers / unit | `1,342` manifest data rows (`1,343` CSV lines including header); secret scan status `CLEAN`; unit = retained-file manifest row / release audit; CI = N/A. |
| Instrument / label provenance | Release metadata only; retained labels are historical **legacy/automatic** fields and are not new annotations. |
| Evidence / source commit | `orbit-research/adsr_phase2_20260604/paper_prep/storage_triage/RELEASE_KEEP_MANIFEST.csv`; `orbit-research/adsr_phase2_20260604/paper_prep/RELEASE_SECRET_HYGIENE_20260707.md`; source commit `d84970bb611ac60976278e59308e31b2ca38e732`. |
| Applicable banned phrasing | `all raw audio released`; `public package complete`; `final hosting complete`; release manifest as a scientific sample frame. |

## 6. Master limitations + banned-wording register

| Scope | Required limitation / allowed boundary | Banned wording | Canonical evidence / commit |
|---|---|---|---|
| Population | Every prevalence/intervention estimate is instrument-scoped and design-scoped to its frozen cohort. | `generic population rate`; `ground truth`; universal prevalence | `orbit-research/adsr_phase2_20260604/paper_prep/CLAIMS.md` @ closeout `00fe296cabcf25f96b35d21bef7b507d42418085`; corrected report @ `168d12f1e47f555c85b7b9085da947b5ef261835` |
| Primary backbone | Corrected primary phenomenon and intervention evidence is ACE-Step v1; ACE-Step v1.5 remains a separate engineering-limited replication attempt. | pooling v1/v1.5; broad backbone robustness; v1.5 scientific confirmation | corrected W2 evidence @ `168d12f1e47f555c85b7b9085da947b5ef261835`; v1.5 @ `8cba0f5882f51b010e912e3f54d15f2246f6e695` / `24af75fb0eaeab96d13689e3ab12d017fc4a1f5a` |
| Causality | Observed request-direction and condition contrasts are descriptive unless the frozen paired design and endpoint support the narrower contrast. | `causal vocal-generation bias`; generic `bias`; `negation causes violations` | corrected report/factorial/neutral sources listed in Sections 2–3 |
| Instrument primacy | Promoted `or` is primary; legacy detector and historical `and` are sensitivity-only. | historical-AND number as primary; `legacy detector validated`; `A-prime PASS` | T6 promotion @ `168d12f1e47f555c85b7b9085da947b5ef261835`; A-prime @ `9723bcf869987e55024dc7081f511146c9f88852` |
| Label scope | A-prime tests perceived voice-presence Label A; T6 supports the request-conditional corrected endpoint and repeat reliability for both labels. | conflating A-prime with T6; claiming A-prime validates/invalidates paper-primary Label B | A-prime report @ `9723bcf869987e55024dc7081f511146c9f88852`; T6 report @ `86103d466d54a8c6363c6060074bb90442fdd30f` |
| Evaluator panels | Panel A is PI-only and power-limited; Panel B is PI+validated-judge supplemental. | `Panel A adequately powered`; `Panel B human-only`; Panel-B legacy BA as validation; T6/panel conflation | evaluator comparison @ `026572302d0d31a491b2b40e100c3344bba37167` |
| Judge | Majority-voted judge calls have automatic provenance and clip-level statistical units. | judge output as human rating; each call as independent sample; Label-B validation | pooled judge @ `65094d43d0e19777caa0626c31a266a2869b5911` |
| AudioSet | Exact human-voice whitelist only. | substring whitelist; synthetic/nonhuman vocalization as human voice; proxy as annotation | AudioSet audit @ `026572302d0d31a491b2b40e100c3344bba37167` |
| Difficulty | Use corrected continuous prompt ECDFs. | retrospective hard bins; `impossible to retry`; `1/mean(p)` expected draws | corrected prompt ECDF @ `168d12f1e47f555c85b7b9085da947b5ef261835` |
| Neutral control | CI includes zero within the selected subset; one studio descriptor was assumed vocally inert; token-count equality is not semantic equivalence; neutral seeds are independent and paired only by prompt; the positive contextual row is not a pure same-base control. | `negative wording has no effect`; `neutral rules out dilution`; semantic matching; noise-paired neutral control; generalization beyond selected `24/32` | neutral report @ `d96f33999be1921bc370e5b6b8d02f0256fc8ccb` |
| Factorial | Positive cells were corrected; proxy-quality columns are not human quality. | initial invalid positive cohort as primary; universal winner; `proved no loss` | factorial scoring/correction @ `168d12f1e47f555c85b7b9085da947b5ef261835` |
| Recipe | `N=4` is the first lowest observed violation point; quality is `PROXY_QUALIFIED_SUCCESS`; no recommendation. | deployable/best operating point; genuine qualified success; no quality loss | recipe v2 @ `026572302d0d31a491b2b40e100c3344bba37167` |
| Live confirmation | Frozen result is `CRITERIA_NOT_ALL_MET`; two-slot savings are discarded; the cohort is a frozen, failure-prone weighted set, so between-policy contrasts are valid only within that design. | live PASS; router win; actual-step post-hoc PASS; rollover repaired live result; generic deployment rate | live report @ `86103d466d54a8c6363c6060074bb90442fdd30f` |
| Quality | B-prime noninferiority was not established; single expert, `40%` ties, pre-W2 selection, same-session T4. | `no quality loss`; `no degradation`; `quality preserved` | B-prime @ `c682212c5039582e62d9ec4493822f42fe578d57` |
| Proxies | CLAP/Audiobox/PickScore/OWLv2/CQS quality components are diagnostics. | human quality; semantic preservation proved; proxy = ground truth | recipe, SA3, SDXL, Tier-3 sources listed above |
| Cross-model | v1.5 and SA3 are bounded/reduced pilots; SDXL is cross-modal exploratory. | broad second-backbone robustness; full cross-modal replication; pooling models | v1.5 @ `8cba0f5882f51b010e912e3f54d15f2246f6e695`; SA3/SDXL @ `d84970bb611ac60976278e59308e31b2ca38e732` |
| Gate 1.5A | Development-only, cross-fitted null on frozen states/outcomes. | production controller; heldout/generalization; global `state useless`; oracle achieved | Gate 1.5A @ `a8c41822c5f451b8e64a3bb03f3a420431e4dfe4` |
| Probe cost | Cost headlines conflict and remain unusable. | cheap/free probe; confirmed efficiency; choosing a contested timing | Gate-B @ `d84970bb611ac60976278e59308e31b2ca38e732`; CLAIMS current history |
| Reproducibility | Bit-exact only in the pinned `2.5.1+cu121` recovery environment. | bit-exact across environments; independent samples | spine recovery @ `a332581f511acbeb9b292fca839295d0503fe72f` |
| Human provenance | One PI expert plus explicitly separated legacy CXY; judge supplement automatic. | multiple independent PI raters; judge as human | ingestion audits listed in Section 5.5 |
| Release | The keep manifest and secret audit are staging assets; hosting/package completion remains open. | all raw audio released; final public package complete; release rows as new labels | release assets in Section 5.7 @ `d84970bb611ac60976278e59308e31b2ca38e732` |
| Governance | Supersede append-only; preserve frozen artifacts and provenance labels. | overwrite/delete old evidence; adoption still blocked; provenance-free supersession | decision log/PLAN/CLAIMS/escalation @ `00fe296cabcf25f96b35d21bef7b507d42418085` |

## 7. STALE-NUMBER TRAP LIST

| Headline / endpoint | Old value and tier | Current value and tier | Canonical current source / commit | Writer control |
|---|---|---|---|---|
| Unconditional voice-present, overall | Historical AND `171/256 = 66.80%` [`60.82%`, `72.28%`], **SENSITIVITY_ONLY** | Promoted OR `187/256 = 73.05%` [`67.30%`, `78.11%`], **PRIMARY** | `analysis_exit1_v2/UNCONDITIONAL_BASE_RATE_V2.csv` @ `026572302d0d31a491b2b40e100c3344bba37167` | Cite `73.1%`, never `66.8%`, as the current headline. |
| Unconditional voice-present, empty | Historical AND `91/128 = 71.09%` [`62.72%`, `78.24%`], **SENSITIVITY_ONLY** | Promoted OR `98/128 = 76.56%` [`68.52%`, `83.06%`], **PRIMARY** | same | Do not mix rule families. |
| Unconditional voice-present, neutral | Historical AND `80/128 = 62.50%` [`53.86%`, `70.41%`], **SENSITIVITY_ONLY** | Promoted OR `89/128 = 69.53%` [`61.08%`, `76.84%`], **PRIMARY** | same | Do not mix rule families. |
| Evaluator Panel-B fixed-rule comparator | Historical fixed AND BA `0.8551167582` [`0.7917019526`, `0.9174765265`], sensitivity `0.8245192308`, specificity `0.8857142857`, **SENSITIVITY_ONLY** | Promoted OR Panel-B BA `0.8000000000` [`0.7000000000`, `0.9000000000`], sensitivity `1.0000000000`, specificity `0.6000000000`, **SENSITIVITY_ONLY**; paper promotion headline is separately T6 BA `0.9873081909`, **PRIMARY** | `analysis_exit1_v2/EVALUATOR_COMPARISON_TABLE.md` @ `026572302d0d31a491b2b40e100c3344bba37167`; T6 report @ `168d12f1e47f555c85b7b9085da947b5ef261835` | Never substitute an evaluator-panel BA for T6 or retain fixed-AND as canonical. |
| Judge Label-A validation | Pre-top-up `n=176` (`149` yes / `27` no), BA `0.9479822191` [`0.8937421409`, `0.9996692569`], LCB `0.9003600682`, `BLOCKED_CLASS_COUNT_TOPUP_REQUIRED` | Final pooled `n=216` (`149` yes / `67` no), BA `0.9507049554` [`0.9390758992`, `0.9602832030`], LCB `0.9411129930`, `PASS` | `orbit-research/adsr_phase2_20260604/paper_prep/autochain_20260712/judge_aprime/JUDGE_LABEL_A_VALIDATION.json` @ `168d12f1e47f555c85b7b9085da947b5ef261835`; `orbit-research/adsr_phase2_20260604/paper_prep/t7_judge_gold_20260713/judge_completion/POOLED_JUDGE_VALIDATION.json` @ `65094d43d0e19777caa0626c31a266a2869b5911` | Cite final `n=216`; do not call the statistically strong but class-count-blocked `n=176` state final. |
| AudioSet Panel-B sensitivity | Whitelist-superset `0.9567307692` | Exact whitelist `0.9543269231` [`0.9302949062`, `0.9760011976`] | `analysis_exit1_v2/EVALUATOR_COMPARISON_TABLE.md`; AudioSet audit @ `026572302d0d31a491b2b40e100c3344bba37167` | Cite exact-whitelist value. |
| AudioSet Panel-B balanced accuracy | Whitelist-superset `0.8640796703` [`0.7611646573`, `0.9572737761`] | Exact whitelist `0.8628777473` [`0.7598230845`, `0.9558036220`] | same | Cite exact-whitelist value. |
| AudioSet Panel-B MCC | Whitelist-superset `0.6500366429`; TP/FN `398/18` | Exact whitelist `0.6416003504` [`0.4689900204`, `0.8048917021`]; TP/FN `397/19` | same | Cite corrected confusion state. |
| A-prime disagreement cardinality | Intended `112` Demucs-vs-PANNs → stale `100` Demucs-vs-Whisper → global-dedup `92` → path-reclassified package bucket `82` | Reconciled primary gate universe `112/112` original-media Demucs-vs-PANNs cases; overlap with stale construct `45`, intended-only `67`, stale-only `55` | `orbit-research/adsr_phase2_20260604/paper_prep/validation_A_prime/A_PRIME_CARDINALITY_REPORT.md`; `orbit-research/adsr_phase2_20260604/paper_prep/validation_A_prime/A_PRIME_CARDINALITY_RECONCILIATION.csv` @ `a5a60232e24deeaa4152d77dc4e4e4b1f143eeb1` | The `112 → 100 → 92 → 82` chain is construct substitution/dedup/reclassification drift, not sample attrition. |
| Spine instrumental violation | Legacy apparent `25.9566%` [`23.8473%`, `28.1834%`], **SENSITIVITY_ONLY** | Calibrated M2 `38.6485%` [`32.2633%`, `47.3812%`], **PRIMARY** publication estimate; direct promoted-OR `52.3597%` [`49.8849%`, `54.8230%`], mechanical readout | `orbit-research/adsr_phase2_20260604/paper_prep/autochain_20260712/recompute/CORRECTED_PUBLICATION_RATES.csv` @ `168d12f1e47f555c85b7b9085da947b5ef261835` | Label direct versus calibrated endpoint explicitly. |
| Spine vocal violation | Legacy apparent `21.2025%` [`19.6535%`, `22.8390%`], **SENSITIVITY_ONLY** | Calibrated M2 `0.2311%` [`0.0352%`, `0.3905%`], **PRIMARY** publication estimate; direct promoted-OR `0.2373%` [`0.1088%`, `0.5169%`], mechanical readout | same | Never cite old apparent rate as corrected. |
| N2 instrumental violation | Legacy apparent `23.8863%` [`22.8257%`, `24.9802%`], **SENSITIVITY_ONLY** | Calibrated M2 `39.2425%` [`30.3896%`, `50.6191%`], **PRIMARY** publication estimate; direct promoted-OR `51.6456%` [`50.3822%`, `52.9069%`], mechanical readout | same | Retire legacy headline. |
| N2 vocal violation | Legacy apparent `59.8690%` [`58.9199%`, `60.8066%`], **SENSITIVITY_ONLY** | Calibrated M2 `0.8296%` [`0.0359%`, `1.1200%`], **PRIMARY** publication estimate; direct promoted-OR `1.2539%` [`1.0570%`, `1.4868%`], mechanical readout | same | Retire legacy headline. |
| Stage-3 `instr_both` violation | Legacy apparent `62.2917%`, **SENSITIVITY_ONLY** | Calibrated M2 `93.2153%` [`85.2467%`, `98.0422%`], **PRIMARY** publication estimate; direct promoted-OR `98.4375%` [`97.4380%`, `99.0509%`], mechanical readout | corrected publication CSV @ `168d12f1e47f555c85b7b9085da947b5ef261835` | Label as violation, not clean rate. |
| Stage-3 `instr_sampler` violation | Legacy apparent `65.5208%`, **SENSITIVITY_ONLY** | Calibrated M2 `78.6297%` [`72.5939%`, `84.1458%`], **PRIMARY**; direct promoted-OR `83.3333%` [`80.8440%`, `85.5570%`], mechanical readout | same | same |
| Stage-3 `instr_text` violation | Legacy apparent `67.3958%`, **SENSITIVITY_ONLY** | Calibrated M2 `80.7173%` [`73.4370%`, `87.7156%`], **PRIMARY**; direct promoted-OR `86.7708%` [`84.4803%`, `88.7682%`], mechanical readout | same | same |
| Stage-3 `vocal_both` violation | Legacy apparent `22.0588%`, **SENSITIVITY_ONLY** | Calibrated M2 `0.1710%` [`0.0212%`, `0.4084%`], **PRIMARY**; direct promoted-OR `0.2757%` [`0.0938%`, `0.8075%`], mechanical readout | same | same |
| Stage-3 `vocal_guidance` violation | Legacy apparent `21.8750%`, **SENSITIVITY_ONLY** | Calibrated M2 `0.0678%` [`0.0212%`, `0.1736%`], **PRIMARY**; direct promoted-OR `0%` [`0%`, `0.3518%`], mechanical readout | same | Zero is cohort/instrument-scoped, not impossibility. |
| Stage-3 `vocal_hints` violation | Legacy apparent `90.6250%`, **SENSITIVITY_ONLY** | Calibrated M2 `1.9042%` [`0.0296%`, `2.9839%`], **PRIMARY**; direct promoted-OR `3.4926%` [`2.5551%`, `4.7575%`], mechanical readout | same | same |
| Factorial plain | Candidate/AND violation `0.568359` [`0.472656`, `0.662109`], **SENSITIVITY_ONLY** | Direct promoted-OR satisfaction `0.33984375`, **PRIMARY** (CI not reported); calibrated satisfaction `0.4384056893` [`0.3542909483`, `0.5254340453`], **EXPLORATORY** | `orbit-research/adsr_phase2_20260604/paper_prep/autochain_20260712/factorial/FACTORIAL_CONDITION_RESULTS.csv` @ `168d12f1e47f555c85b7b9085da947b5ef261835` | Endpoint and rule changed; do not compare as the same estimand. |
| Factorial negative text | Candidate/AND violation `0.619141` [`0.539062`, `0.699219`], **SENSITIVITY_ONLY** | Direct satisfaction `0.263671875`, **PRIMARY** (CI not reported); calibrated `0.3876462148` [`0.3164786460`, `0.4574563351`], **EXPLORATORY** | same | same |
| Factorial positive text | Candidate/AND violation `0.353516` [`0.263672`, `0.443359`], **SENSITIVITY_ONLY** | Direct satisfaction `0.552734375`, **PRIMARY** (CI not reported); calibrated `0.6608059215` [`0.5668142543`, `0.7477994554`], **EXPLORATORY** | same | same |
| Factorial sampler only | Candidate/AND violation `0.552734` [`0.445312`, `0.658203`], **SENSITIVITY_ONLY** | Direct satisfaction `0.359375`, **PRIMARY** (CI not reported); calibrated `0.4584383393` [`0.3583265767`, `0.5607083483`], **EXPLORATORY** | same | same |
| Factorial negative sampler | Candidate/AND violation `0.591797` [`0.494141`, `0.687500`], **SENSITIVITY_ONLY** | Direct satisfaction `0.26953125`, **PRIMARY** (CI not reported); calibrated `0.4001858853` [`0.3221368052`, `0.4796390705`], **EXPLORATORY** | same | same |
| Factorial positive sampler | Candidate/AND violation `0.332031` [`0.230469`, `0.435547`], **SENSITIVITY_ONLY** | Direct satisfaction `0.568359375`, **PRIMARY** (CI not reported); calibrated `0.6797944307` [`0.5826621722`, `0.7687567182`], **EXPLORATORY** | same | same |
| Factorial positive-text implementation | Invalid first positive cohort candidate/AND violation `0.435547`, **SENSITIVITY_ONLY** | Corrected positive-only candidate/AND violation `0.353516` [`0.263672`, `0.443359`], **SENSITIVITY_ONLY** | `orbit-research/adsr_phase2_20260604/paper_prep/w2_execution_20260712/factorial/FACTORIAL_POSITIVE_CORRECTION_ADDENDUM.md` @ `25a4853e7e5f0894cac0d551c2ef9ce422fea594` | Never use the invalid first cohort as a factorial cell. |
| Factorial positive-sampler implementation | Invalid first positive cohort candidate/AND violation `0.406250`, **SENSITIVITY_ONLY** | Corrected positive-only candidate/AND violation `0.332031` [`0.230469`, `0.435547`], **SENSITIVITY_ONLY** | same | Never use the invalid first cohort as a factorial cell. |
| Recipe operating point | v1: `N=8`, positive-text violation approximately `0.094`, qualified success approximately `0.906`, described as deployable | v2: first lowest observed at `N=4`, violation `0.09375` [`0`, `0.1875`], proxy-qualified success `0.78125` [`0.625`, `0.90625`], no deployment recommendation | `analysis_exit1_v2/RECIPE_CURVES_V2.csv`; `analysis_exit1_v2/RECIPE_CURVES_V2.md` @ `026572302d0d31a491b2b40e100c3344bba37167`; v1 source `analysis_exit1/RECIPE_CURVES.md` @ `5eaf24f2ffbe4efe2153114a69ceee4e271424da` | Use `PROXY_QUALIFIED_SUCCESS`; do not carry forward `N=8` deployment claim. |
| B-prime gate interpretation | Original-rule sensitivity: quality rate `0.416667`, one-sided `p = 0.156163`, rule met; overall `0.400000`, `p = 0.116347`, rule met, **SENSITIVITY_ONLY** | `B_PRIME_GATE = FAIL_NONINFERIORITY_NOT_ESTABLISHED`; primary quality score LCB `0.307145`, exact LCB `0.295877`, both below strict `>0.40`, **REDUCED** | `orbit-research/adsr_phase2_20260604/paper_prep/validation_B_prime/B_PRIME_GATE_REPORT_20260712.md`; `orbit-research/adsr_phase2_20260604/paper_prep/validation_B_prime/B_PRIME_GATE_RESULT_20260712.json` @ `c682212c5039582e62d9ec4493822f42fe578d57` | Never convert the secondary original-rule sensitivity into a gate PASS or a no-degradation claim. |
| Retry-study denominator | Guide headline `16,384` draws (`32 × 512`), **STALE/UNRECONCILED** | Hash-frozen allowed value `8,192` rows (`32 × 256`) pending source-document reconciliation | `orbit-research/adsr_phase2_20260604/paper_prep/CLAIMS.md` @ `00fe296cabcf25f96b35d21bef7b507d42418085` | Cite only `8,192 frozen draws (32 prompts × 256 tries)` while V1 remains active. |
| Live intervention headline | Pre-W2 legacy-tail arm6 selected type error `0.0098`, clean-yield gain `+29.7%`, **SENSITIVITY_ONLY** | Promoted-OR bounded live confirmation: always-direction violation `0.1640625`; routed direction-action `0.3125`; `CRITERIA_NOT_ALL_MET`, **REDUCED** | `orbit-research/adsr_phase2_20260604/paper_prep/w2_execution_20260712/live_confirmation_20260713/LIVE_CONFIRM_RESULTS.csv` and audit @ `86103d466d54a8c6363c6060074bb90442fdd30f`; historical aggregate `orbit-research/adsr_phase2_20260604/GATE_B_FINAL_REPORT.md` @ `d84970bb611ac60976278e59308e31b2ca38e732` | Designs/endpoints differ; never carry the old live-PASS wording into the current promoted-OR result. |
| Difficulty regimes | Legacy bins `67/33/23/5` easy/seed-recoverable/low/rare; `25/128` uncertain memberships | No corrected bin counts; continuous `876`-unit promoted-OR ECDF is canonical | `orbit-research/adsr_phase2_20260604/paper_prep/autochain_20260712/recompute/CORRECTED_PROMPT_ECDFS.csv` @ `168d12f1e47f555c85b7b9085da947b5ef261835` | Do not create corrected bins. |
| Spine exact recovery target | Failed environment `0/1` target, `0/50` controls | Pinned environment `1/1` target, `50/50` controls | `orbit-research/adsr_phase2_20260604/paper_prep/w2_execution_20260712/spine_reconstruction_torch251_recovery/SPINE_RECONSTRUCTION_AUDIT.md` @ `a332581f511acbeb9b292fca839295d0503fe72f` | Use recovery artifact only. |
| Spine recovery label flips / cardinality | Failed environment `85/4,096` flips; `4` handoff duplicates / `4,100` raw scoring rows | Pinned environment `15/4,096` flips; `0` duplicates / `4,096` rows | same | Use recovery artifact only. |
| T6 runtime package identity | First package overlap with exact-runtime recovery: train `48/60`, heldout `85/100`, transport `20/20`, repeats `12/20`; reserve `171/200` | Exact-runtime T6 package: `201` presentations including appendix; promotion values in Section 1.2 | `orbit-research/adsr_phase2_20260604/paper_prep/autochain_20260712/T6_INGEST_AUDIT.json` and recovery audit paths @ `168d12f1e47f555c85b7b9085da947b5ef261835` | Do not interchange package IDs or counts. |
| SA3 human calibration completion | Earlier plan text: bundle `60`, ratings `0` | Current ingestion: `60/60` PI ratings | `orbit-research/adsr_phase2_20260604/paper_prep/pi_ratings_20260712/processed/DROP2_INGEST_AUDIT.json` @ `e30f40f9f9ee14ff07557f6b17e205fb174dfcb8` | Do not cite the stale unrated-bundle status. |
| W2 adoption state | `DRAFT_AWAITING_DUAL_PI_ADOPTION`; signature-gated PLAN/CLAIMS | `W2_ADOPTION = EXECUTED`; append-only PLAN/CLAIMS supersession applied | `orbit-research/adsr_phase2_20260604/paper_prep/DECISIONS.md`, escalation, PLAN, CLAIMS @ `00fe296cabcf25f96b35d21bef7b507d42418085` | Outcome adoption changed; historical text remains provenance, not current status. |
| v1.5 Gate-0 retry state | Gate-0 retry planned/open | `V15_GATE0 = FAIL_ESCALATED`; actual NFE `50` passed, state/resume/switch/fork/rollover/reserve failed | `orbit-research/adsr_phase2_20260604/paper_prep/rescue_v15_gate0_20260717/V15_GATE0_REPORT.md` @ `24af75fb0eaeab96d13689e3ab12d017fc4a1f5a` | Do not call retry pending/unreported or scientific evidence. |

## 8. Candidate figures/tables

| Candidate | Status / content | Source CSV/JSON | Source commit |
|---|---|---|---|
| Measurement Table 1 | T6 promoted-OR promotion and transport | `orbit-research/adsr_phase2_20260604/paper_prep/autochain_20260712/T6_PROMOTION_RESULT.json` | `168d12f1e47f555c85b7b9085da947b5ef261835` |
| Measurement Table 2 | Judge validation | `orbit-research/adsr_phase2_20260604/paper_prep/t7_judge_gold_20260713/judge_completion/POOLED_JUDGE_VALIDATION.json` | `65094d43d0e19777caa0626c31a266a2869b5911` |
| Measurement Table 3 | Evaluator Panels A/B | `analysis_exit1_v2/EVALUATOR_COMPARISON_AUDIT.json` | `026572302d0d31a491b2b40e100c3344bba37167` |
| Measurement Table 4 | A-prime legacy falsification | `orbit-research/adsr_phase2_20260604/paper_prep/validation_A_prime/A_PRIME_GATE_RESULT_20260713.json` | `9723bcf869987e55024dc7081f511146c9f88852` |
| Phenomenon Figure 1 | Unconditional promoted-OR base rate | `analysis_exit1_v2/UNCONDITIONAL_BASE_RATE_V2.csv` | `026572302d0d31a491b2b40e100c3344bba37167` |
| Phenomenon Figure 2 | Spine/N2/Stage-3 corrected rates | `orbit-research/adsr_phase2_20260604/paper_prep/autochain_20260712/recompute/CORRECTED_PUBLICATION_RATES.csv` | `168d12f1e47f555c85b7b9085da947b5ef261835` |
| Phenomenon Figure 3 | Corrected prompt difficulty ECDF | `orbit-research/adsr_phase2_20260604/paper_prep/autochain_20260712/recompute/CORRECTED_PROMPT_ECDFS.csv` | `168d12f1e47f555c85b7b9085da947b5ef261835` |
| Phenomenon Table 1 | Corrected prompt-level rates | `orbit-research/adsr_phase2_20260604/paper_prep/autochain_20260712/recompute/CORRECTED_PROMPT_RATES.csv` | `168d12f1e47f555c85b7b9085da947b5ef261835` |
| Factorial Figure | Six calibrated cells | `orbit-research/adsr_phase2_20260604/paper_prep/autochain_20260712/factorial/FACTORIAL_CONDITION_RESULTS.csv` | `168d12f1e47f555c85b7b9085da947b5ef261835` |
| Factorial inset | Two interaction contrasts | `orbit-research/adsr_phase2_20260604/paper_prep/autochain_20260712/factorial/FACTORIAL_INTERACTION_CONTRASTS.csv` | `168d12f1e47f555c85b7b9085da947b5ef261835` |
| Neutral-control Figure | Four cells | `analysis_exit1_v2/neutral_control/FOUR_CELL_RESULTS.csv` | `fd9cba693dd9f7cadd0fc9d80e38e4a19392c23d` |
| Neutral-control Table | Paired delta and sign-flip result | `analysis_exit1_v2/neutral_control/FOUR_CELL_RESULTS.json` | `fd9cba693dd9f7cadd0fc9d80e38e4a19392c23d` |
| Recipe Figure | N=`1/2/4/8` violation and proxy-quality curves | `analysis_exit1_v2/RECIPE_CURVES_V2.csv` | `026572302d0d31a491b2b40e100c3344bba37167` |
| Legacy frontier appendix | Free-filter and oracle decomposition | `orbit-research/adsr_phase2_20260604/phase0/P0_1_GATED_FRONTIER.json`; `orbit-research/adsr_phase2_20260604/phase0/P0_2_ORACLE_DECOMP.json` | `d84970bb611ac60976278e59308e31b2ca38e732` |
| Legacy limited-draw appendix | Selected difficult-set deployment success | `orbit-research/adsr_phase2_20260604/paper_prep/analysis_v2/deployment_success_metrics.csv`; `orbit-research/adsr_phase2_20260604/paper_prep/analysis_v2/deployment_success_paired_deltas.csv` | `5469f6c5e11d94b9b2bf4efc937db94fb5916bd2` |
| Fidelity appendix | CLAP prompt-fidelity diagnostic | `orbit-research/adsr_phase2_20260604/paper_prep/clap_fidelity/CLAP_FIDELITY_EXPANDED_RESULTS.csv` | `d84970bb611ac60976278e59308e31b2ca38e732` |
| Router appendix | Cross-validated offline replay | `orbit-research/adsr_phase2_20260604/paper_prep/router_replay/ROUTER_REPLAY_CV_RESULTS.csv` | `d84970bb611ac60976278e59308e31b2ca38e732` |
| Live-confirm Table | Four policies and strata | `orbit-research/adsr_phase2_20260604/paper_prep/w2_execution_20260712/live_confirmation_20260713/LIVE_CONFIRM_RESULTS.csv` | `86103d466d54a8c6363c6060074bb90442fdd30f` |
| Live-confirm contrast inset | Frozen bootstrap contrasts | `orbit-research/adsr_phase2_20260604/paper_prep/w2_execution_20260712/live_confirmation_20260713/LIVE_CONFIRM_AUDIT.json` | `86103d466d54a8c6363c6060074bb90442fdd30f` |
| Quality Table | B-prime noninferiority gate | `orbit-research/adsr_phase2_20260604/paper_prep/validation_B_prime/B_PRIME_GATE_RESULT_20260712.json` | `c682212c5039582e62d9ec4493822f42fe578d57` |
| Reproducibility Table | Spine exact-runtime regeneration | `orbit-research/adsr_phase2_20260604/paper_prep/w2_execution_20260712/spine_reconstruction_torch251_recovery/SPINE_RECONSTRUCTION_AUDIT.json` | `a332581f511acbeb9b292fca839295d0503fe72f` |
| Tier-3 Gate-0 Table | Resume and fork deterministic controls | `orbit-research/adsr_phase2_20260604/paper_prep/tier3_bolt_20260715/BOLT_RESUME_EQUIVALENCE.csv`; `orbit-research/adsr_phase2_20260604/paper_prep/tier3_bolt_20260715/BOLT_FORK_CALIBRATION.csv` | `bc302b6feb6ebf72732a7312c5bd710bc03b51f8` |
| Tier-3 Gate-1 Table | Static programs, outcome-aware actions, and strata | `orbit-research/adsr_phase2_20260604/paper_prep/tier3_bolt_20260715/BOLT_STATIC_PROGRAM_TABLE.csv`; `orbit-research/adsr_phase2_20260604/paper_prep/tier3_bolt_20260715/BOLT_ORACLE_ACTION_TABLE.csv`; `orbit-research/adsr_phase2_20260604/paper_prep/tier3_bolt_20260715/BOLT_ORACLE_STRATUM_RESULTS.csv` | `bc4e9444297efecddf88a225301a016b1d9c8a38` |
| Tier-3 Figure 1 | Static program / rollover comparison | `orbit-research/adsr_phase2_20260604/paper_prep/tier3_bolt_20260715/BOLT_STATIC_PROGRAM_TABLE.csv` | `bc4e9444297efecddf88a225301a016b1d9c8a38` |
| Tier-3 Figure 2 | Oracle headroom by stratum | `orbit-research/adsr_phase2_20260604/paper_prep/tier3_bolt_20260715/BOLT_ORACLE_STRATUM_RESULTS.csv` | `bc4e9444297efecddf88a225301a016b1d9c8a38` |
| Tier-3 Figure 3 | Gate 1.5A clustered bootstrap | `orbit-research/adsr_phase2_20260604/paper_prep/tier3_bolt_20260715/BOLT_GATE15A_BOOTSTRAP.csv` | `a8c41822c5f451b8e64a3bb03f3a420431e4dfe4` |
| Tier-3 Table | Gate 1.5A cross-fitted predictions / metrics | `orbit-research/adsr_phase2_20260604/paper_prep/tier3_bolt_20260715/BOLT_GATE15A_CROSSFIT_PREDICTIONS.csv`; `orbit-research/adsr_phase2_20260604/paper_prep/tier3_bolt_20260715/BOLT_GATE15A_METRICS.json` | `a8c41822c5f451b8e64a3bb03f3a420431e4dfe4` |
| v1.5 Table | Bounded replication attempt audit | `orbit-research/adsr_phase2_20260604/paper_prep/v15_replication_20260709/V15_ATTEMPT_AUDIT.csv` | `8cba0f5882f51b010e912e3f54d15f2246f6e695` |
| v1.5 Gate-0 Table | Engineering terminal diagnosis / NFE | `orbit-research/adsr_phase2_20260604/paper_prep/rescue_v15_gate0_20260717/V15_TERMINAL_DIAGNOSIS.json`; `orbit-research/adsr_phase2_20260604/paper_prep/rescue_v15_gate0_20260717/V15_NFE_ACCOUNTING.csv` | `24af75fb0eaeab96d13689e3ab12d017fc4a1f5a` |
| SA3 Figure | Guide-scale prevalence | `orbit-research/adsr_phase2_20260604/paper_prep/sao/stable_audio_3_medium/prevalence_full500/SA3_PREVALENCE_DEMUCS_SUMMARY.csv` | `d84970bb611ac60976278e59308e31b2ca38e732` |
| SA3 Table | True-intermediate observability | `orbit-research/adsr_phase2_20260604/paper_prep/sao/stable_audio_3_medium/true_intermediate/SA3_INTERMEDIATE_METRICS.csv` | `1f7fa915517f15445a0bd82b6366d488bc89fbef` |
| SDXL Table | Cross-modal signatures | `orbit-research/adsr_phase2_20260604/t2i/T2I_SIGNATURES.json` | `d84970bb611ac60976278e59308e31b2ca38e732` |
| Human-provenance Table | T1/T2 ingestion | `orbit-research/adsr_phase2_20260604/paper_prep/pi_ratings_20260711/processed/PI_RATING_INGEST_AUDIT.json` | `2a58eee0810012ea3affc150697619b16f36e6ff` |
| Human-provenance Table | T3/T4/T5 ingestion | `orbit-research/adsr_phase2_20260604/paper_prep/pi_ratings_20260712/processed/DROP2_INGEST_AUDIT.json` | `e30f40f9f9ee14ff07557f6b17e205fb174dfcb8` |
| Human-provenance Table | T6/T7 ingestion | `orbit-research/adsr_phase2_20260604/paper_prep/autochain_20260712/T6_INGEST_AUDIT.json`; `orbit-research/adsr_phase2_20260604/paper_prep/t7_judge_gold_20260713/ratings_ingest/T7_RATINGS_INGEST_AUDIT.json` | `168d12f1e47f555c85b7b9085da947b5ef261835`; `cd626ba7c5cc7b11eba13ec0e8db96301f0fbbfc` |

## 9. Open items affecting the paper

| Open item | Current exact state | Required disposition / boundary | Evidence / source commit |
|---|---|---|---|
| ACE-Step v1.5 Gate-0 retry | `V15_GATE0 = FAIL_ESCALATED`; model/environment and actual-NFE checks PASS; state contract, resume, condition switch, fork, true rollover, and completion reserve FAIL; full generation measured `50` transformer calls, `50` inline Euler updates, `0` scheduler calls; second harness failed before its first continuation transformer call because timestep suffix was a list rather than the native tensor contract; historical run-local `TEST_SUITE_STATUS = FAIL`, repository collection `16` errors, focused tests `exit=0` / `[100%]`; no scientific axis ran | PI choice: authorize one targeted tensor-timestep repair and fresh bounded Gate 0, or revert the tempo axis to proven v1 primitives; distinguish this historical run-local suite failure from the current closeout suite; paper status remains engineering-only **REDUCED** | `orbit-research/adsr_phase2_20260604/paper_prep/rescue_v15_gate0_20260717/V15_GATE0_REPORT.md`; `orbit-research/adsr_phase2_20260604/paper_prep/rescue_v15_gate0_20260717/V15_TERMINAL_DIAGNOSIS.json`; `orbit-research/adsr_phase2_20260604/paper_prep/rescue_v15_gate0_20260717/V15_TEST_RESULTS.json` @ `24af75fb0eaeab96d13689e3ab12d017fc4a1f5a` |
| Retry-study denominator V1 | Guide headline `16,384 = 32 × 512`; hash-frozen tracked core `8,192 = 32 × 256` | Reconcile source prose; until then cite only `8,192 frozen draws (32 prompts × 256 tries)` | `orbit-research/adsr_phase2_20260604/paper_prep/CLAIMS.md` @ `00fe296cabcf25f96b35d21bef7b507d42418085` |
| Factorial PI quality spotcheck | `20` pairs staged; `0` scored | Remains open; do not convert proxy-quality results to human quality | `orbit-research/adsr_phase2_20260604/paper_prep/w2_execution_20260712/factorial/FACTORIAL_PI_SPOTCHECK_MANIFEST.csv` @ `25a4853e7e5f0894cac0d551c2ef9ce422fea594` |
| Factorial direct-primary intervals | Direct promoted-OR satisfaction points are tracked for all six cells, but prompt-cluster CIs and direct-primary pairwise deltas are absent | Do not substitute calibrated-M2 intervals for the direct primary endpoint; compute only under a separately authorized append-only analysis | Factorial condition CSV/report @ `168d12f1e47f555c85b7b9085da947b5ef261835` |
| Prospective live rollover | Development static replay complete; no fresh `64`-prompt live rollover rerun/reanalysis | No claim that rollover repaired live confirmation; new run requires separate authorization | BOLT static table @ `bc4e9444297efecddf88a225301a016b1d9c8a38`; live report @ `86103d466d54a8c6363c6060074bb90442fdd30f` |
| SA3 paper tier | Calibration completed but frozen second-backbone promotion criterion not met | Retain **REDUCED** model-specific pilot; no full second-backbone claim | SA3 prevalence/intervention @ `d84970bb611ac60976278e59308e31b2ca38e732`; paired fidelity/true-intermediate @ `1f7fa915517f15445a0bd82b6366d488bc89fbef`; PI ingest @ `e30f40f9f9ee14ff07557f6b17e205fb174dfcb8` |
| SA3 intervention-fidelity human packet | `20` blinded pairs staged; all three preference fields blank; `0` scored | No obtained human fidelity/quality/constraint claim; PI rating remains optional/open | `orbit-research/adsr_phase2_20260604/paper_prep/sao/stable_audio_3_medium/intervention_fidelity/blinded_pairs/SA3_INTERVENTION_PAIRS_RATINGS.csv` @ `1f7fa915517f15445a0bd82b6366d488bc89fbef` |
| Gate 1.5A axis | `STOP_THIS_AXIS`; no Gate 1.5B or Gate 2 | Retain exact prereg scope and development-null wording | Gate 1.5A report/prereg @ `a8c41822c5f451b8e64a3bb03f3a420431e4dfe4` |
| Probe wall-clock accounting | Tracked headlines conflict (`~0.9/52 s` versus `~0.3/40 s`); detailed cost files named by Gate-B are absent at current HEAD | Pin authoritative cost accounting before any wall-clock headline | Gate-B @ `d84970bb611ac60976278e59308e31b2ca38e732`; current CLAIMS |
| Release hosting/package | Keep manifest has `1,342` rows and secret audit is `CLEAN`; final public hosting/package is not tracked as complete | Assemble and rescan the exact public release directory before any release-complete statement | `orbit-research/adsr_phase2_20260604/paper_prep/storage_triage/RELEASE_KEEP_MANIFEST.csv`; `orbit-research/adsr_phase2_20260604/paper_prep/RELEASE_SECRET_HYGIENE_20260707.md` @ `d84970bb611ac60976278e59308e31b2ca38e732` |

### UNTRACEABLE — do not use

| Untraceable or absent quantity/artifact | Do-not-use rule | Traceable boundary/source |
|---|---|---|
| A multi-instrument “T6-weighted evaluator-comparison panel” | Do not invent PANNs/Whisper/AudioSet T6-weighted rows; no tracked artifact exists. | Only T6 promoted-OR design-weighted promotion/transport is traceable in `orbit-research/adsr_phase2_20260604/paper_prep/autochain_20260712/T6_PROMOTION_RESULT.json` @ `168d12f1e47f555c85b7b9085da947b5ef261835`. |
| A-prime bucket CIs | Do not derive or report intervals for `7/112`, `16/47`, `28/30`, or `124/493`. | Point counts only in A-prime report @ `9723bcf869987e55024dc7081f511146c9f88852`. |
| T6 reliability and transport CIs; judge MCC CI | Do not invent intervals. | Point values only in T6 and pooled-judge artifacts listed in Section 1. |
| Factorial interaction CIs | Do not attach intervals to `-0.0074929796` or `-0.0010441408`. | Points only in `orbit-research/adsr_phase2_20260604/paper_prep/autochain_20260712/factorial/FACTORIAL_INTERACTION_CONTRASTS.csv` @ `168d12f1e47f555c85b7b9085da947b5ef261835`. |
| Factorial direct-primary cell CIs and pairwise deltas | Do not use calibrated-M2 intervals as direct promoted-OR intervals or invent direct pairwise tests. | Direct cell points only in `orbit-research/adsr_phase2_20260604/paper_prep/autochain_20260712/factorial/FACTORIAL_CONDITION_RESULTS.csv` @ `168d12f1e47f555c85b7b9085da947b5ef261835`. |
| Live per-policy point-estimate CIs | Do not infer four policy intervals from the stored contrast bootstrap. | Policy points in `orbit-research/adsr_phase2_20260604/paper_prep/w2_execution_20260712/live_confirmation_20260713/LIVE_CONFIRM_RESULTS.csv`; only frozen contrast bounds in `orbit-research/adsr_phase2_20260604/paper_prep/w2_execution_20260712/live_confirmation_20260713/LIVE_CONFIRM_AUDIT.json` @ `86103d466d54a8c6363c6060074bb90442fdd30f`. |
| v1.5 prevalence numerator and prevalence-component CIs | Do not infer a numerator from rounded `0.448242` or invent CIs. | Rate and coverage only in v1.5 final report @ `8cba0f5882f51b010e912e3f54d15f2246f6e695`. |
| SDXL diagnostic CIs | Do not invent intervals for prevalence, AUC, or frontier points. | Points only in T2I signatures @ `d84970bb611ac60976278e59308e31b2ca38e732`. |
| Gate-1.5A “supersession note” | Do not cite an untracked supersession note or paraphrase it as a new scope. | Exact scope is traceable only in `orbit-research/adsr_phase2_20260604/paper_prep/tier3_bolt_20260715/BOLT_GATE15A_PREREG.md` @ `a8c41822c5f451b8e64a3bb03f3a420431e4dfe4`. |
| Gate-B detailed online ledgers/cost files and a single authoritative probe-time headline | Do not use either contested wall-clock headline. | Aggregate conflict is traceable in Gate-B and current CLAIMS; detailed named files are absent at HEAD. |
| Separate tracked `2026-07-17` strategy-review artifact | Do not invent an evidence path. | Governance concurrence sentence is recorded by authority in `orbit-research/adsr_phase2_20260604/paper_prep/autochain_20260712/T6_PROMOTION_ESCALATION.md` @ closeout `00fe296cabcf25f96b35d21bef7b507d42418085`. |
