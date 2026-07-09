"""mprm.ui — minimal human-evaluation UI scaffold.

Built in M0 per STOP-B-1 fix #4 so that M6 human eval can launch without waiting on UI
development. Supports whole-song playback, section playback (when section boundaries are
attached), prompt/lyrics display, pairwise A/B preference, and per-section worst-section
annotation. See EXPERIMENT_PLAN_EXEC.md Block D.hum for the rating contract.
"""

from mprm.ui.server import smoke_check, build_app
from mprm.ui.manifest import PairManifest, load_manifest, save_manifest
from mprm.ui.storage import AnnotationStore

__all__ = [
    "smoke_check",
    "build_app",
    "PairManifest",
    "load_manifest",
    "save_manifest",
    "AnnotationStore",
]
