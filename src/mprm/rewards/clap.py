import torch
import torchaudio

from mprm.data.prompts import Prompt
from mprm.rewards.interface import RewardModel, RewardScore


class ClapReward(RewardModel):
    axis = "semantic_fit"
    version = "laion-clap-music-630k"

    # STOP-B-8 Phase-1 (2026-05-17): laion_clap's load_ckpt(model_id=...) is an
    # INTEGER index into a hardcoded list of 4 checkpoint filenames:
    #   0 -> 630k-best.pt                     (non-fusion, no audioset)
    #   1 -> 630k-audioset-best.pt            (non-fusion, default for enable_fusion=False)
    #   2 -> 630k-fusion-best.pt              (fusion)
    #   3 -> 630k-audioset-fusion-best.pt     (fusion, default for enable_fusion=True)
    # mprm's METHOD_SPEC variant string "laion-clap-music-630k" was a project-local
    # label that didn't match this API. We map it to id=1 (non-fusion + audioset) —
    # the closest fit for general semantic-fit scoring with our `enable_fusion=False`.
    _VARIANT_TO_LAION_MODEL_ID = {
        "laion-clap-music-630k": 1,
        "630k-best": 0,
        "630k-audioset-best": 1,
        "630k-fusion-best": 2,
        "630k-audioset-fusion-best": 3,
    }

    def __init__(self, variant: str = "laion-clap-music-630k", device: str = "cuda"):
        self.variant = variant
        self.device = device
        self._model = None

    def _ensure_loaded(self) -> None:
        if self._model is None:
            # STOP-B-8 Phase-1 (2026-05-17): install transformers from_pretrained
            # shim BEFORE laion_clap is imported so its module-level loads of
            # bert-base-uncased / roberta-base / facebook/bart-base resolve to
            # locally-cached directories instead of hitting huggingface.co.
            # See src/mprm/compat/laion_clap_local_tokenizers.py for details.
            from mprm.compat import laion_clap_local_tokenizers  # noqa: F401
            try:
                import laion_clap
            except ImportError as e:
                raise ImportError("laion-clap not installed. See github.com/LAION-AI/CLAP") from e
            # STOP-B-8 Phase-1 (2026-05-17): amodel must be "HTSAT-tiny" for the
            # public 630k-*.pt checkpoints. The prior "HTSAT-base" was a copy-
            # paste error — base has 1024-dim audio branch + 8 blocks/layer,
            # but the 630k weights are tiny (768-dim + 6 blocks). Mismatch
            # produced ~200 size-mismatch errors at load_state_dict time.
            self._model = laion_clap.CLAP_Module(enable_fusion=False, amodel="HTSAT-tiny").to(self.device)

            # STOP-B-8 Phase-1: 630k-*.pt checkpoints contain
            # `text_branch.embeddings.position_ids`, which newer transformers
            # versions register as a buffer that's NOT in `state_dict()`. The
            # strict-mode load_state_dict raises on this lone unexpected key.
            # We filter it before the inner load — no missing keys remain after
            # the HTSAT-tiny architecture fix above, so strict=True still
            # catches real mismatches.
            _STALE_KEYS = {"text_branch.embeddings.position_ids"}
            _orig_load_sd = self._model.model.load_state_dict
            def _patched_load_sd(state_dict, strict=True):
                filtered = {k: v for k, v in state_dict.items() if k not in _STALE_KEYS}
                return _orig_load_sd(filtered, strict=strict)
            self._model.model.load_state_dict = _patched_load_sd

            # Translate project-local variant string → laion_clap integer model_id.
            model_id = self._VARIANT_TO_LAION_MODEL_ID.get(self.variant)
            if model_id is None:
                raise ValueError(
                    f"Unknown CLAP variant {self.variant!r}; expected one of"
                    f" {sorted(self._VARIANT_TO_LAION_MODEL_ID)}"
                )
            self._model.load_ckpt(model_id=model_id)

    def score(self, waveform: torch.Tensor, sample_rate: int, prompt: Prompt) -> RewardScore:
        self._ensure_loaded()
        if sample_rate != 48_000:
            waveform = torchaudio.functional.resample(waveform, sample_rate, 48_000)
        if waveform.dim() == 2:
            waveform = waveform.mean(dim=0, keepdim=True)
        # STOP-B-8 Phase-1 (2026-05-17): laion_clap.hook.tokenizer() does a
        # `.squeeze(0)` on the (1, seq_len) RobertaTokenizer output, leaving a
        # 1-D (seq_len,) tensor that transformers' newer RobertaModel rejects
        # (`input_shape` unpack fails on 1-D). Workaround: pass our own
        # non-squeezing tokenizer to keep the batch dim.
        def _no_squeeze_tokenizer(texts):
            return self._model.tokenize(
                texts, padding="max_length", truncation=True, max_length=77,
                return_tensors="pt",
            )
        with torch.no_grad():
            audio_emb = self._model.get_audio_embedding_from_data(
                x=waveform.numpy(), use_tensor=False
            )
            text_emb = self._model.get_text_embedding(
                [prompt.text], tokenizer=_no_squeeze_tokenizer, use_tensor=False,
            )
        # laion_clap returns numpy with shape (1, D); flatten to (D,) and use
        # torch ops so `.norm()` is available regardless of the upstream dtype.
        a = torch.as_tensor(audio_emb, dtype=torch.float32).reshape(-1)
        t = torch.as_tensor(text_emb, dtype=torch.float32).reshape(-1)
        cosine = float((a * t).sum() / (a.norm() * t.norm() + 1e-8))
        return RewardScore(axis=self.axis, value=cosine, raw={"variant": self.variant})
