"""Access to the generated snapshot of design, config, dictionary and facts. Loaded on first use, never at import."""
from __future__ import annotations

import functools
import json
from importlib import resources
from typing import Any, cast


@functools.lru_cache(maxsize=None)
def load() -> dict[str, Any]:
    """The snapshot as a dict (cached)."""
    return cast("dict[str, Any]", json.loads(resources.files("halvaro.core").joinpath("_data/snapshot.json").read_text(encoding="utf-8")))


def snapshot_hash() -> str:
    """Hash of the snapshot content; it is the `snapshot` field of every Envelope."""
    return cast(str, load()["hash"])
