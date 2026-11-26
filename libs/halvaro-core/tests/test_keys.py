"""C1: keys, with the dictionary foreign key map checked on the release."""
import pandas as pd
import pytest

import halvaro.core as core
from halvaro.core import snapshot


def test_every_prefix_sample_parses_and_reports_width_and_family():
    spine = snapshot.load()["keys"]
    assert len(spine) == 34
    for p, k in spine.items():
        text = f"{p}-{1:0{k['width']}d}"
        parts = core.parse_key(text)
        assert (parts.prefix, parts.number, parts.width, parts.family) == (p, 1, k["width"], k["family"])
        assert core.is_valid_key(text) and core.is_valid_key(text, p) and not core.is_valid_key(text, "XXX")


@pytest.mark.parametrize("bad", ["emp-000001", "EMP-1", "EMP-0000001", "XYZ-000001", "EMP000001", "EMP-00000a", "", None, 7, "WST-01", "LE-1"])
def test_bad_keys_raise_and_are_not_valid(bad):
    assert not core.is_valid_key(bad)
    with pytest.raises(core.KeyFormatError):
        core.parse_key(bad)


def test_master_of():
    m = core.master_of("EMP")
    assert (m.source, m.table, m.column, m.stage) == ("hr", "employee", "emp_key", "day1")
    assert core.master_of("INV").stage == "month3" and core.master_of("PRJ").stage == "month12"
    assert core.master_of("WST").table == "weather_station"
    with pytest.raises(core.KeyFormatError):
        core.master_of("XYZ")


def test_column_prefixes_from_fk_target_not_from_the_name():
    assert core.column_prefixes("hr.employment_term.manager_emp_key") == ("EMP",)
    assert core.column_prefixes("competence.requirement.scope_key") == ("CON", "PRJ", "ROLE")
    assert core.column_prefixes("hr.employee.username") == ()
    with pytest.raises(core.FrameError):
        core.column_prefixes("hr.employee.no_such_column")


def test_check_key_column_rules():
    df = pd.DataFrame({"k": ["EMP-000001", "PRJ-000002", None, "emp-1", "ZZZ-000001", "EMP-00000009", "BUD-2024", "BUD-24"]})
    v = core.check_key_column(df, "k", "hr.employment_term.manager_emp_key")
    got = {(r.key, r.rule) for r in v.itertuples()}
    assert got == {("PRJ-000002", "wrong_prefix"), ("", "null"), ("emp-1", "bad_format"), ("ZZZ-000001", "unknown_prefix"),
                   ("EMP-00000009", "bad_format"), ("BUD-2024", "wrong_prefix"), ("BUD-24", "bad_format")}
    assert list(v.columns) == ["table", "key", "rule", "detail"] and v.equals(core.check_key_column(df, "k", "hr.employment_term.manager_emp_key"))
    assert len(core.check_key_column(df[["k"]].iloc[:1], "k")) == 0
    assert not core.check_key_column(pd.DataFrame({"k": ["BUD-2024"]}), "k", "finance.budget_line.budget_version").shape[0], "no fk_target, no prefix rule"
    assert not core.check_key_column(pd.DataFrame({"k": [None, "EMP-000001"]}), "k", allow_null=True).shape[0]
    with pytest.raises(core.FrameError):
        core.check_key_column(df, "missing")


def test_check_polymorphic():
    df = pd.DataFrame({"k": ["ROLE-001", "PRJ-000001", "CON-000001", "free text", "PRJ-000002"], "t": ["role", "project", "contract", "project_type", "role"]})
    mapping = {"role": "ROLE", "project": "PRJ", "contract": "CON", "project_type": None}
    v = core.check_polymorphic(df, "k", "t", mapping)
    assert [(r.key, r.rule) for r in v.itertuples()] == [("PRJ-000002", "wrong_prefix")]
    refs = pd.DataFrame({"k": ["MTR-0001", "SUP-000001", "MTR-0002"], "t": ["MTR", "SUP", "PRJ"]})
    assert [r.key for r in core.check_polymorphic(refs, "k", "t").itertuples()] == ["MTR-0002"]
    assert core.check_polymorphic(pd.DataFrame({"k": ["X-1"], "t": ["alien"]}), "k", "t", mapping).iloc[0]["rule"] == "unknown_type"


def test_parse_label_natural_labels():
    assert core.parse_label("WST-01").table == "weather_station" and core.parse_label("GND-00012").column == "area_id"
    assert core.parse_label("BUD-2024").prefix == "BUD" and core.parse_label("FC-2024-Q3").table == "forecast_version"
    assert core.parse_label("GL-3000").prefix == "GL"
    for bad in ("WST-1", "BUD-24", "FC-2024-Q5", "EMP-000001", "nonsense", None):
        with pytest.raises(core.KeyFormatError):
            core.parse_label(bad)


def test_table_key():
    assert core.table_key("hr.employee") == ("emp_key",)
    assert core.table_key("hr.holiday_accrual") == ("emp_key", "holiday_year", "period")
    with pytest.raises(core.FrameError):
        core.table_key("hr.nope")
