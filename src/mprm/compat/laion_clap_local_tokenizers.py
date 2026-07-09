"""Monkey-patch transformers.{Bert,Roberta,Bart}{Tokenizer,Model}.from_pretrained
so laion_clap's module-level loads pick up pre-cached LOCAL tokenizer/model
directories instead of attempting to download from huggingface.co.

STOP-B-8 Phase-1 follow-up (2026-05-17):
  laion_clap 1.1.4's `training/data.py` and `clap_module/bert.py` and
  `clap_module/model.py` all do `XxxTokenizer.from_pretrained("bert-base-uncased")`
  (and `"roberta-base"`, `"facebook/bart-base"`, `BertModel.from_pretrained(...)`)
  at MODULE-LEVEL. On networks where `huggingface_hub.snapshot_download` is
  unreliable but ModelScope works (the user's box: hf-mirror.com is a redirector
  to huggingface.co which the Python lib can't always follow), every import of
  `laion_clap` fails before any CLAP method can be called.

  The fix: import this shim BEFORE `import laion_clap`. The shim wraps each
  affected `from_pretrained` classmethod so the magic strings get routed to
  pre-cached local directories specified by env vars (with sensible defaults).
  Original behavior is preserved for any other model_name_or_path.

Env var defaults (override at launch time if you've staged elsewhere):
  LAION_CLAP_BERT_DIR     = /home/yehaocun23s/source/laion_clap_tokenizers/bert-base-uncased
  LAION_CLAP_ROBERTA_DIR  = /home/yehaocun23s/source/laion_clap_tokenizers/roberta-base
  LAION_CLAP_BART_DIR     = /home/yehaocun23s/source/laion_clap_tokenizers/facebook--bart-base

If a target dir does not exist, the shim falls back to the original (network)
behavior so a future env where huggingface.co is reachable Just Works.
"""
from __future__ import annotations

import os
import warnings


_DEFAULTS = {
    "bert-base-uncased": ("LAION_CLAP_BERT_DIR",
                           "/home/yehaocun23s/source/laion_clap_tokenizers/bert-base-uncased"),
    "roberta-base": ("LAION_CLAP_ROBERTA_DIR",
                       "/home/yehaocun23s/source/laion_clap_tokenizers/roberta-base"),
    "facebook/bart-base": ("LAION_CLAP_BART_DIR",
                             "/home/yehaocun23s/source/laion_clap_tokenizers/facebook--bart-base"),
}

_installed = False


def _resolve(model_name_or_path: str) -> str:
    """If model_name_or_path matches one of the laion_clap magic strings AND
    the env-var-configured local dir exists, return the local path. Otherwise
    return the original arg unchanged."""
    entry = _DEFAULTS.get(model_name_or_path)
    if entry is None:
        return model_name_or_path
    env_var, default = entry
    local = os.environ.get(env_var, default)
    if local and os.path.isdir(local):
        return local
    return model_name_or_path


def _wrap_from_pretrained(cls):
    """Wrap `cls.from_pretrained` so the first positional arg is rerouted via
    `_resolve` if it matches one of the magic strings. No-op if already wrapped."""
    original = cls.from_pretrained
    if getattr(original, "_laion_clap_shimmed", False):
        return  # already patched
    # original is a bound classmethod; the underlying function takes (cls, name_or_path, *a, **kw)

    def _patched(model_name_or_path, *args, **kwargs):
        return original(_resolve(model_name_or_path), *args, **kwargs)

    _patched._laion_clap_shimmed = True
    # Replace the classmethod on the class. Since `from_pretrained` is inherited,
    # setting it on the subclass shadows the parent for laion_clap's call sites.
    cls.from_pretrained = _patched


def install() -> None:
    """Idempotent install of the from_pretrained patches. Safe to call from
    multiple import paths."""
    global _installed
    if _installed:
        return
    try:
        from transformers import (
            BertTokenizer, BertModel,
            RobertaTokenizer, RobertaModel,
            BartTokenizer, BartModel,
        )
    except ImportError as e:
        warnings.warn(
            "laion_clap_local_tokenizers shim: transformers not importable;"
            f" shim is a no-op. ({type(e).__name__}: {e})",
            stacklevel=2,
        )
        return
    for cls in (BertTokenizer, BertModel, RobertaTokenizer, RobertaModel,
                BartTokenizer, BartModel):
        _wrap_from_pretrained(cls)
    _installed = True


# Auto-install on import so callers only need `import mprm.compat.laion_clap_local_tokenizers`.
install()
