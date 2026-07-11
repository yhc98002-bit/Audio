import importlib.util
from pathlib import Path

import pytest


SCRIPT = Path(__file__).parents[1] / "paper_prep/scripts/score_validation_fallback.py"
SPEC = importlib.util.spec_from_file_location("score_validation_fallback", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


@pytest.mark.parametrize(
    "source", ["", "qwen_unvalidated", "automatic_model", "unknown"]
)
def test_old_fallback_rejects_every_unvalidated_source(source):
    with pytest.raises(ValueError, match="rating_source"):
        MODULE.validate_fallback_sources([{"rating_source": source}])


def test_old_fallback_accepts_only_shared_enum_syntax():
    MODULE.validate_fallback_sources([{"rating_source": "human:CXY"}])
    MODULE.validate_fallback_sources([{"rating_source": "pi:Richard Ye"}])
