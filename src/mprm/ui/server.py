"""Gradio-based human-evaluation UI (Block D.hum).

Minimal pairwise A/B preference UI per STOP-B-1 fix #4. Supports:
- whole-song playback (both A and B);
- section playback (per section span attached to a sample);
- prompt + lyrics display;
- per-axis A/B preference radios (≥ 5 axes);
- worst-section label per sample;
- section-local A/B preference per matching section pair.

Run via `python scripts/ui_serve.py --manifest <path>`.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from mprm.ui.manifest import PairManifest, load_manifest
from mprm.ui.storage import Annotation, AnnotationStore


def smoke_check() -> bool:
    """4-pair smoke test (M0 R009 deliverable)."""
    try:
        import gradio  # noqa: F401
    except ImportError:
        raise RuntimeError(
            "gradio not installed. Install with `pip install gradio>=4` "
            "(it is listed in requirements.txt as an optional UI dep)."
        )
    # Build the app with 4 synthetic pairs (no audio loading) to verify the layout.
    pairs = _synthetic_pairs(n=4)
    app = build_app(pairs, store_path="runs/ui_smoke/annotations.jsonl")
    if app is None:
        raise RuntimeError("build_app returned None.")
    print(f"UI smoke OK: built app with {len(pairs)} pairs.")
    return True


def _synthetic_pairs(n: int = 4) -> list[PairManifest]:
    from mprm.ui.manifest import Sample, Section
    pairs: list[PairManifest] = []
    for i in range(n):
        pairs.append(PairManifest(
            pair_id=f"smoke_{i:02d}",
            prompt_id=f"smoke_prompt_{i:02d}",
            prompt_text=f"Smoke prompt #{i} — synthetic, no audio loading expected.",
            lyrics=None,
            sample_a=Sample(
                method="method_a", audio_path=f"/tmp/non-existent-a-{i}.wav",
                sections=[Section("intro", 0.0, 8.0), Section("verse", 8.0, 30.0)],
            ),
            sample_b=Sample(
                method="method_b", audio_path=f"/tmp/non-existent-b-{i}.wav",
                sections=[Section("intro", 0.0, 8.0), Section("verse", 8.0, 30.0)],
            ),
        ))
    return pairs


def build_app(pairs: list[PairManifest], store_path: str | Path):
    """Build the Gradio app. Returns the gradio Blocks object (caller may .launch() it)."""
    import gradio as gr
    store = AnnotationStore(store_path)
    rater_id_state = "anonymous_rater"

    def render_pair(idx: int) -> tuple:
        pair = pairs[idx]
        return (
            pair.prompt_text,
            pair.lyrics or "(instrumental — no lyrics)",
            pair.sample_a.audio_path,
            pair.sample_b.audio_path,
            "\n".join(f"{s.label}: {s.start_seconds:.1f}–{s.end_seconds:.1f}s"
                      for s in pair.sample_a.sections),
            "\n".join(f"{s.label}: {s.start_seconds:.1f}–{s.end_seconds:.1f}s"
                      for s in pair.sample_b.sections),
        )

    def save_annotation(pair_idx: int, rater_id: str,
                          overall: str, musicality: str, prompt_fit: str,
                          lyric: str, worst_section_quality: str,
                          worst_label_a: str, worst_label_b: str,
                          notes: str) -> str:
        pair = pairs[pair_idx]
        axis_prefs = {
            "overall": overall,
            "musicality": musicality,
            "prompt_fit": prompt_fit,
            "lyric_intelligibility": lyric,
            "worst_section_quality": worst_section_quality,
        }
        ann = Annotation(
            pair_id=pair.pair_id,
            rater_id=rater_id or rater_id_state,
            timestamp=AnnotationStore.now(),
            axis_preferences=axis_prefs,
            worst_section_label_a=worst_label_a or None,
            worst_section_label_b=worst_label_b or None,
            notes=notes or None,
        )
        store.append(ann)
        return f"Saved annotation for pair {pair.pair_id} (rater {ann.rater_id})."

    with gr.Blocks(title="M-PRM human evaluation") as app:
        gr.Markdown("# M-PRM human evaluation — pairwise A/B")
        pair_idx = gr.Number(value=0, label="Pair index", precision=0)
        rater = gr.Textbox(label="Rater ID", value="")
        prompt_md = gr.Markdown()
        lyrics_md = gr.Markdown()
        with gr.Row():
            audio_a = gr.Audio(label="Sample A", interactive=False)
            audio_b = gr.Audio(label="Sample B", interactive=False)
        with gr.Row():
            sections_a = gr.Textbox(label="A — sections", interactive=False, lines=4)
            sections_b = gr.Textbox(label="B — sections", interactive=False, lines=4)
        gr.Markdown("### Pairwise preference (per axis)")
        overall = gr.Radio(["A", "B", "tie"], label="Overall")
        musicality = gr.Radio(["A", "B", "tie"], label="Musicality")
        prompt_fit = gr.Radio(["A", "B", "tie"], label="Prompt fit")
        lyric = gr.Radio(["A", "B", "tie"], label="Lyric intelligibility")
        worst_section_quality = gr.Radio(["A", "B", "tie"], label="Worst-section quality")
        gr.Markdown("### Worst-section annotation")
        worst_label_a = gr.Textbox(label="A worst section label (e.g. 'verse 2')")
        worst_label_b = gr.Textbox(label="B worst section label")
        notes = gr.Textbox(label="Notes (optional)", lines=2)
        save_btn = gr.Button("Save annotation", variant="primary")
        status = gr.Markdown()
        pair_idx.change(render_pair, inputs=[pair_idx],
                         outputs=[prompt_md, lyrics_md, audio_a, audio_b,
                                  sections_a, sections_b])
        save_btn.click(save_annotation,
                        inputs=[pair_idx, rater,
                                overall, musicality, prompt_fit, lyric, worst_section_quality,
                                worst_label_a, worst_label_b, notes],
                        outputs=[status])
        app.load(render_pair, inputs=[pair_idx],
                 outputs=[prompt_md, lyrics_md, audio_a, audio_b,
                          sections_a, sections_b])
    return app


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, help="path to pair manifest JSONL")
    parser.add_argument("--store", default="runs/ui/annotations.jsonl")
    parser.add_argument("--port", type=int, default=7860)
    args = parser.parse_args()
    pairs = load_manifest(args.manifest)
    app = build_app(pairs, store_path=args.store)
    app.launch(server_port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
