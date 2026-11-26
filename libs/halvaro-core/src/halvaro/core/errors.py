"""Errors of halvaro-core. Every message says what, where, and what to do."""
from __future__ import annotations

from typing import Any, Iterable


class HalvaroError(Exception):
    """Base class of all errors raised by the halvaro libraries."""


class StageRefusal(HalvaroError):
    """A function needs sources the caller's stage cannot see."""

    def __init__(self, missing_sources: Iterable[str], stage_needed: str, stage_held: str, function: str | None = None) -> None:
        self.missing_sources = tuple(sorted(missing_sources))
        self.stage_needed, self.stage_held, self.function = stage_needed, stage_held, function
        where = f" ({function})" if function else ""
        super().__init__(f"Sources {', '.join(self.missing_sources)} appear at stage {stage_needed}; the session holds stage {stage_held}{where}. "
                         f"Ask for a session at stage {stage_needed} or use only the sources of stage {stage_held}.")


class RestrictedColumnRefusal(HalvaroError):
    """A restricted column was asked for by a role that may not read it."""

    def __init__(self, column: str, role: str, stage: str) -> None:
        self.column, self.role, self.stage = column, role, stage
        super().__init__(f"Column {column} is restricted; role {role} at stage {stage} may not read it. Use an aggregate above the minimum group size or a role with restricted access.")


class AmbiguousKey(HalvaroError):
    """One key matched more than one candidate."""

    def __init__(self, key: Any, candidates: Iterable[Any]) -> None:
        self.key, self.candidates = key, tuple(candidates)
        super().__init__(f"Key {key} matches {len(self.candidates)} candidates: {', '.join(map(str, self.candidates[:5]))}. Pass a date or a more specific key.")


class UnmatchedKeys(HalvaroError):
    """Keys on one side of a join have no partner (strict mode only)."""

    def __init__(self, side: str, keys: Iterable[Any]) -> None:
        self.side, self.keys = side, tuple(keys)
        super().__init__(f"{len(self.keys)} keys on the {side} side have no partner, for example {', '.join(map(str, self.keys[:5]))}. Check the report, or join without strict.")


class KeyFormatError(HalvaroError):
    """A text is not a valid typed key or natural label."""


class FrameError(HalvaroError):
    """A frame lacks a table, column or shape the function needs."""


class FrameMissing(HalvaroError):
    """A visible source has no frame; this is a programming error of the caller."""


class ReleaseMismatch(HalvaroError):
    """Frames come from different data releases."""


class SumGuardError(HalvaroError):
    """A sum would mix currencies or units."""


class UnknownRegion(HalvaroError):
    """A site, country or region code the calendar does not know."""


class PeriodError(HalvaroError):
    """A period or an effective dated frame is malformed."""


class FactNotFound(HalvaroError, KeyError):
    """A fact id or config path does not exist in the snapshot."""

    def __str__(self) -> str:
        return str(self.args[0]) if self.args else ""


class ProfileError(HalvaroError):
    """A database or session profile the guard cannot map to a stage and role."""


class AggregateRefusal(HalvaroError):
    """A frame ties a restricted measure to individual people, or a group is below the minimum size."""


class BasisError(HalvaroError):
    """A currency conversion basis that is missing, unknown or not available in this version."""
