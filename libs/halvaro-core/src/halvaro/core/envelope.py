"""The one result type of the halvaro libraries."""
from __future__ import annotations

import dataclasses
import datetime as dt
from typing import Any, Iterable

from . import registry, snapshot
from .errors import HalvaroError
from ._version import __version__
from .facts import combine_status

STATUSES = ("ok", "VERIFY", "synthetic", "VERIFY+synthetic")


@dataclasses.dataclass(frozen=True)
class Envelope:
    """Wraps a public result. A domain library subclasses it, adds fields after these and removes or renames none."""

    value: Any
    facts_used: tuple[Any, ...] = ()                      # ((fact id, value, status), ...)
    status: str = "ok"                          # ok, VERIFY, synthetic or VERIFY+synthetic
    as_of: dt.date | None = None
    stage: str | None = None                    # the highest stage of `sources`
    sources: tuple[str, ...] = ()
    basis: str | None = None
    synthetic: bool = True
    warnings: tuple[str, ...] = ()
    function: str | None = None                 # registered function id
    library_version: str | None = None
    snapshot: str | None = None                 # snapshot hash
    release: str | None = None                  # data release of the frames, from release_now


def make_envelope(value: Any, function: str | None = None, *, facts: Iterable[Any] = (), as_of: dt.date | None = None, sources: Iterable[str] = (), basis: str | None = None,
                  warnings: Iterable[str] = (), release: str | None = None, cls: type[Envelope] = Envelope, **extra: Any) -> Envelope:
    """Build an envelope with provenance stamped: status from the facts, stage from the sources, snapshot hash and the version of the distribution the function id belongs to.
    Without a function id, or when that version cannot be found, the core version is stamped and a warning says so."""
    from . import access            # late import: access needs the registry, the registry needs this module
    facts = tuple(facts)
    version, warnings = __version__, list(warnings)
    if function:
        try:
            version = registry.library_version(registry.library_of(function))
        except HalvaroError as e:
            warnings.append(f"library version of {function} unknown, the core version is stamped: {e}")
    return cls(value=value, facts_used=tuple((f.id, f.value, f.status) for f in facts), status=combine_status(f.status for f in facts), as_of=as_of,
               stage=access.stage_of_sources(sources) if sources else None, sources=tuple(sources), basis=basis, warnings=tuple(warnings),
               function=function, library_version=version, snapshot=snapshot.snapshot_hash(), release=release, **extra)
