"""Typed keys and natural labels, the master map and the foreign key prefixes of the dictionary."""
from __future__ import annotations

import functools
import re
from typing import Any, Mapping, NamedTuple

import pandas as pd

from . import snapshot, violations
from .errors import FrameError, KeyFormatError
from .registry import function

KEY_RE = re.compile(r"^([A-Z]{2,5})-([0-9]+)$")

# Polymorphic key columns: type column and the prefix each type value implies (None: free text, not checked; mapping None: the type column holds the prefix).
POLYMORPHIC = {
    "competence.requirement.scope_key": ("scope_type", {"role": "ROLE", "project": "PRJ", "contract": "CON", "project_type": None}),
    "projects.meeting_attendance.attendee": ("attendee_type", {"employee": "EMP", "external": "CNT"}),
    "energy-esg.emission_line.ref_key": ("ref_type", None),
}


class KeyParts(NamedTuple):
    prefix: str
    number: int
    width: int
    family: str
    entity: str | None


class MasterInfo(NamedTuple):
    prefix: str
    entity: str | None
    source: str
    table: str
    column: str
    stage: str


class LabelParts(NamedTuple):
    prefix: str
    text: str
    source: str
    table: str
    column: str


@functools.lru_cache(maxsize=None)
def _rx(pattern: str) -> re.Pattern[str]:
    return re.compile(pattern)


@function(oracle="py:../libs/halvaro-core/repo_tests/test_oracle_older_keys_access_facts.py::test_parse_key_oracle_every_primary_key_of_the_baseline_by_string_slicing")
def parse_key(text: str) -> KeyParts:
    """Use this when you have the text of a typed key such as EMP-000001 and need its prefix, number, width and family.

    Rule: the text must be a prefix of the key list, a dash and digits of the width the prefix has. Natural labels such as GL accounts are read by parse_label, not here.

    Args:
        text: The key as text.

    Returns:
        KeyParts: prefix, number (a whole number), width (the number of digits), family and entity.

    Raises:
        KeyFormatError: the text is not a typed key, the prefix is not known, or the digits do not match the width of the prefix.

    Example:
        >>> from halvaro.core import parse_key
        >>> parse_key("EMP-000001")
        KeyParts(prefix='EMP', number=1, width=6, family='transactional', entity='employee')
        >>> parse_key("EMP-1")
        Traceback (most recent call last):
        ...
        halvaro.core.errors.KeyFormatError: 'EMP-1' does not match ^EMP-[0-9]{6}$ (width 6, family transactional)
    """
    spine = snapshot.load()["keys"]
    m = KEY_RE.fullmatch(text) if isinstance(text, str) else None
    if not m or m.group(1) not in spine:
        raise KeyFormatError(f"{text!r} is not a typed key: expected PREFIX-digits with a prefix of design/keys.yaml (natural labels go through parse_label)")
    k = spine[m.group(1)]
    if not _rx(k["regex"]).fullmatch(text):
        raise KeyFormatError(f"{text!r} does not match {k['regex']} (width {k['width']}, family {k['family']})")
    return KeyParts(m.group(1), int(m.group(2)), len(m.group(2)), k["family"], k["entity"])


@function(oracle="py:../libs/halvaro-core/repo_tests/test_oracle_older_keys_access_facts.py::test_is_valid_key_oracle_baseline_keys_are_valid_and_damaged_keys_are_not")
def is_valid_key(text: Any, prefix: str | None = None) -> bool:
    """Use this when you only need to know whether a text is a valid typed key, without handling an error.

    Rule: the text must be a key of a prefix of the key list with the digits of its width; with a prefix it must be a key of that prefix.

    Args:
        text: The text to test; a value that is not a text is not a key.
        prefix: The prefix the key must have. Optional.

    Returns:
        bool: True for a valid key, False for anything else.

    Raises:
        Nothing is raised: a text that is not a key gives False.

    Example:
        >>> from halvaro.core import is_valid_key
        >>> is_valid_key("EMP-000001"), is_valid_key("EMP-1"), is_valid_key("EMP-000001", "GL")
        (True, False, False)
    """
    try:
        parts = parse_key(text)
    except KeyFormatError:
        return False
    return prefix is None or parts.prefix == prefix


@function(oracle="py:../libs/halvaro-core/repo_tests/test_oracle_older_keys_access_facts.py::test_master_of_oracle_the_master_table_of_a_prefix_holds_exactly_the_keys_of_that_prefix", parameters=("prefix",))
def master_of(prefix: str) -> MasterInfo:
    """Use this when you have a key prefix and need the entity it names and the table that is its master.

    Rule: the prefix is looked up in the master list of the design (master-of.yaml): the entity, the source, the table, the key column and the stage at which the master becomes visible.

    Args:
        prefix: A key prefix such as EMP.

    Returns:
        MasterInfo: prefix, entity, source, table, column and stage.

    Raises:
        KeyFormatError: the prefix has no master.

    Example:
        >>> from halvaro.core import master_of
        >>> info = master_of("EMP")
        >>> info.source, info.table, info.stage
        ('hr', 'employee', 'day1')
    """
    m = snapshot.load()["masters"].get(prefix)
    if m is None:
        raise KeyFormatError(f"prefix {prefix!r} has no master in design/master-of.yaml")
    return MasterInfo(prefix, m["entity"], m["source"], m["table"], m["column"], m["stage"])


@function(sources=(), oracle="py:../libs/halvaro-core/repo_tests/test_oracle_keys_repo.py::test_column_prefixes_oracle_every_foreign_key_column_of_the_dictionary")
def column_prefixes(column: str) -> tuple[str, ...]:
    """Use this when you need the key prefixes that a column of the data dictionary may hold, taken from its foreign key target.

    Rule: the prefixes are read from the dictionary for the column; a polymorphic column has several, and a column that is no foreign key has none.

    Args:
        column: The dictionary column as source.table.column, for example "competence.crew_plan.emp_key".

    Returns:
        tuple: the allowed prefixes as text, for example ('EMP',); empty when the column is no foreign key.

    Raises:
        FrameError: the column is not a column of the data dictionary.

    Example:
        >>> from halvaro.core import column_prefixes
        >>> column_prefixes("competence.crew_plan.emp_key")
        ('EMP',)
        >>> column_prefixes("competence.crew_plan.nothing")
        Traceback (most recent call last):
        ...
        halvaro.core.errors.FrameError: competence.crew_plan.nothing is not a column of the data dictionary; use source.table.column
    """
    snap = snapshot.load()
    if column not in snap["columns"]:
        raise FrameError(f"{column} is not a column of the data dictionary; use source.table.column")
    return tuple(snap["fk_prefixes"].get(column, ()))


@function(oracle="py:../libs/halvaro-core/repo_tests/test_oracle_keys_repo.py::test_check_key_column_oracle_baseline_keys_are_clean_and_corrupted_keys_are_found")
def check_key_column(frame: pd.DataFrame, column: str, target: str | None = None, allow_null: bool = False) -> pd.DataFrame:
    """Use this when you need to check that every value of a key column is a well formed key, and optionally that its prefix is one the dictionary allows for that column.

    Rule: each null is a violation "null" unless allow_null is set (one per null row). Each distinct non null value is checked once: a natural label (BUD, FC, GND, WST) must match the pattern of its kind, any other value must look like PREFIX-digits (else "bad_format"), carry a prefix of the key design (else "unknown_prefix") and match the pattern of that prefix (else "bad_format"). When target names a dictionary column that is a foreign key, a well formed key whose prefix is not one of the allowed prefixes of that column is a "wrong_prefix". A target without a foreign key adds no prefix check.

    Args:
        frame: The frame that holds the key column.
        column: The name of the key column in the frame.
        target: The dictionary column as source.table.column whose allowed prefixes apply. Optional; it also names the table in the result.
        allow_null: True when null keys are allowed. Optional, default False.

    Returns:
        pandas.DataFrame: the violations with the columns table, key, rule and detail, sorted by those columns; empty when all keys pass. The table is the target when given, else the column name; the key of a null is empty text.

    Raises:
        FrameError: the column is not a column of the frame, or target is given and is not a column of the data dictionary.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import check_key_column
        >>> frame = pd.DataFrame({"k": ["EMP-000001", "EMP-1", "DEP-01", None]})
        >>> check_key_column(frame, "k", "competence.crew_plan.emp_key")[["key", "rule"]]
                 key          rule
        0                     null
        1     DEP-01  wrong_prefix
        2      EMP-1    bad_format
    """
    if column not in frame.columns:
        raise FrameError(f"column {column} is missing in the frame; it has {', '.join(map(str, frame.columns[:8]))}")
    snap = snapshot.load()
    allowed = (set(column_prefixes(target)) or None) if target else None      # a column without fk_target imposes no prefix
    label = target or column
    rows = []
    s = frame[column]
    for _ in range(0 if allow_null else int(s.isna().sum())):
        rows.append((label, "", "null", "key is null"))
    for v in s.dropna().astype(str).unique():
        m = KEY_RE.fullmatch(v)
        pre = v.split("-", 1)[0]
        if pre in snap["natural_labels"]:
            ok = bool(_rx(snap["natural_labels"][pre]["regex"]).fullmatch(v))
        elif not m or pre not in snap["keys"]:
            rows.append((label, v, "unknown_prefix" if m else "bad_format", "prefix is not in design/keys.yaml" if m else "not PREFIX-digits"))
            continue
        else:
            ok = bool(_rx(snap["keys"][pre]["regex"]).fullmatch(v))
        if not ok:
            rows.append((label, v, "bad_format", "does not match the regex of its prefix"))
        elif allowed is not None and pre not in allowed:
            rows.append((label, v, "wrong_prefix", f"column holds {sorted(allowed)}, key has {pre}"))
    return violations.frame(rows)


@function(oracle="py:../libs/halvaro-core/repo_tests/test_oracle_keys_repo.py::test_check_polymorphic_oracle_baseline_columns_follow_their_type")
def check_polymorphic(frame: pd.DataFrame, key_column: str, type_column: str, mapping: Mapping[Any, str | None] | None = None) -> pd.DataFrame:
    """Use this when a key column can hold keys of different kinds and a type column says which kind each row has, and you need the rows where the two disagree.

    Rule: for each distinct pair of type and key (rows with a null key are skipped) the prefix is the text of the key before the first dash. With a mapping the type must be a key of the mapping and the prefix must equal its value; a value None means the type is free text and is not checked. Without a mapping the type value itself is the expected prefix. A type that is not in the mapping gives "unknown_type", a prefix that differs gives "wrong_prefix".

    Args:
        frame: The frame that holds both columns.
        key_column: The column with the keys.
        type_column: The column with the type of each key.
        mapping: A mapping from a type value to the expected prefix, or None for a type that is not checked. Optional; without it the type column holds the prefix.

    Returns:
        pandas.DataFrame: the violations with the columns table, key, rule and detail, sorted by those columns; the table is the name of the key column. Empty when all rows agree.

    Raises:
        FrameError: key_column or type_column is not a column of the frame.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import check_polymorphic
        >>> frame = pd.DataFrame({"t": ["employee", "external", "employee"], "k": ["EMP-000001", "CNT-000001", "CNT-000002"]})
        >>> check_polymorphic(frame, "k", "t", {"employee": "EMP", "external": "CNT"})[["key", "rule", "detail"]]
                  key          rule                                  detail
        0  CNT-000002  wrong_prefix  t='employee' implies EMP, key has CNT
    """
    for c in (key_column, type_column):
        if c not in frame.columns:
            raise FrameError(f"column {c} is missing in the frame")
    rows = []
    for t, v in frame[[type_column, key_column]].dropna(subset=[key_column]).drop_duplicates().itertuples(index=False):
        pre = str(v).split("-", 1)[0]
        want = t if mapping is None else mapping.get(t, "?")
        if want == "?":
            rows.append((key_column, str(v), "unknown_type", f"{type_column} value {t!r} is not in the mapping"))
        elif want is not None and pre != want:
            rows.append((key_column, str(v), "wrong_prefix", f"{type_column}={t!r} implies {want}, key has {pre}"))
    return violations.frame(rows)


@function(oracle="py:../libs/halvaro-core/repo_tests/test_oracle_keys_repo.py::test_parse_label_oracle_every_natural_label_and_gl_account_of_the_baseline")
def parse_label(text: str) -> LabelParts:
    """Use this when you have a natural label (a budget, forecast, waste or ground label) or a GL account and need its parts.

    Rule: the text before the first dash picks the label kind; the label must match the pattern of its kind. A GL account is read as a key of the GL prefix.

    Args:
        text: The label as text.

    Returns:
        LabelParts: prefix, text, source, table and column of the master.

    Raises:
        KeyFormatError: the text is not a known label or does not match the pattern of its kind.

    Example:
        >>> from halvaro.core import parse_label
        >>> label = parse_label("GL-7000")
        >>> label.prefix, label.table
        ('GL', 'gl_account')
        >>> parse_label("XX-1")
        Traceback (most recent call last):
        ...
        halvaro.core.errors.KeyFormatError: 'XX-1' is not a natural label; known: ...
    """
    snap = snapshot.load()
    pre = text.split("-", 1)[0] if isinstance(text, str) else ""
    n = snap["natural_labels"].get(pre)
    if n is None:
        if pre == "GL":
            p = parse_key(text)
            return LabelParts(p.prefix, text, snap["masters"]["GL"]["source"], snap["masters"]["GL"]["table"], snap["masters"]["GL"]["column"])
        raise KeyFormatError(f"{text!r} is not a natural label; known: {', '.join(sorted(snap['natural_labels']))} and GL")
    if not _rx(n["regex"]).fullmatch(text):
        raise KeyFormatError(f"{text!r} does not match {n['regex']}")
    src, tbl = n["table"].split(".")
    return LabelParts(pre, text, src, tbl, n["column"])


@function(oracle="py:../libs/halvaro-core/repo_tests/test_oracle_older_keys_access_facts.py::test_table_key_oracle_the_key_columns_are_unique_and_not_null_in_the_baseline_and_in_the_dictionary")
def table_key(source_table: str) -> tuple[str, ...]:
    """Use this when you need the columns that make up the primary key of a table, composite keys included.

    Rule: the key columns are read from the table keys of the release, in the order they are listed there.

    Args:
        source_table: The table as source.table, for example "competence.crew_plan".

    Returns:
        tuple: the names of the key columns, one for a simple key and several for a composite key.

    Raises:
        FrameError: the table is not a table of the release.

    Example:
        >>> from halvaro.core import table_key
        >>> table_key("competence.crew_plan")
        ('prj_key', 'emp_key')
        >>> table_key("competence.nothing")
        Traceback (most recent call last):
        ...
        halvaro.core.errors.FrameError: competence.nothing is not a table of the release; use source.table
    """
    k = snapshot.load()["table_keys"].get(source_table)
    if k is None:
        raise FrameError(f"{source_table} is not a table of the release; use source.table")
    return tuple(k["key"])
