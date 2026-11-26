"""Typed results of the holiday functions (standard 3.1): one frozen model per result, every field with a description and a unit.

Since halvaro-hr 1.0 (issue #233) the functions return these models directly. `holiday_balance` returns one `HolidayBalance`; the six functions that returned a frame return an immutable
sequence of row models: `LedgerRows` (a tuple-like container of `LedgerRow`), `CarryOverRows`, `CarryOverProjectionRows`, `AccrualRows`, `LeaveLedgerRows` and `HighCarryOverRows`. A container
is read like a tuple (`len`, indexing, iteration) and `rows.to_frame()` gives the DataFrame the function returned before 1.0, with the same columns in the same order.
`Container.from_frame(frame)` and `Model.from_frame(frame)` build the typed form from a frame, `Model.columns()` lists the fields with type, description and unit. Importing this module does no I/O.
"""
from __future__ import annotations

import dataclasses
import datetime as dt
import types
from typing import Any, ClassVar, Iterable, Iterator, Mapping, Sequence, TypeVar, overload

import pandas as pd

from halvaro.core import FrameError

# The units a field may carry. A number of days is "days", a yes or no is "flag".
UNITS = ("days", "date", "month", "flag", "key", "label", "status", "text")


def _field(description: str, unit: str) -> Any:
    """A dataclass field that carries its description and unit as metadata."""
    if unit not in UNITS:
        raise ValueError(f"unit {unit!r} is not one of {UNITS}")
    return dataclasses.field(metadata={"description": description, "unit": unit})


@dataclasses.dataclass(frozen=True)
class ColumnSpec:
    """One field of a result: its name, type as text, description and unit."""

    name: str
    type: str
    description: str
    unit: str


@dataclasses.dataclass(frozen=True)
class _Result:
    """Base of the result models: the column specification read from the field metadata."""

    @classmethod
    def columns(cls) -> tuple[ColumnSpec, ...]:
        """The fields of the model in order, each with type, description and unit."""
        return tuple(ColumnSpec(f.name, str(f.type), f.metadata["description"], f.metadata["unit"]) for f in dataclasses.fields(cls))

    def to_dict(self) -> dict[str, Any]:
        """The fields as a dict in field order, for example for a JSON response."""
        return {f.name: getattr(self, f.name) for f in dataclasses.fields(self)}


R = TypeVar("R", bound="_Row")
Q = TypeVar("Q", bound="_Rows[Any]")


def _missing(value: Any) -> bool:
    """True for None, NaN, NaT and pd.NA: a missing value of a frame."""
    if value is None or value is pd.NA:
        return True
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def _coerce(type_text: str, value: Any) -> Any:
    """A value of a frame as the declared type of the field: a float field holds a float, a flag a bool; None stays None."""
    if value is None:
        return None
    if type_text in ("float", "float | None"):
        return float(value)
    if type_text in ("bool", "bool | None"):
        return bool(value)
    return value


@dataclasses.dataclass(frozen=True)
class _Row(_Result):
    """Base of the models of one frame row."""

    @classmethod
    def from_frame(cls: type[R], frame: pd.DataFrame) -> tuple[R, ...]:
        """One frozen model per row of a frame returned by the holiday function of this model before 1.0; a missing value becomes None, a float field holds a float and a flag a bool.

        Raises FrameError when the frame lacks a column of the model.
        """
        specs = cls.columns()
        names = [c.name for c in specs]
        absent = [n for n in names if n not in frame.columns]
        if absent:
            raise FrameError(f"{cls.__name__}.from_frame: the frame lacks column(s) {', '.join(absent)}")
        kinds = {c.name: c.type for c in specs}
        records = frame[names].to_dict("records")
        return tuple(cls(**{str(k): _coerce(kinds[str(k)], None if _missing(v) else v) for k, v in r.items()}) for r in records)


@dataclasses.dataclass(frozen=True)
class HolidayBalance(_Result):
    """Result of `holiday_balance`: the balance of one person and holiday year at the end of a month."""

    emp_key: str = _field("Key of the person (EMP-).", "key")
    holiday_year: str = _field("Label of the holiday year the balance belongs to.", "label")
    as_of: str = _field("Date asked for, as ISO text. Its month is the last month counted.", "date")
    entitlement_days: float = _field("Full-year entitlement of the person in this holiday year; 0 without an entitlement row. Reported, not part of the balance.", "days")
    carried_in_days: float = _field("Days carried into the holiday year; 0 without an entitlement row.", "days")
    carry_over_agreement: bool = _field("True when the person has a carry-over agreement in this holiday year.", "flag")
    accrued_days_ytd: float = _field("Days accrued from the start of the holiday year to the month of as_of.", "days")
    taken_days_ytd: float = _field("Days taken from the start of the holiday year to the month of as_of.", "days")
    balance_days: float = _field("carried_in_days plus accrued_days_ytd minus taken_days_ytd, rounded to 2 decimals.", "days")
    has_entitlement_row: bool = _field("True when an entitlement row exists for the person and holiday year.", "flag")
    legal_status: str = _field("Combined status of the legal facts behind the result (VERIFY, verified, synthetic or proposed).", "status")

    @classmethod
    def from_dict(cls, record: dict[str, Any]) -> HolidayBalance:
        """The model of the dict returned by `holiday_balance`. Raises FrameError when a key is missing or unknown."""
        names = [c.name for c in cls.columns()]
        wrong = sorted(set(record) ^ set(names))
        if wrong:
            raise FrameError(f"HolidayBalance.from_dict: missing or unknown key(s) {', '.join(wrong)}")
        return cls(**{k: record[k] for k in names})


@dataclasses.dataclass(frozen=True)
class LedgerRow(_Row):
    """One row of the frame of `holiday_ledger`: the running balance of a person and holiday year after one month."""

    emp_key: str = _field("Key of the person (EMP-).", "key")
    holiday_year: str = _field("Label of the holiday year.", "label")
    period: str = _field("Month of the row as YYYY-MM.", "month")
    accrued_days: float = _field("Days accrued in the month.", "days")
    taken_days: float = _field("Days taken in the month.", "days")
    balance: float = _field("carried_in_days plus the running sum of accrued_days minus taken_days up to and including this month, rounded to 2 decimals.", "days")
    opening_balance: bool = _field("True when carried_in_days of the year is the start value of the data window, not a carry-over.", "flag")
    missing_entitlement: bool = _field("True when the person has no entitlement row for the holiday year; carried_in_days then counts as 0.", "flag")
    negative: bool = _field("True when balance is below zero.", "flag")
    legal_status: str = _field("Combined status of the legal facts behind the result (VERIFY, verified, synthetic or proposed).", "status")


@dataclasses.dataclass(frozen=True)
class CarryOverRow(_Row):
    """One row of the frame of `carry_over_position`: the days carried into a holiday year against the cap of their basis."""

    emp_key: str = _field("Key of the person (EMP-).", "key")
    holiday_year: str = _field("Label of the holiday year the days were carried into.", "label")
    carried_in_days: float = _field("Days carried into the holiday year.", "days")
    carry_over_agreement: bool = _field("True when the person has a carry-over agreement in this holiday year.", "flag")
    opening_balance: bool = _field("True when carried_in_days is the start value of the data window, not a carry-over.", "flag")
    country: str = _field("Country whose holiday year label the row has: DK or DE.", "text")
    basis: str = _field("Basis of the cap: agreement or default.", "text")
    cap: float | None = _field("Most days the basis lets the person carry in; None on an opening row.", "days")
    headroom: float | None = _field("cap minus carried_in_days; negative when the carry-in is above the cap; None on an opening row.", "days")
    at_cap: bool = _field("True when headroom is zero; always False on an opening row.", "flag")
    deadline: dt.date | None = _field("Date by which the carried-in days are to be used (DE rows); None for DK rows.", "date")
    legal_status: str = _field("Combined status of the legal facts behind the result (VERIFY, verified, synthetic or proposed).", "status")


@dataclasses.dataclass(frozen=True)
class CarryOverProjectionRow(_Row):
    """One row of the frame of `carry_over_projection`: the carry-in the next holiday year should start with, against the stored one."""

    emp_key: str = _field("Key of the person (EMP-).", "key")
    holiday_year: str = _field("Label of the closing holiday year.", "label")
    year_end_balance: float = _field("Balance of the last ledger period of the closing holiday year.", "days")
    country: str = _field("Country whose holiday year label the row has: DK or DE.", "text")
    next_holiday_year: str = _field("Label of the holiday year that follows.", "label")
    basis: str = _field("Basis of the cap: agreement or default.", "text")
    cap: float = _field("Most days the basis lets the person carry in.", "days")
    projected_carry_in: float = _field("year_end_balance limited to zero at the bottom and to cap at the top, rounded to 2 decimals.", "days")
    stored_carry_in: float | None = _field("carried_in_days of the next holiday year; None when the next year has no row.", "days")
    difference: float | None = _field("projected_carry_in minus stored_carry_in; None without a stored value.", "days")
    matches: bool | None = _field("True when the size of difference is within the tolerance; None without a stored value.", "flag")
    legal_status: str = _field("Combined status of the legal facts behind the result (VERIFY, verified, synthetic or proposed).", "status")


@dataclasses.dataclass(frozen=True)
class AccrualRow(_Row):
    """One row of the frame of `accrual_expected`: stored and expected accrual of a person in a month."""

    emp_key: str = _field("Key of the person (EMP-).", "key")
    holiday_year: str = _field("Label of the holiday year.", "label")
    period: str = _field("Month of the row as YYYY-MM.", "month")
    accrued_days: float | None = _field("Days accrued in the month as stored; None on a month that is missing in the ledger.", "days")
    expected_days: float = _field("Monthly rate times the employed share of the month minus days of non-accruing leave, rounded to 2 decimals.", "days")
    missing_month: bool = _field("True when the month should exist and is missing in the ledger.", "flag")
    difference: float | None = _field("accrued_days minus expected_days; None on a missing month.", "days")
    within_tolerance: bool = _field("True when the size of difference is within the tolerance; False on a missing month.", "flag")
    legal_status: str = _field("Combined status of the legal facts behind the result (VERIFY, verified, synthetic or proposed).", "status")


@dataclasses.dataclass(frozen=True)
class LeaveLedgerRow(_Row):
    """One row of the frame of `leave_vs_ledger`: holiday leave days against taken days of a person and holiday year."""

    emp_key: str = _field("Key of the person (EMP-).", "key")
    holiday_year: str | None = _field("Label of the holiday year; None for a leave record of a person without ledger rows.", "label")
    leave_days: float = _field("Days of the holiday leave records that ended by the data date and lie in this holiday year.", "days")
    taken_days: float = _field("Sum of taken_days of the ledger in this holiday year.", "days")
    difference: float = _field("taken_days minus leave_days, rounded to 2 decimals.", "days")
    total_difference_days: float = _field("Sum of difference over all rows; the same value on every row.", "days")
    within_total_tolerance: bool = _field("True when the size of total_difference_days is within the tolerance.", "flag")
    legal_status: str = _field("Combined status of the legal facts behind the result (VERIFY, verified, synthetic or proposed).", "status")


@dataclasses.dataclass(frozen=True)
class HighCarryOverRow(_Row):
    """One row of the frame of `high_carry_over`: a person whose carry-in is above the threshold."""

    emp_key: str = _field("Key of the person (EMP-).", "key")
    holiday_year: str = _field("Label of the holiday year the days were carried into.", "label")
    carried_in_days: float = _field("Days carried into the holiday year.", "days")
    carry_over_agreement: bool = _field("True when the person has a carry-over agreement in this holiday year.", "flag")
    legal_status: str = _field("Combined status of the legal facts behind the result (VERIFY, verified, synthetic or proposed).", "status")


def _column(kind: str, values: list[Any]) -> Any:
    """One column of the frame form: float64, bool, nullable boolean or object, from the declared type of the field."""
    if kind in ("float", "float | None"):
        return pd.Series(values, dtype="float64")
    if kind == "bool":
        return pd.Series(values, dtype="bool")
    if kind == "bool | None":
        return pd.array(values, dtype="boolean")
    return pd.Series(values, dtype="object")


class _Rows(Sequence[R]):
    """Base of the containers: an immutable sequence of row models of one result, with `to_frame()`.

    Reads like a tuple (`len`, indexing, iteration, `in`, `==`). Nothing in it can be set or deleted. A slice gives a plain tuple of rows. `policy_status` holds the status of the policy
    facts behind a default that the function used (empty when the caller gave every policy value).
    """

    __slots__ = ("_rows", "_policy")
    _rows: tuple[R, ...]
    _policy: Mapping[str, str]
    model: ClassVar[type[_Row]]

    def __init__(self, rows: Iterable[R] = (), *, policy_status: Mapping[str, str] | None = None) -> None:
        """Raises FrameError when an item is not a row of the model of this container."""
        held = tuple(rows)
        wrong = [type(r).__name__ for r in held if not isinstance(r, self.model)]
        if wrong:
            raise FrameError(f"{type(self).__name__} holds {self.model.__name__} rows only, got {wrong[0]}")
        object.__setattr__(self, "_rows", held)
        object.__setattr__(self, "_policy", types.MappingProxyType(dict(sorted((policy_status or {}).items()))))

    def __setattr__(self, name: str, value: Any) -> None:
        raise dataclasses.FrozenInstanceError(f"cannot assign to field {name!r}: {type(self).__name__} is immutable")

    def __delattr__(self, name: str) -> None:
        raise dataclasses.FrozenInstanceError(f"cannot delete field {name!r}: {type(self).__name__} is immutable")

    @property
    def policy_status(self) -> Mapping[str, str]:
        """Status of the policy facts whose default the function used, by fact id; empty when the caller gave the value."""
        return self._policy

    @overload
    def __getitem__(self, index: int) -> R: ...

    @overload
    def __getitem__(self, index: slice) -> tuple[R, ...]: ...

    def __getitem__(self, index: int | slice) -> R | tuple[R, ...]:
        return self._rows[index]

    def __len__(self) -> int:
        return len(self._rows)

    def __iter__(self) -> Iterator[R]:
        return iter(self._rows)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, _Rows) and type(other) is type(self) and self._rows == other._rows and dict(self._policy) == dict(other._policy)

    def __hash__(self) -> int:
        return hash((type(self).__name__, self._rows, tuple(self._policy.items())))

    def __repr__(self) -> str:
        return f"{type(self).__name__}({len(self._rows)} rows)"

    def __reduce__(self) -> tuple[Any, ...]:
        return (_rebuild, (type(self), self._rows, dict(self._policy)))

    @classmethod
    def from_frame(cls: type[Q], frame: pd.DataFrame, *, policy_status: Mapping[str, str] | None = None) -> Q:
        """The container of a frame with the columns of the row model (the form the functions returned before 1.0). A missing value becomes None.

        Raises FrameError when the frame lacks a column of the model.
        """
        rows: Iterable[Any] = cls.model.from_frame(frame)
        return cls(rows, policy_status=policy_status or frame.attrs.get("policy_status"))

    def to_frame(self) -> pd.DataFrame:
        """A new DataFrame with one row per model and the columns of the model in field order, the frame the function returned before 1.0.

        Dtypes follow the declared field types: float64 for a float field, bool for a flag, the nullable boolean for `bool | None`, object for the rest, and None as the missing value of
        an object column. The frame is a copy: changing it changes nothing in the container. A non-empty `policy_status` is put in `frame.attrs["policy_status"]`.
        """
        specs = self.model.columns()
        frame = pd.DataFrame({c.name: _column(c.type, [getattr(r, c.name) for r in self._rows]) for c in specs}, columns=[c.name for c in specs])
        if self._policy:
            frame.attrs["policy_status"] = dict(self._policy)
        return frame


def _rebuild(cls: type[Any], rows: tuple[Any, ...], policy: dict[str, str]) -> Any:
    """Rebuild a container for pickle and copy."""
    return cls(rows, policy_status=policy)


class LedgerRows(_Rows[LedgerRow]):
    """Result of `holiday_ledger`: immutable sequence of `LedgerRow`, one per accrual row, sorted by emp_key, holiday_year and period."""

    __slots__ = ()
    model = LedgerRow


class CarryOverRows(_Rows[CarryOverRow]):
    """Result of `carry_over_position`: immutable sequence of `CarryOverRow`, one per entitlement row."""

    __slots__ = ()
    model = CarryOverRow


class CarryOverProjectionRows(_Rows[CarryOverProjectionRow]):
    """Result of `carry_over_projection`: immutable sequence of `CarryOverProjectionRow`, one per person and closing holiday year, sorted by emp_key and holiday_year."""

    __slots__ = ()
    model = CarryOverProjectionRow


class AccrualRows(_Rows[AccrualRow]):
    """Result of `accrual_expected`: immutable sequence of `AccrualRow`, sorted by emp_key, holiday_year and period."""

    __slots__ = ()
    model = AccrualRow


class LeaveLedgerRows(_Rows[LeaveLedgerRow]):
    """Result of `leave_vs_ledger`: immutable sequence of `LeaveLedgerRow`, sorted by emp_key and holiday_year."""

    __slots__ = ()
    model = LeaveLedgerRow


class HighCarryOverRows(_Rows[HighCarryOverRow]):
    """Result of `high_carry_over`: immutable sequence of `HighCarryOverRow`, sorted by emp_key. `policy_status` names the status of the threshold fact when its default was used."""

    __slots__ = ()
    model = HighCarryOverRow


# Function name to the model of its result. Used by the documentation quality test and by tools/build_skill.py.
RESULT_MODELS: dict[str, type[_Result]] = {
    "holiday_balance": HolidayBalance,
    "holiday_ledger": LedgerRow,
    "carry_over_position": CarryOverRow,
    "carry_over_projection": CarryOverProjectionRow,
    "accrual_expected": AccrualRow,
    "leave_vs_ledger": LeaveLedgerRow,
    "high_carry_over": HighCarryOverRow,
}

# Function name to the container of its result (the six functions that returned a frame before 1.0).
RESULT_CONTAINERS: dict[str, type[_Rows[Any]]] = {
    "holiday_ledger": LedgerRows,
    "carry_over_position": CarryOverRows,
    "carry_over_projection": CarryOverProjectionRows,
    "accrual_expected": AccrualRows,
    "leave_vs_ledger": LeaveLedgerRows,
    "high_carry_over": HighCarryOverRows,
}
