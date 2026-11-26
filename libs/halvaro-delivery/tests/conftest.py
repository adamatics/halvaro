"""Fixtures: the baseline release (HALVARO_RELEASE_DIR; tests marked `release` skip without it) and its tables."""
from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import pytest


def _root(env: str) -> Path:
    p = Path(env).expanduser().resolve()
    if (p / "truth").is_dir() or any((c / "parquet").is_dir() for c in p.iterdir() if c.is_dir()):
        return p
    return p / "baseline"


@pytest.fixture(scope="session")
def release_dir() -> Path:
    env = os.environ.get("HALVARO_RELEASE_DIR")
    if not env:
        pytest.skip("set HALVARO_RELEASE_DIR to an exported release, for example build/out/baseline")
    return _root(env)


@pytest.fixture(scope="session")
def load(release_dir):
    cache: dict = {}

    def _load(source: str, table: str) -> pd.DataFrame:
        if (source, table) not in cache:
            cache[(source, table)] = pd.read_parquet(release_dir / source / "parquet" / f"{table}.parquet")
        return cache[(source, table)]

    return _load
