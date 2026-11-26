"""halvaro.core: shared foundation of the Halvaro Infra libraries. Importing this package does no I/O."""
from . import access, calendar, errors, facts, format, frames, keys, money, org, periods, registry, testing, theme, violations
from ._version import __version__
from .access import (Context, RestrictedAggregate, assert_aggregate, mark_aggregate, require_columns, require_sources, source_stage, stage_banner,
                     strip_restricted, visible_sources)
from .calendar import (add_working_days, is_working_day, net_working_days, public_holidays, region_of, working_days)
from .envelope import Envelope, make_envelope
from .errors import (AggregateRefusal, AmbiguousKey, BasisError, FactNotFound, FrameError, FrameMissing, HalvaroError, KeyFormatError, PeriodError,
                     ProfileError, ReleaseMismatch, RestrictedColumnRefusal, StageRefusal, SumGuardError, UnknownRegion, UnmatchedKeys)
from .facts import Fact, cfg, combine_status, fact
from .format import format_money, format_number, format_percent
from .frames import JoinResult, UnmatchedReport, join_report, reduce_chunks, require_frame_columns
from .keys import (KeyParts, LabelParts, MasterInfo, check_key_column, check_polymorphic, column_prefixes, is_valid_key, master_of, parse_key,
                   parse_label, table_key)
from .money import convert, from_cents, guarded_sum, rdiv, to_cents
from .org import (check_org_integrity, cost_centre_of_team, grade_info, role_info, team_context, team_of_cost_centre)
from .periods import (ReleaseInfo, add_months, asof_join, check_contiguity, compare_periods, interval_join, month_end, month_start, parse_period, period_of, period_range,
                      release_now, rows_on, year_of)
from .registry import FunctionMeta, check, export_index, function, registered
from .snapshot import snapshot_hash
from .testing import asof_stable, loader_contract, stage_matrix
from .theme import apply_theme, caption, footer, line_with_gaps, map_label, stage_placeholder, synthetic_label

__all__ = [
    "__version__", "Envelope", "make_envelope", "Fact", "fact", "cfg", "combine_status", "FunctionMeta", "function", "registered", "export_index", "check",
    "snapshot_hash",
    "HalvaroError", "StageRefusal", "RestrictedColumnRefusal", "AmbiguousKey", "UnmatchedKeys", "KeyFormatError", "FrameError", "FrameMissing",
    "ReleaseMismatch", "SumGuardError", "UnknownRegion", "PeriodError", "FactNotFound", "ProfileError", "AggregateRefusal", "BasisError",
    "KeyParts", "MasterInfo", "LabelParts", "parse_key", "is_valid_key", "master_of", "column_prefixes", "check_key_column", "check_polymorphic",
    "parse_label", "table_key",
    "ReleaseInfo", "parse_period", "period_of", "month_start", "month_end", "add_months", "compare_periods", "period_range", "year_of", "rows_on",
    "asof_join", "check_contiguity", "release_now",
    "Context", "RestrictedAggregate", "source_stage", "visible_sources", "require_sources", "require_columns", "assert_aggregate", "mark_aggregate",
    "strip_restricted", "stage_banner",
    "team_context", "role_info", "grade_info", "cost_centre_of_team", "team_of_cost_centre", "check_org_integrity",
    "public_holidays", "region_of", "is_working_day", "working_days", "add_working_days", "net_working_days",
    "to_cents", "from_cents", "rdiv", "convert", "guarded_sum", "reduce_chunks", "interval_join",
    "format_number", "format_percent", "format_money", "synthetic_label", "map_label", "caption", "footer", "stage_placeholder", "line_with_gaps", "apply_theme", "stage_matrix", "asof_stable", "loader_contract",
    "JoinResult", "UnmatchedReport", "join_report", "require_frame_columns",
]
