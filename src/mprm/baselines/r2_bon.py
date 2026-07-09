from mprm.baselines.interface import Baseline, BaselineResult
from mprm.data.audio_io import save_audio
from mprm.data.prompts import Prompt


class R2BoN(Baseline):
    rung_id = "R2"
    name = "bon_raw"

    def __init__(self, *args, n: int, primary_axis: str, cfg_scale: float | None = None,
                 inference_steps: int | None = None, n_sweep: list[int] | None = None,
                 **kwargs):
        super().__init__(*args, **kwargs)
        self.n = n
        self.n_sweep = n_sweep
        self.primary_axis = primary_axis
        self.cfg_scale = cfg_scale
        self.inference_steps = inference_steps

    def _generate_candidates(self, prompt: Prompt, seed: int, n: int):
        candidates = []
        for i in range(n):
            res = self.model.sample(prompt, seed=seed + i,
                                     cfg_scale=self.cfg_scale, steps=self.inference_steps)
            metrics = self.score_all_axes(res.waveform, res.sample_rate, prompt)
            candidates.append((res, metrics))
        return candidates

    def run_on_prompt(self, prompt: Prompt, *, seed: int) -> BaselineResult:
        # Nested BoN sampling per FINAL_REVISION_CRITIC.md #4: generate BoN-max_n
        # candidates ONCE, derive BoN-{4, 8, 16} post-hoc by truncating the same
        # ranked candidate list. Save ranking provenance (per-candidate seed +
        # primary-axis score + all-axes metrics + rank) to extras so cross-N
        # comparisons are reproducible from disk.
        sweep_values = self.n_sweep or [self.n]
        max_n = max(sweep_values)
        candidates = self._generate_candidates(prompt, seed, max_n)

        # Compute global ranking (over max_n candidates) for provenance.
        # Sort by primary_axis descending; stable sort = candidate_index tie-break.
        indexed = [(i, c) for i, c in enumerate(candidates)]
        ranked = sorted(
            indexed,
            key=lambda ic: ic[1][1].get(self.primary_axis, float("-inf")),
            reverse=True,
        )
        ranked_candidates = [
            {
                "rank": rank,                       # 1-indexed rank in primary_axis ordering
                "candidate_index": orig_idx,        # 0-indexed position in generation order
                "candidate_seed": seed + orig_idx,  # the seed actually fed to model.sample
                "primary_axis_score": float(c[1].get(self.primary_axis, float("nan"))),
                "all_metrics": c[1],
            }
            for rank, (orig_idx, c) in enumerate(ranked, start=1)
        ]

        per_n_summary: dict[int, dict[str, float]] = {}
        per_n_best_waveform: dict[int, tuple] = {}
        per_n_best_candidate_index: dict[int, int] = {}
        for n in sweep_values:
            subset = candidates[:n]
            # Pick best within this nested subset (same primary_axis criterion)
            best_subset_idx, best = max(
                enumerate(subset),
                key=lambda ic: ic[1][1].get(self.primary_axis, float("-inf")),
            )
            per_n_summary[n] = best[1]
            per_n_best_waveform[n] = (best[0].waveform, best[0].sample_rate)
            per_n_best_candidate_index[n] = best_subset_idx
        # Headroom gate expects BoN-8 as the canonical R2 result (METHOD_SPEC §3 / EXPERIMENT_PLAN_EXEC Block A).
        canonical_n = 8 if 8 in sweep_values else min(sweep_values, key=lambda x: abs(x - 8))
        canonical_metrics = per_n_summary[canonical_n]
        wav, sr = per_n_best_waveform[canonical_n]
        wav_path = self.output_dir / f"{prompt.prompt_id}_seed{seed}_bon{canonical_n}.wav"
        save_audio(wav_path, wav, sr)
        return BaselineResult(
            rung_id=self.rung_id,
            run_id=f"{self.rung_id}-{prompt.prompt_id}-seed{seed}",
            prompt_id=prompt.prompt_id,
            waveform_path=str(wav_path),
            metrics=canonical_metrics,
            extras={
                "seed": seed,
                "n_sweep": sweep_values,
                "canonical_n": canonical_n,
                "per_n_summary": per_n_summary,
                "per_n_best_candidate_index": per_n_best_candidate_index,
                "n_total_candidates": len(candidates),
                # Nested-BoN provenance (FINAL_REVISION_CRITIC.md #4):
                "ranked_candidates": ranked_candidates,
                "selection_provenance": {
                    "primary_axis": self.primary_axis,
                    "ranking_method": "stable_sort_desc_by_primary_axis",
                    "tie_break": "candidate_index_ascending_via_stable_sort",
                    "max_n_generated": max_n,
                    "derives": {str(n): {"top_k": n, "best_candidate_index": per_n_best_candidate_index[n]} for n in sweep_values},
                },
            },
        )
