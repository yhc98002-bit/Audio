"""ACE-Step wrapper — STOP-B-8 minimal M1a binding to upstream v1.

The actual model loading goes through the upstream `acestep.pipeline_ace_step.ACEStepPipeline`
(github.com/ace-step/ACE-Step, Apache 2.0). The proposal commits to ACE-Step v1.5 long-term;
STOP-B-8 binds to v1 for M1a because v1.5 ships as a Gradio handler stack rather than a
clean wrapper class. Revisit for Phase B / STOP-B-9.

What this adapter supports (M1a path):
- Basic sample: text + lyrics + duration + guidance_scale + infer_step + seed → wav.
- R9-lite extras: omega_scale, guidance_interval, guidance_interval_decay, min_guidance_scale,
  scheduler_type, cfg_type, use_erg_tag, use_erg_lyric, use_erg_diffusion. All pass straight
  through to upstream `__call__`.

What this adapter explicitly DOES NOT support (raises NotImplementedError):
- `return_trajectory=True` — upstream writes only the final waveform to save_path; intermediate
  step latents are not exposed publicly.
- `sde_mode=True` / `eta_schedule` — upstream uses scheduler_type for SDE (`heun`) without a
  per-step eta exposed.
- `extras["step_allocation_late_frac"]` / `extras["negative_prompt_strength"]` — no upstream
  equivalents; full R9 sampler-control deferred to STOP-B-9.
- `predict_velocity` / `encode` / `decode` / `tweedie_clean` / `tweedie_decode` — upstream
  exposes neither the flow head nor the DCAE encoder/decoder at the public pipeline level.
  These are required by D3 Tweedie sanity + M2 entry + M-PRM main method; STOP-B-9.

D3a STATUS may remain AMBIGUOUS after STOP-B-8 — Phase B / M2 stays blocked until then.
"""
from __future__ import annotations

import logging
import os
import tempfile
import warnings
from pathlib import Path

import torch

from mprm.data.prompts import Prompt
from mprm.inference.interface import FlowMatchingModel, SamplingResult

log = logging.getLogger(__name__)

# STOP-B-8: public upstream `__call__` kwargs that are safe to pass through from
# mprm `extras`. KEEP IN SYNC with R9-lite SamplerScheduleLite axes + upstream
# `acestep.pipeline_ace_step.ACEStepPipeline.__call__` (around line 1445 of the
# upstream file). Adding kwargs here must be verified against upstream signature.
UPSTREAM_PASSTHROUGH_KEYS: frozenset[str] = frozenset({
    "omega_scale",
    "guidance_interval",
    "guidance_interval_decay",
    "min_guidance_scale",
    "scheduler_type",
    "cfg_type",
    "use_erg_tag",
    "use_erg_lyric",
    "use_erg_diffusion",
    "guidance_scale_text",
    "guidance_scale_lyric",
})

# STOP-B-8: mprm extras keys that are KNOWN to require unsupported upstream surface.
# Raising explicit NotImplementedError on these prevents the silent-degradation
# trap (Codex STOP-B-7.2 lesson). STOP-B-8.1 (Codex Q4): also reject the same names
# as sample() kwargs if a caller routes them via extras instead of the explicit
# kwarg slots — defence-in-depth.
# STOP-B-9 (2026-05-21): return_trajectory removed from this set — now supported via
# scheduler.step hook (see _SchedulerStepCapture below). sde_mode / eta_schedule stay
# unsupported (per-step eta is still not exposed by upstream's public API).
UNSUPPORTED_EXTRAS_KEYS: frozenset[str] = frozenset({
    "step_allocation_late_frac",
    "negative_prompt_strength",
    "sde_mode",
    "eta_schedule",
    "sde_eta",
})


_SCHEDULER_CAPTURE_ACTIVE = False  # module-level reentrance guard (Codex review B1)


class _SchedulerStepCapture:
    """STOP-B-9 (2026-05-21; Codex-review-revised 2026-05-22): hook-based trajectory capture.

    Context manager that monkeypatches `FlowMatchEulerDiscreteScheduler.step`
    to record `(step_index, sigma, sigma_next, timestep, sample, model_output)`
    at every step. Used by `AceStepModel.sample(return_trajectory=True)` to
    capture trajectory without forking the upstream sampling loop.

    Captures BEFORE the scheduler advances, so `sample` is `x_σ` (the input
    latent at the current σ) and `model_output` is the velocity v_out the
    pipeline mixed (CFG-aware — apg / cfg / cfg_zero_star / etc. all reduce
    to a single `model_output` arg by the time scheduler.step is called).

    **Concurrency contract (Codex review B1, 2026-05-22).** The patch is
    class-level, so two concurrent `sample(return_trajectory=True)` calls in
    the same Python process would interleave records and crash. We raise
    on reentrant `__enter__` rather than silently corrupt records. This is
    safe for d3 sanity (single-process, sequential calls) but Phase B M-PRM
    training that wants parallel trajectory capture across DataLoader workers
    or torch.distributed ranks needs a different approach (per-instance hook
    or thread-local state).

    Use:
        with _SchedulerStepCapture() as cap:
            pipeline(...)
        records = cap.records  # list of dicts
    """

    def __init__(self):
        self.records: list[dict] = []
        self._original_step = None

    def __enter__(self):
        global _SCHEDULER_CAPTURE_ACTIVE
        if _SCHEDULER_CAPTURE_ACTIVE:
            raise RuntimeError(
                "STOP-B-9: _SchedulerStepCapture is already active in this process."
                " Reentrant or concurrent trajectory capture is not supported by"
                " the current class-level monkeypatch (Codex review B1, 2026-05-22)."
                " Either serialise sample(return_trajectory=True) calls, or upgrade"
                " to a per-instance hook for Phase B parallel capture."
            )
        from acestep.schedulers.scheduling_flow_match_euler_discrete import (
            FlowMatchEulerDiscreteScheduler,
        )
        self._original_step = FlowMatchEulerDiscreteScheduler.step
        records = self.records
        original = self._original_step

        def _capturing_step(sched_self, model_output, timestep, sample, **kwargs):
            # Initialize step_index if upstream hasn't yet (it does so itself on
            # first call, but we read before delegating).
            if sched_self.step_index is None:
                sched_self._init_step_index(timestep)
            si = sched_self.step_index
            sigma = float(sched_self.sigmas[si])
            sigma_next = (
                float(sched_self.sigmas[si + 1])
                if (si + 1) < len(sched_self.sigmas)
                else 0.0
            )
            if torch.is_tensor(timestep):
                t_val = float(
                    timestep.item() if timestep.ndim == 0 else timestep[0].item()
                )
            else:
                t_val = float(timestep)
            records.append({
                "step_index": int(si),
                "sigma": sigma,
                "sigma_next": sigma_next,
                "timestep": t_val,
                "sample": sample.detach().clone().to(torch.float32).cpu(),
                "model_output": model_output.detach().clone().to(torch.float32).cpu(),
            })
            return original(
                sched_self,
                model_output=model_output,
                timestep=timestep,
                sample=sample,
                **kwargs,
            )

        FlowMatchEulerDiscreteScheduler.step = _capturing_step
        _SCHEDULER_CAPTURE_ACTIVE = True
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        global _SCHEDULER_CAPTURE_ACTIVE
        from acestep.schedulers.scheduling_flow_match_euler_discrete import (
            FlowMatchEulerDiscreteScheduler,
        )
        if self._original_step is not None:
            FlowMatchEulerDiscreteScheduler.step = self._original_step
        _SCHEDULER_CAPTURE_ACTIVE = False
        return False


class AceStepModel(FlowMatchingModel):
    """STOP-B-8 minimal upstream-v1 binding.

    Args:
        checkpoint: One of —
            (a) a local directory containing the four required subdirs
                {music_dcae_f8c8, music_vocoder, ace_step_transformer, umt5-base}, in which
                case upstream loads weights from there;
            (b) a HuggingFace repo slug (for reference; upstream's hardcoded REPO_ID
                `ACE-Step/ACE-Step-v1-3.5B` is what is actually downloaded);
            (c) None — upstream auto-downloads `ACE-Step/ACE-Step-v1-3.5B` into the
                HuggingFace default cache. Respects `HF_ENDPOINT` env var (set this
                to `https://hf-mirror.com` on networks without huggingface.co access).
            Override (a) explicitly via the `ACE_STEP_CHECKPOINT_DIR` env var.
        device: "cuda" / "cuda:N" / "cpu". Translated to upstream `device_id` (int).
        lora_path: optional LoRA path / HF slug. Forwarded to upstream `load_lora`.
        dtype: "bfloat16" / "float16" / "float32". Forwarded to upstream.

    See module docstring for the supported / unsupported feature list.
    """

    name = "ace_step_v1_5"   # logical name preserved (METHOD_SPEC); upstream is v1
    # STOP-B-8.1 (Codex Q3): upstream writes audio at 48000 Hz by default
    # (`acestep.pipeline_ace_step.py:1366,1391` — `sample_rate=48000`). Earlier
    # mprm placeholder of 44_100 was wrong. The actual rate is propagated via
    # `result.sample_rate` (read from torchaudio after load_audio), so reward
    # models see the correct rate; this class attribute is informational only.
    sample_rate = 48_000
    latent_rate_factor = 64  # PLACEHOLDER per FOM-1; verified later in STOP-B-9 / D3a

    UPSTREAM_REPO_ID = "ACE-Step/ACE-Step-v1-3.5B"
    REQUIRED_CHECKPOINT_SUBDIRS = (
        "music_dcae_f8c8", "music_vocoder", "ace_step_transformer", "umt5-base"
    )
    # STOP-B-8 Phase-1 (Codex Q6 follow-up): minimum-size sanity for the primary
    # weight file inside each subdir. Used by `_modelscope_cache_complete()` to
    # reject partial downloads. Conservative lower bounds: dcae ~300 MB,
    # vocoder ~200 MB, transformer ~1 GB (full size ~6 GB), umt5-base ~50 MB.
    REQUIRED_CHECKPOINT_FILES: dict[str, tuple[str, int]] = {
        "music_dcae_f8c8": ("diffusion_pytorch_model.safetensors", 200_000_000),
        "music_vocoder": ("diffusion_pytorch_model.safetensors", 150_000_000),
        "ace_step_transformer": ("diffusion_pytorch_model.safetensors", 1_000_000_000),
        "umt5-base": ("model.safetensors", 50_000_000),
    }

    def __init__(self, checkpoint: str | None = None, device: str = "cuda",
                 lora_path: str | None = None, dtype: str = "bfloat16"):
        self.checkpoint = checkpoint
        self.device = device
        self.lora_path = lora_path
        self.dtype = dtype
        self._device_id = self._parse_device(device)
        self._checkpoint_dir = self._resolve_checkpoint_dir(checkpoint)
        self._pipeline = None

    # ------------------------------------------------------------------ helpers

    @staticmethod
    def _parse_device(device: str) -> int:
        # STOP-B-8.1 (Codex Q1): reject CPU explicitly. Upstream `ACEStepPipeline.__init__`
        # builds `torch.device(f"cuda:{device_id}")` unconditionally
        # (`acestep.pipeline_ace_step.py:121-124`) — there is no safe CPU device_id.
        # MPS/CPU fallback is only triggered when `torch.cuda.is_available()` is False
        # AND `torch.backends.mps.is_available()` returns True. The methodology requires
        # GPU sampling anyway, so we reject CPU at construction time rather than letting
        # upstream silently use CUDA on a CUDA host.
        if device == "cpu":
            raise NotImplementedError(
                "STOP-B-8 AceStepModel: device='cpu' is not supported by the upstream"
                " ACE-Step v1 pipeline (it unconditionally constructs"
                " torch.device(f'cuda:{device_id}')). Use 'cuda' or 'cuda:N' on a GPU host."
            )
        if device == "cuda":
            return 0
        if device.startswith("cuda:"):
            return int(device.split(":", 1)[1])
        raise ValueError(
            f"STOP-B-8 AceStepModel: unsupported device {device!r}."
            " Use 'cuda' or 'cuda:N'."
        )

    @classmethod
    def _resolve_checkpoint_dir(cls, checkpoint: str | None) -> str | None:
        """Return a path to pass to upstream `ACEStepPipeline(checkpoint_dir=…)`.

        Resolution order (STOP-B-8 contract + STOP-B-8 Phase-1 Codex Q6 fix):
          1. If `ACE_STEP_CHECKPOINT_DIR` env var is set and is a directory, use it.
          2. If `checkpoint` is an existing local directory, use it.
          3. Auto-detect a ModelScope cache at
             `~/.cache/modelscope/hub/models/ACE-Step/ACE-Step-v1-3___5B` (or the
             generic `~/.cache/modelscope/hub/models/<slug>` for the configured
             checkpoint). ModelScope replaces `.` with `___` in path components.
          4. Else, return None — upstream will then `snapshot_download(REPO_ID)`
             into the default huggingface cache (respects `HF_ENDPOINT` env var).
        """
        env_dir = os.environ.get("ACE_STEP_CHECKPOINT_DIR")
        if env_dir and Path(env_dir).is_dir():
            return env_dir
        if checkpoint:
            p = Path(checkpoint)
            if p.is_dir():
                return str(p)
        # STOP-B-8 Phase-1 (Codex Q6 + Q6-follow-up): ModelScope auto-detect for
        # the upstream REPO_ID. Path scheme: `~/.cache/modelscope/hub/models/<org>/<repo>`
        # where dots in the repo name are escaped as `___`. STRICT check: each
        # required subdir must contain its primary weight file AND that file
        # must be at least the conservative minimum size (to reject partial
        # downloads while the snapshot is in progress).
        ms_slug = cls.UPSTREAM_REPO_ID.replace(".", "___")
        ms_path = Path.home() / ".cache" / "modelscope" / "hub" / "models" / ms_slug
        if cls._modelscope_cache_complete(ms_path):
            return str(ms_path)
        return None

    @classmethod
    def _modelscope_cache_complete(cls, ms_path: Path) -> bool:
        """STOP-B-8 Phase-1 (Codex Q6 follow-up): treat a ModelScope cache as
        usable ONLY if every required subdir has its primary weight file at
        the minimum conservative size. Prevents partial / in-progress downloads
        from being silently picked up (`load_checkpoint` would then fail deep
        inside diffusers with a confusing "no .bin file" error)."""
        if not ms_path.is_dir():
            return False
        for sub in cls.REQUIRED_CHECKPOINT_SUBDIRS:
            subdir = ms_path / sub
            if not subdir.is_dir():
                return False
            fname, min_size = cls.REQUIRED_CHECKPOINT_FILES[sub]
            fpath = subdir / fname
            if not fpath.is_file():
                return False
            try:
                if fpath.stat().st_size < min_size:
                    return False
            except OSError:
                return False
        return True

    def _has_required_subdirs(self, checkpoint_dir: str | None) -> bool:
        if checkpoint_dir is None:
            return False
        d = Path(checkpoint_dir)
        return all((d / sub).is_dir() for sub in self.REQUIRED_CHECKPOINT_SUBDIRS)

    # ------------------------------------------------------------------ loading

    _torchaudio_save_shimmed = False

    @classmethod
    def _install_torchaudio_save_shim(cls) -> None:
        """Replace `torchaudio.save` + `torchaudio.load` with soundfile-backed
        implementations on torch >= 2.6.

        STOP-B-8 Phase-2 (2026-05-18). torchaudio 2.6+ routes save/load
        through torchcodec; the native lib is broken on the Blackwell box.
        soundfile is already a REQUIRED import in D0 + is in active use
        elsewhere in the project, so routing through it is the lowest-risk
        fix.

        On torch 2.5.1 (A800) this method is a no-op: the legacy
        soundfile/sox backend in torchaudio works directly and the project
        does not need the shim.

        Class-level idempotent — installs at most once per process."""
        if cls._torchaudio_save_shimmed:
            return
        import torchaudio  # noqa: F401  (the module to patch)
        # Version gate: skip on torch < 2.6 where the legacy backend works.
        try:
            import torch as _torch
            _major, _minor = [int(x) for x in _torch.__version__.split("+")[0].split(".")[:2]]
            if (_major, _minor) < (2, 6):
                cls._torchaudio_save_shimmed = True  # mark as "handled" so we don't retry
                return
        except Exception:  # noqa: BLE001
            pass
        import soundfile as sf
        import numpy as np

        _original_save = torchaudio.save
        _original_load = torchaudio.load

        def _shim_save(uri, src, sample_rate, *, channels_first: bool = True,
                       format=None, encoding=None, bits_per_sample=None,
                       buffer_size=4096, backend=None, compression=None):
            fmt = (format or "").lower() if isinstance(format, str) else ""
            if fmt in ("wav", "flac", "ogg", ""):
                arr = src.detach().cpu().to(torch.float32).numpy() if hasattr(src, "detach") else np.asarray(src)
                if arr.ndim == 1:
                    pass  # mono (samples,)
                elif arr.ndim == 2:
                    arr = arr.T if channels_first else arr  # → (samples, channels)
                else:
                    raise ValueError(f"shim_save: unsupported tensor rank {arr.ndim}")
                sf_fmt = "WAV" if fmt in ("wav", "") else ("FLAC" if fmt == "flac" else "OGG")
                sf.write(str(uri), arr, int(sample_rate), format=sf_fmt)
                return
            return _original_save(uri, src, sample_rate, channels_first=channels_first,
                                    format=format, encoding=encoding,
                                    bits_per_sample=bits_per_sample,
                                    buffer_size=buffer_size, backend=backend,
                                    compression=compression)

        def _shim_load(uri, *args, **kwargs):
            # Strip torchcodec-only kwargs that older callers (and torchaudio's
            # legacy path) tolerate but we don't use here.
            channels_first = kwargs.pop("channels_first", True)
            # soundfile returns (samples, channels) as numpy; convert to torch
            # (channels, samples) by default for parity with torchaudio.load.
            try:
                arr, sr = sf.read(str(uri), dtype="float32", always_2d=False)
            except Exception:  # noqa: BLE001
                return _original_load(uri, *args, **kwargs)
            t = torch.from_numpy(np.ascontiguousarray(arr))
            if t.dim() == 1:
                t = t.unsqueeze(0)  # → (1, samples)
            elif t.dim() == 2:
                if channels_first:
                    t = t.T.contiguous()  # (samples, channels) → (channels, samples)
            return t, int(sr)

        torchaudio.save = _shim_save  # type: ignore[assignment]
        torchaudio.load = _shim_load  # type: ignore[assignment]
        cls._torchaudio_save_shimmed = True

    def _ensure_loaded(self) -> None:
        if self._pipeline is not None:
            return
        # STOP-B-8 Phase-2 (2026-05-18): on torch >= 2.6 install the
        # soundfile-backed torchaudio shim (see
        # mprm.compat.torchaudio_soundfile_shim for the reason). The class
        # method is a defense-in-depth wrapper; mprm.__init__ already auto-
        # installs the shim conditionally. On torch 2.5.1 (A800) this call
        # short-circuits because the shim is a no-op there.
        self._install_torchaudio_save_shim()
        try:
            from acestep.pipeline_ace_step import ACEStepPipeline
        except ImportError as e:
            raise ImportError(
                "STOP-B-8 ACE-Step v1 adapter: cannot import"
                " `acestep.pipeline_ace_step.ACEStepPipeline`."
                " Clone github.com/ace-step/ACE-Step and `pip install -e .` from that"
                " directory (the upstream package installs as `acestep`, not `ace_step`)."
            ) from e

        # Upstream constructor does NOT load weights eagerly — `self.loaded = False` until
        # __call__ or explicit load_checkpoint.
        try:
            self._pipeline = ACEStepPipeline(
                checkpoint_dir=self._checkpoint_dir,
                device_id=self._device_id,
                dtype=self.dtype,
            )
        except Exception as e:
            raise RuntimeError(
                f"STOP-B-8: ACEStepPipeline(checkpoint_dir={self._checkpoint_dir!r},"
                f" device_id={self._device_id}, dtype={self.dtype!r}) construction failed:"
                f" {type(e).__name__}: {e}"
            ) from e

        # Trigger explicit checkpoint load so failures surface here, not deep inside the
        # first sample() call. Upstream's `load_checkpoint()` either uses the local dir (if
        # the four required subdirs exist) or `snapshot_download(REPO_ID, cache_dir=…)`.
        # STOP-B-8.1 (Codex Q1): upstream sets `self.loaded = True` inside `load_checkpoint`
        # (acestep.pipeline_ace_step.py:237) — no need to set it again here.
        try:
            self._pipeline.load_checkpoint(self._checkpoint_dir)
        except Exception as e:
            local_subdir_hint = ""
            if self._checkpoint_dir is not None and not self._has_required_subdirs(self._checkpoint_dir):
                local_subdir_hint = (
                    f"\n  NOTE: {self._checkpoint_dir!r} does not contain the four required"
                    f" subdirs {list(self.REQUIRED_CHECKPOINT_SUBDIRS)}; upstream tried to"
                    f" snapshot_download `{self.UPSTREAM_REPO_ID}` into it instead."
                )
            raise RuntimeError(
                "STOP-B-8 ACE-Step v1 adapter: load_checkpoint failed."
                f" checkpoint_dir={self._checkpoint_dir!r}, upstream REPO_ID="
                f"{self.UPSTREAM_REPO_ID!r}. Cause: {type(e).__name__}: {e}."
                f"{local_subdir_hint}\n"
                "  Fix options:\n"
                "    A. Set ACE_STEP_CHECKPOINT_DIR to a local dir containing the four\n"
                "       required subdirs, then re-run.\n"
                "    B. Ensure `HF_ENDPOINT=https://hf-mirror.com` (or huggingface.co\n"
                "       reachable) and let upstream auto-download via snapshot_download.\n"
                "    C. Pre-download manually:\n"
                "       huggingface-cli download ACE-Step/ACE-Step-v1-3.5B --local-dir <path>\n"
                "       export ACE_STEP_CHECKPOINT_DIR=<path>"
            ) from e

        if self.lora_path:
            try:
                self._pipeline.load_lora(self.lora_path, 1.0)
            except Exception as e:
                raise RuntimeError(
                    f"STOP-B-8 ACE-Step v1 adapter: load_lora({self.lora_path!r}) failed:"
                    f" {type(e).__name__}: {e}"
                ) from e

    # ------------------------------------------------------------------ sample

    def sample(self, prompt: Prompt, *, seed: int, cfg_scale: float | None = None,
               steps: int | None = None, return_trajectory: bool = False,
               sde_mode: bool = False, eta_schedule: torch.Tensor | None = None,
               extras: dict | None = None,
               ) -> SamplingResult:
        # STOP-B-9 (2026-05-21): return_trajectory now supported via scheduler.step hook.
        # No early-raise — the trajectory capture is set up below before _pipeline(...).
        if sde_mode:
            raise NotImplementedError(
                "STOP-B-8: sde_mode=True is not supported. Upstream v1 exposes"
                " `scheduler_type` ('euler' default; 'heun' / 'pingpong' available) but no"
                " per-step eta. If a stochastic scheduler is sufficient, pass"
                " `extras={'scheduler_type': 'heun'}` instead. Full SDE control defers"
                " to STOP-B-9."
            )
        if eta_schedule is not None:
            raise NotImplementedError(
                "STOP-B-8: eta_schedule is not supported by the upstream v1 public API."
                " Defer to STOP-B-9 / Phase B M-PRM scope."
            )
        extras = dict(extras or {})
        for k in tuple(extras.keys()):
            if k in UNSUPPORTED_EXTRAS_KEYS:
                raise NotImplementedError(
                    f"STOP-B-8: extras[{k!r}] is not supported by the upstream v1 public"
                    " API. Full R9 (4-axis sampler-control) is deferred to STOP-B-9. For"
                    " M1a, use R9-lite (configs/baselines/r9_s7_sampler_control.yaml,"
                    " mode: r9_lite_public_api) which searches only public upstream axes."
                )

        self._ensure_loaded()

        # Upstream defaults: infer_step=60, guidance_scale=15.0. We honor mprm's defaults
        # (cfg_scale=5.0, steps=50) per METHOD_SPEC unless the caller overrides.
        cfg_scale = cfg_scale if cfg_scale is not None else 5.0
        steps = steps if steps is not None else 50

        # Translate structure_hint into the prompt text (no upstream equivalent slot).
        prompt_text = prompt.text or ""
        if prompt.structure_hint:
            prompt_text = f"{prompt_text} [structure: {prompt.structure_hint}]"

        upstream_kwargs: dict = {
            "format": "wav",
            "audio_duration": float(prompt.duration_target),
            "prompt": prompt_text,
            "lyrics": prompt.lyrics or "",
            "infer_step": int(steps),
            "guidance_scale": float(cfg_scale),
            "manual_seeds": [int(seed)],
        }

        # Forward only known-safe upstream kwargs (R9-lite axes + plain pass-throughs).
        applied_extras: dict = {}
        ignored_extras: dict = {}
        for k, v in extras.items():
            if k in UPSTREAM_PASSTHROUGH_KEYS:
                upstream_kwargs[k] = v
                applied_extras[k] = v
            else:
                # Not a known upstream kwarg AND not in UNSUPPORTED_EXTRAS_KEYS (those
                # raised above) — log and skip rather than pass through. Avoids feeding
                # upstream **kwargs that it would silently absorb.
                ignored_extras[k] = v
                log.warning("STOP-B-8 AceStepModel.sample: ignoring unknown extras key"
                            " %r (not in UPSTREAM_PASSTHROUGH_KEYS).", k)

        # Use a unique temp file so concurrent samples don't collide. Upstream writes
        # only via save_path; there is no in-memory return.
        save_path = tempfile.NamedTemporaryFile(suffix=".wav", delete=False).name
        upstream_kwargs["save_path"] = save_path

        # STOP-B-9: optionally capture trajectory via scheduler.step hook.
        capture = _SchedulerStepCapture() if return_trajectory else None
        try:
            if capture is not None:
                with capture:
                    self._pipeline(**upstream_kwargs)
            else:
                self._pipeline(**upstream_kwargs)
            if not os.path.exists(save_path):
                raise RuntimeError(
                    f"STOP-B-8: upstream pipeline returned but {save_path} was not written."
                )
            from mprm.data.audio_io import load_audio
            waveform, sr = load_audio(save_path)
        finally:
            # STOP-B-8.1 (Codex Q3): upstream also writes `<save_path>_input_params.json`
            # next to the wav (acestep.pipeline_ace_step.py:1733-1740). Clean both up.
            for path_to_clean in (save_path,
                                   save_path.replace(".wav", "_input_params.json")):
                try:
                    if os.path.exists(path_to_clean):
                        os.unlink(path_to_clean)
                except OSError:
                    pass

        trajectory_list = None
        traj_extras: dict = {}
        if capture is not None:
            # Materialize trajectory as a list of latents in time order (step_index
            # ascending). Each entry is z_σ at that step (BEFORE scheduler advance).
            recs = sorted(capture.records, key=lambda r: r["step_index"])
            trajectory_list = [r["sample"] for r in recs]
            # Phase B prep §B parity (2026-05-22 H5): also record the guidance
            # interval bounds the pipeline used, plus a per-step `cfg_active`
            # flag. The captured `model_output` at step k is:
            #   - CFG-mixed velocity if `start_idx ≤ k < end_idx`
            #   - cond-only velocity otherwise (pipeline's `else` branch in the
            #     main loop at `pipeline_ace_step.py:~1213`)
            # Tweedie reconstruction is well-defined either way, but downstream
            # callers (parity, M-PRM training) that want to RECOMPUTE v via
            # `predict_velocity` MUST pass `cfg_active=cfg_active_flags[k]`
            # explicitly to match the sampler's per-step branch decision.
            guidance_interval_used = float(
                applied_extras.get("guidance_interval", 0.5)
            )
            num_steps = len(recs)
            start_idx = int(num_steps * ((1.0 - guidance_interval_used) / 2.0))
            end_idx = int(num_steps * (guidance_interval_used / 2.0 + 0.5))
            # Pipeline also checks `do_classifier_free_guidance` (true iff
            # cfg_scale ∉ {0.0, 1.0}). Mirror that here.
            cfg_dcfg = not (cfg_scale == 0.0 or cfg_scale == 1.0)
            cfg_active_flags = [
                bool(cfg_dcfg and (start_idx <= r["step_index"] < end_idx))
                for r in recs
            ]
            traj_extras = {
                "trajectory_sigmas": [r["sigma"] for r in recs],
                "trajectory_sigmas_next": [r["sigma_next"] for r in recs],
                "trajectory_timesteps": [r["timestep"] for r in recs],
                "trajectory_step_indices": [r["step_index"] for r in recs],
                "trajectory_model_outputs": [r["model_output"] for r in recs],
                "trajectory_cfg_active": cfg_active_flags,
                "trajectory_capture": "stop_b9_scheduler_step_hook",
                "guidance_interval_used": guidance_interval_used,
                "guidance_interval_start_idx": start_idx,
                "guidance_interval_end_idx": end_idx,
                "do_classifier_free_guidance": cfg_dcfg,
            }

        return SamplingResult(
            waveform=waveform.cpu(),
            sample_rate=sr,
            trajectory=trajectory_list,
            seed=seed,
            cfg_scale=cfg_scale,
            inference_steps=steps,
            extras={
                "adapter": "stop_b8_ace_step_v1_minimal",
                "applied_extras": applied_extras,
                "ignored_extras": ignored_extras,
                "structure_hint_inlined": bool(prompt.structure_hint),
                **traj_extras,
            },
        )

    # ---------------------------------------------------------- STOP-B-9 APIs

    # CONVENTION NOTE (audit-Round-4 + STOP-B-9, 2026-05-21):
    # The base class `FlowMatchingModel.tweedie_clean(z_tau, tau, prompt)` has
    # `tau` named per rectified-flow convention (tau=1 → data, tau=0 → noise).
    # For ACE-Step the convention is INVERTED (σ=0 → data, σ=1 → noise), and
    # the model receives `timestep = σ * 1000` (per `pipeline_ace_step.py:663`
    # `t_i = t / 1000`, `_sigma_to_t(σ) = σ * 1000`).
    #
    # We KEEP the base-class argument name `tau` to preserve interface
    # compatibility, but the value passed in MUST be the ACE-Step σ (data=0,
    # noise=1) — typically pulled from `scheduler.sigmas[k]` (shift=3.0
    # applied). Passing a rectified-flow `tau` (data=1) here would produce a
    # wrong Tweedie estimate. See `TWEEDIE_DERIVATION_NOTE.md` §5 + §8.

    def predict_velocity(self, z_tau: torch.Tensor, tau: float, prompt: Prompt,
                          *, cfg_scale: float | None = None,
                          condition_cache: dict | None = None,
                          cfg_active: bool | None = None) -> torch.Tensor:
        """Call ACE-Step's flow head and return v_out at the given σ.

        STOP-B-9 (2026-05-21). For d3 sanity, `tweedie_decode` can also be
        invoked via a captured trajectory's `model_outputs` (cheaper because
        the velocity was already computed during sampling); this method is for
        the M-PRM training path where v at a freshly-perturbed z must be
        evaluated.

        Args:
            z_tau: latent at the current σ. Shape `(B, 8, 16, T)` or `(8, 16, T)`.
            tau: σ value in ACE-Step convention (0=data, 1=noise). Pull from
                `scheduler.sigmas[k]` (shift-applied), NOT a uniform fraction.
            prompt: the Prompt that conditions the velocity.
            cfg_scale: classifier-free guidance scale. Default 5.0 (matches
                AceStepModel.sample default).
            condition_cache: optional pre-computed encoder embeddings from
                `_build_condition_cache(prompt, cfg_type='cfg')`. If None,
                computed fresh.

        **cfg_active parameter (Phase B prep §B H5 fix, 2026-05-22).** The
        ACE-Step pipeline's default `guidance_interval=0.5` restricts CFG
        mixing to trajectory steps `[start_idx, end_idx)`; outside that
        interval, the pipeline emits the cond-only velocity (single decode
        call). Captured `trajectory_model_outputs[k]` therefore matches:
          - CFG-mixed velocity when `trajectory_cfg_active[k] = True`
          - cond-only velocity when `trajectory_cfg_active[k] = False`
        To reproduce the captured velocity faithfully at a given step,
        callers MUST pass `cfg_active` explicitly:
          - `cfg_active=True`  → compute CFG-mixed velocity (`v_uncond + s*(v_cond - v_uncond)`)
          - `cfg_active=False` → return cond-only velocity (`v_cond`)
          - `cfg_active=None`  → **raises ValueError** when `cfg_scale > 1.0` (silent inference is unsafe per PI directive 2026-05-22). With `cfg_scale ≤ 1.0` CFG is a no-op so `cfg_active=None` is allowed and returns `v_cond`.

        Returns the requested velocity (mixed or cond-only) in float32 on the
        model's device. This matches `cfg_type='cfg'` sampling. Other upstream
        cfg variants (apg / cfg_zero_star) are NOT replicated here.

        **Codex review B2/B3 (2026-05-22) — known parity gaps for Phase B:**
        - APG (upstream default `cfg_type='apg'`) has a momentum buffer + a
          guidance-interval schedule that depends on the current step index.
          `predict_velocity(z, σ, prompt)` is stateless and CANNOT match APG
          sampling without those inputs. Phase B M-PRM training must either
          (a) force `cfg_type='cfg'` end-to-end, or (b) extend this method
          with explicit momentum + step-index state.
        - ERG paths (`use_erg_tag` / `use_erg_lyric` / `use_erg_diffusion` —
          all default True in upstream `__call__`) install forward hooks that
          weaken attention layers via a temperature factor; they affect the
          captured `v_out` during sampling but are NOT replicated here. For
          full parity, Phase B should either disable ERG (pass
          `extras={'use_erg_tag': False, 'use_erg_lyric': False,
          'use_erg_diffusion': False}` to `sample()`) or implement the ERG
          hooks inside `_build_condition_cache` / `predict_velocity`.

        D3 sanity is unaffected because it uses captured `v_out` from the
        sampling trajectory (the `v_out=` shortcut in `tweedie_decode`); it
        only validates the algebra `x̂_0 = z − σ·v`, not this method.
        """
        self._ensure_loaded()
        cfg_scale = 5.0 if cfg_scale is None else float(cfg_scale)
        sigma = float(tau)
        if condition_cache is None:
            condition_cache = self._build_condition_cache(prompt)

        model_dtype = condition_cache["dtype"]
        z = z_tau.to(self.device).to(model_dtype)
        if z.dim() == 3:
            z = z.unsqueeze(0)
        bsz, _, _, frame_length = z.shape

        # Per pipeline_ace_step.py:663, the model receives `timestep = σ * 1000`.
        # Use a 1-D tensor of length `bsz` (matches upstream's
        # `timestep = t.expand(latent_model_input.shape[0])`).
        #
        # **dtype = float32 (Phase B prep §B parity fix, 2026-05-22 H1)**: the
        # upstream scheduler stores timesteps in float32 (per
        # `scheduling_flow_match_euler_discrete.py:215`:
        # `timesteps = sigmas * self.config.num_train_timesteps` where sigmas is
        # float32). The pipeline main loop then does `timestep = t.expand(bsz)`
        # which preserves float32. Using `model_dtype` (bf16) here quantizes the
        # timestep value — e.g. σ=0.738 → σ×1000=738.04 rounds to 740.0 in bf16
        # (mantissa step ≈ 4 near magnitude 738). This propagates through
        # `time_proj`'s sinusoidal embedding and produces a measurable mismatch
        # with the captured-v from sampling. Captured-v parity diagnosis
        # (`scripts/d3_captured_v_parity.py` + determinism check 2026-05-22)
        # confirmed this is the root cause. `ace_step_transformer.decode` casts
        # the embedded_timestep to hidden_states.dtype internally, so the
        # downstream graph remains in bf16 — only the position embedding sees
        # the higher-precision input.
        timestep = torch.full(
            (bsz,), sigma * 1000.0, device=self.device, dtype=torch.float32
        )
        attention_mask = torch.ones(
            bsz, frame_length, device=self.device, dtype=model_dtype
        )

        # Phase B prep §B H5 (2026-05-22): require explicit cfg_active when
        # CFG could matter. Silent inference would mis-reconstruct captured-v
        # at guidance-interval boundaries.
        if cfg_scale > 1.0 and cfg_active is None:
            raise ValueError(
                "predict_velocity: cfg_active must be passed explicitly when "
                "cfg_scale > 1.0. Captured v_out from sampling is "
                "branch-dependent on the pipeline's guidance_interval — "
                "inside the interval it is CFG-mixed; outside, it is "
                "cond-only. Pass `cfg_active=True/False` per "
                "`trajectory_cfg_active[step_index]` from the sampling "
                "result, or set cfg_active=True/False to indicate which "
                "branch this call should reproduce. (Defaulting silently "
                "is disallowed per PI directive 2026-05-22.)"
            )
        do_mix = bool(cfg_active) and cfg_scale > 1.0

        transformer = self._pipeline.ace_step_transformer
        with torch.no_grad():
            v_cond = transformer.decode(
                hidden_states=z,
                attention_mask=attention_mask,
                encoder_hidden_states=condition_cache["encoder_hidden_cond"],
                encoder_hidden_mask=condition_cache["encoder_mask_cond"],
                output_length=frame_length,
                timestep=timestep,
            ).sample
            if do_mix:
                v_uncond = transformer.decode(
                    hidden_states=z,
                    attention_mask=attention_mask,
                    encoder_hidden_states=condition_cache["encoder_hidden_null"],
                    encoder_hidden_mask=condition_cache["encoder_mask_null"],
                    output_length=frame_length,
                    timestep=timestep,
                ).sample
                # Plain CFG: v = v_uncond + s * (v_cond - v_uncond).
                v_out = v_uncond + cfg_scale * (v_cond - v_uncond)
            else:
                v_out = v_cond
        return v_out.to(torch.float32)

    def _build_condition_cache(self, prompt: Prompt) -> dict:
        """STOP-B-9 helper: precompute the (cond, null) encoder embeddings.

        Matches the cfg_type='cfg' branch of the upstream pipeline (
        `pipeline_ace_step.py:__call__` text/lyric/speaker setup + the
        ace_step_transformer.encode call inside text2music_diffusion_process).
        Speaker is zeros (per released checkpoint), null cond uses
        `torch.zeros_like` text + lyric (no ERG temperature — that is a
        Phase-A extras-mode feature and is not used here).
        """
        self._ensure_loaded()
        pipeline = self._pipeline
        device = self.device
        # Resolve dtype (matches what upstream stores on its modules).
        # Upstream constructs as `to(self.dtype)` with one of bfloat16/float16/float32.
        dtype_str = self.dtype
        if dtype_str == "bfloat16":
            model_dtype = torch.bfloat16
        elif dtype_str == "float16":
            model_dtype = torch.float16
        else:
            model_dtype = torch.float32

        prompt_text = prompt.text or ""
        if prompt.structure_hint:
            prompt_text = f"{prompt_text} [structure: {prompt.structure_hint}]"
        lyrics_text = prompt.lyrics or ""

        # 1. Text embeddings (umt5)
        encoder_text_hidden, text_attention_mask = pipeline.get_text_embeddings([prompt_text])
        bsz = 1
        encoder_text_hidden = encoder_text_hidden.to(model_dtype)

        # 2. Speaker embeddings — zeros for released checkpoint.
        speaker_embeds = torch.zeros(bsz, 512, device=device, dtype=model_dtype)

        # 3. Lyrics: empty → single 0-token, otherwise tokenize.
        if len(lyrics_text) > 0:
            lyric_token_idx_list = pipeline.tokenize_lyrics(lyrics_text)
            lyric_mask_list = [1] * len(lyric_token_idx_list)
            lyric_token_idx = torch.tensor(lyric_token_idx_list, device=device).unsqueeze(0).long()
            lyric_mask = torch.tensor(lyric_mask_list, device=device).unsqueeze(0).long()
        else:
            lyric_token_idx = torch.tensor([0], device=device).repeat(bsz, 1).long()
            lyric_mask = torch.tensor([0], device=device).repeat(bsz, 1).long()

        transformer = pipeline.ace_step_transformer
        with torch.no_grad():
            encoder_hidden_cond, encoder_mask_cond = transformer.encode(
                encoder_text_hidden,
                text_attention_mask,
                speaker_embeds,
                lyric_token_idx,
                lyric_mask,
            )
            # Null branch for CFG (matches pipeline_ace_step.py:1232+
            # `P(null_speaker, null_text, null_lyric)` path when use_erg_lyric=False).
            encoder_hidden_null, encoder_mask_null = transformer.encode(
                torch.zeros_like(encoder_text_hidden),
                text_attention_mask,
                torch.zeros_like(speaker_embeds),
                torch.zeros_like(lyric_token_idx),
                lyric_mask,
            )
        return {
            "dtype": model_dtype,
            "encoder_hidden_cond": encoder_hidden_cond,
            "encoder_mask_cond": encoder_mask_cond,
            "encoder_hidden_null": encoder_hidden_null,
            "encoder_mask_null": encoder_mask_null,
        }

    def decode(self, z_one: torch.Tensor) -> torch.Tensor:
        """DCAE latent → waveform via upstream MusicDCAE.decode.

        STOP-B-9 (2026-05-21). Accepts a latent in `(B, 8, 16, T)` or
        `(8, 16, T)` shape; returns waveform `(channels, samples)` at 48000 Hz
        in float32 on CPU. Single-sample (B=1) output is squeezed.
        """
        self._ensure_loaded()
        dtype_str = self.dtype
        if dtype_str == "bfloat16":
            model_dtype = torch.bfloat16
        elif dtype_str == "float16":
            model_dtype = torch.float16
        else:
            model_dtype = torch.float32
        z = z_one.to(self.device).to(model_dtype)
        if z.dim() == 3:
            z = z.unsqueeze(0)
        with torch.no_grad():
            _sr, pred_wavs = self._pipeline.music_dcae.decode(z, sr=self.sample_rate)
        # pred_wavs is a list (one per batch element). Return single waveform.
        wav = pred_wavs[0]
        return wav.detach().cpu().float()

    def encode(self, waveform: torch.Tensor) -> torch.Tensor:
        """Waveform → DCAE latent via upstream MusicDCAE.encode.

        STOP-B-9 (2026-05-21). Accepts a `(channels, samples)` or
        `(B, channels, samples)` waveform at 48000 Hz; returns latent
        `(B, 8, 16, T)` in float32 on the model's device.
        """
        self._ensure_loaded()
        dtype_str = self.dtype
        if dtype_str == "bfloat16":
            model_dtype = torch.bfloat16
        elif dtype_str == "float16":
            model_dtype = torch.float16
        else:
            model_dtype = torch.float32
        w = waveform.to(self.device).to(model_dtype)
        if w.dim() == 2:
            w = w.unsqueeze(0)
        with torch.no_grad():
            latents, _audio_lengths = self._pipeline.music_dcae.encode(w, sr=self.sample_rate)
        return latents.to(torch.float32)

    def tweedie_clean(self, z_tau: torch.Tensor, tau: float, prompt: Prompt,
                       *, cfg_scale: float | None = None,
                       condition_cache: dict | None = None,
                       v_out: torch.Tensor | None = None,
                       cfg_active: bool | None = None) -> torch.Tensor:
        """ACE-Step Tweedie clean-target estimate: `x̂_0 = x_σ - σ · v_out`.

        STOP-B-9 + audit-Round-4 (2026-05-21). The formula is source-confirmed
        at `pipeline_ace_step.py:711` (`zt_edit_denoised = zt_edit - t_i * V_delta_avg`,
        where `t_i = t / 1000 = σ`). See `TWEEDIE_DERIVATION_NOTE.md` §5 + §8.

        Args:
            z_tau: latent at the current σ.
            tau: σ value in ACE-Step convention (σ=0 data, σ=1 noise). Must come
                from `scheduler.sigmas[k]` (shift-applied), NOT a uniform fraction.
            prompt: conditions the velocity (ignored if `v_out` provided).
            v_out: optional pre-computed velocity (e.g. captured from a sampling
                trajectory via `_SchedulerStepCapture`). When supplied,
                `predict_velocity` is skipped entirely — faster + matches the
                exact mixing the pipeline used.
            cfg_scale / condition_cache: forwarded to `predict_velocity` when
                `v_out` is None.
        """
        sigma = float(tau)
        if v_out is None:
            v_out = self.predict_velocity(
                z_tau, tau, prompt,
                cfg_scale=cfg_scale,
                condition_cache=condition_cache,
                cfg_active=cfg_active,
            )
        z32 = z_tau.to(torch.float32)
        v32 = v_out.to(torch.float32).to(z32.device)
        # x̂_0 = x_σ − σ · v_out  (ACE-Step convention: σ=0 data, σ=1 noise)
        return z32 - sigma * v32

    def tweedie_decode(self, z_tau: torch.Tensor, tau: float, prompt: Prompt,
                        *, cfg_scale: float | None = None,
                        condition_cache: dict | None = None,
                        v_out: torch.Tensor | None = None,
                        cfg_active: bool | None = None) -> torch.Tensor:
        """Decode the Tweedie clean-target estimate to waveform.

        STOP-B-9 (2026-05-21). Equivalent to `decode(tweedie_clean(...))`.
        Accepts the same optional `v_out` shortcut.
        """
        z0_hat = self.tweedie_clean(
            z_tau, tau, prompt,
            cfg_scale=cfg_scale,
            condition_cache=condition_cache,
            v_out=v_out,
            cfg_active=cfg_active,
        )
        return self.decode(z0_hat)
