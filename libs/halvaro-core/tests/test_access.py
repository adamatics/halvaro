"""C2: stage, role and restricted columns, aggregate guard."""
import datetime as dt

import pandas as pd
import pytest

import halvaro.core as core

PAY = "hr.employment_term.base_salary"


def test_context_from_profile():
    c = core.Context.from_profile("halvaro-stage2", now=dt.date(2026, 11, 30))
    assert (c.stage, c.role, c.restricted_ok) == ("month3", "halvaro_stage2", False)
    assert core.Context.from_profile("mcp_people_hr", stage="day1").restricted_ok
    assert not core.Context.from_profile("mcp_people", stage="day1").restricted_ok
    assert core.Context.from_profile("api_hr", stage="month12").restricted_ok
    assert core.Context.from_profile("mcp_people", stage="day1", restricted_ok=True).restricted_ok
    for bad in ("mcp_people", "root", "halvaro-stage4"):
        with pytest.raises(core.ProfileError):
            core.Context.from_profile(bad)
    with pytest.raises(core.ProfileError):
        core.Context(stage="day9", role="x")


def test_stages_are_cumulative_and_sources_have_a_stage():
    assert core.visible_sources("day1") == {"hr"} and core.visible_sources("month3") == {"hr", "finance"} and len(core.visible_sources("month12")) == 14
    assert core.source_stage("finance") == "month3" and core.source_stage("telemetry") == "month12"
    with pytest.raises(core.FrameError):
        core.source_stage("payroll")


def test_stage_matrix_names_the_missing_source():
    """A month3 function at day1 refuses and names finance and the stage where it appears."""
    day1, month3, month12 = (core.Context(stage=s, role="r") for s in ("day1", "month3", "month12"))
    with pytest.raises(core.StageRefusal) as e:
        core.require_sources(day1, ["hr", "finance"], function="halvaro.hr.staffing.planned_vs_actual_hours")
    assert e.value.missing_sources == ("finance",) and e.value.stage_needed == "month3" and e.value.stage_held == "day1"
    core.require_sources(month3, ["hr.employee.emp_key", "finance"])
    with pytest.raises(core.StageRefusal) as e:
        core.require_sources(month3, ["projects", "competence", "hr"])
    assert e.value.missing_sources == ("competence", "projects") and e.value.stage_needed == "month12"
    core.require_sources(month12, list(core.visible_sources("month12")))
    assert core.stage_banner(e.value).startswith("Needs competence, projects (appears at stage month12)")


def test_restricted_column_refused_for_mcp_people_and_allowed_for_hr_role():
    with pytest.raises(core.RestrictedColumnRefusal) as e:
        core.require_columns(core.Context.from_profile("mcp_people", stage="day1"), ["hr.employee.emp_key", PAY])
    assert e.value.column == PAY and e.value.role == "mcp_people"
    assert "Restricted column" in core.stage_banner(e.value)
    core.require_columns(core.Context.from_profile("mcp_people_hr", stage="day1"), [PAY])
    core.require_columns(core.Context.from_profile("mcp_people", stage="day1"), ["hr.employee.emp_key"])
    with pytest.raises(core.RestrictedColumnRefusal):
        core.require_columns(core.Context.from_profile("halvaro-stage1"), [PAY]), "stage profiles refuse unless the context says restricted ok"


def test_aggregate_guard():
    persons = pd.DataFrame({"emp_key": ["EMP-000001", "EMP-000002"], "base_salary": [1, 2]})
    with pytest.raises(core.AggregateRefusal, match="emp_key"):
        core.assert_aggregate(persons, "base_salary")
    by_dept = pd.DataFrame({"dep_key": ["DEP-01", "DEP-02"], "base_salary": [10.0, 20.0], "n": [12, 3]})
    agg = core.mark_aggregate(by_dept, "base_salary", ("dep_key",))
    assert isinstance(agg, core.RestrictedAggregate) and agg.group_columns == ("dep_key",)
    core.assert_aggregate(by_dept, "base_salary", min_group=3, count_column="n")
    with pytest.raises(core.AggregateRefusal, match="fewer than 8"):
        core.assert_aggregate(by_dept, "base_salary", min_group=8, count_column="n")
    with pytest.raises(core.FrameError):
        core.assert_aggregate(by_dept, "base_salary", min_group=8)
    with pytest.raises(core.FrameError):
        core.assert_aggregate(by_dept, "nope")


def test_strip_restricted():
    df = pd.DataFrame({"team_key": ["TEAM-001"], "base_salary": [1], "fte": [1.0]})
    assert list(core.strip_restricted(df, core.Context.from_profile("mcp_people", stage="day1")).columns) == ["team_key", "fte"]
    assert list(core.strip_restricted(df, core.Context.from_profile("mcp_people_hr", stage="day1")).columns) == list(df.columns)
