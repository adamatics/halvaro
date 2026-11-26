"""Reference organisation lookups over the hr and finance reference frames (no person level terms)."""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any, cast

import pandas as pd

from . import calendar, snapshot, violations
from .errors import FrameError
from .registry import function

TEAM = ("hr.team.team_key", "hr.team.dep_key", "hr.team.cost_centre_key", "hr.team.legal_entity_key", "hr.team.site_key", "hr.site.country")


def _need(frame: pd.DataFrame, columns: Sequence[str], what: str) -> None:
    missing = [c for c in columns if c not in frame.columns]
    if missing:
        raise FrameError(f"{what} frame lacks column(s) {', '.join(missing)}")


@function(sources=TEAM, oracle="py:../libs/halvaro-core/repo_tests/test_oracle_org_release.py::test_team_context_oracle_baseline_every_team_with_site_country_and_region")
def team_context(team: pd.DataFrame, site: pd.DataFrame) -> pd.DataFrame:
    """Use this when you need per team its department, cost centre, legal entity, site, country and calendar region in one frame.

    Rule: the site frame is joined to the team frame on the site key; the region is read from the site key by region_of.

    Args:
        team: Team frame (hr.team) with team_key, dep_key, cost_centre_key, legal_entity_key and site_key.
        site: Site frame (hr.site) with site_key and country.

    Returns:
        pandas.DataFrame: the five team columns, country and region, one row per team in the order of the team frame.

    Raises:
        FrameError: a frame lacks a column.
        UnknownRegion: a team has a site that has no region.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import team_context
        >>> team = pd.DataFrame({"team_key": ["T1"], "dep_key": ["D1"], "cost_centre_key": ["CC-1"], "legal_entity_key": ["LE-01"], "site_key": ["SITE-05"]})
        >>> site = pd.DataFrame({"site_key": ["SITE-05"], "country": ["DE"]})
        >>> team_context(team, site)[["team_key", "country", "region"]].to_dict("records")
        [{'team_key': 'T1', 'country': 'DE', 'region': 'DE-HH'}]
    """
    _need(team, ["team_key", "dep_key", "cost_centre_key", "legal_entity_key", "site_key"], "hr.team")
    _need(site, ["site_key", "country"], "hr.site")
    out = team[["team_key", "dep_key", "cost_centre_key", "legal_entity_key", "site_key"]].merge(site[["site_key", "country"]], on="site_key", how="left")
    out["region"] = out["site_key"].map(calendar.region_of)
    return out


@function(sources=("hr.role.role_key", "hr.role.dep_key", "hr.role.gra_key", "hr.grade.level"), oracle="py:../libs/halvaro-core/repo_tests/test_oracle_org_release.py::test_role_info_oracle_baseline_every_role_gets_its_grade")
def role_info(role: pd.DataFrame, grade: pd.DataFrame) -> pd.DataFrame:
    """Use this when you need per role its department and grade, with the grade level, name and bands.

    Rule: the grade columns of grade_info are joined to the role frame on the grade key as a left join, so a role whose grade is not in the grade frame keeps its row and gets empty grade columns. The grade name arrives as name_grade because the role has a name of its own.

    Args:
        role: Role frame (hr.role) with role_key, name, dep_key and gra_key.
        grade: Grade frame (hr.grade) with gra_key, level, name and the four band columns.

    Returns:
        pandas.DataFrame: role_key, name, dep_key, gra_key, level, name_grade, band_min_dkk, band_max_dkk, band_min_eur and band_max_eur, one row per role in the order of the role frame (as long as gra_key is unique in the grade frame).

    Raises:
        FrameError: the role frame or the grade frame lacks a column.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import role_info
        >>> role = pd.DataFrame({"role_key": ["R1", "R2"], "name": ["Analyst", "Lead"], "dep_key": ["D1", "D1"], "gra_key": ["G1", "G9"]})
        >>> grade = pd.DataFrame({"gra_key": ["G1"], "level": [3], "name": ["Grade 3"], "band_min_dkk": [10], "band_max_dkk": [20], "band_min_eur": [1], "band_max_eur": [2]})
        >>> info = role_info(role, grade)
        >>> info[["role_key", "gra_key", "level", "name_grade"]].to_dict("records")
        [{'role_key': 'R1', 'gra_key': 'G1', 'level': 3.0, 'name_grade': 'Grade 3'}, {'role_key': 'R2', 'gra_key': 'G9', 'level': nan, 'name_grade': nan}]
    """
    _need(role, ["role_key", "name", "dep_key", "gra_key"], "hr.role")
    return role[["role_key", "name", "dep_key", "gra_key"]].merge(grade_info(grade), on="gra_key", how="left", suffixes=("", "_grade"))


@function(sources=("hr.grade.gra_key", "hr.grade.level"), oracle="py:../libs/halvaro-core/repo_tests/test_oracle_org_release.py::test_grade_info_oracle_baseline_rows_and_bands")
def grade_info(grade: pd.DataFrame) -> pd.DataFrame:
    """Use this when you need the grade level, name and bands in DKK and EUR from the grade frame.

    Rule: the seven grade columns are taken from the grade frame as they are. Nothing is converted, checked or dropped, and the rows keep their order.

    Args:
        grade: Grade frame (hr.grade) with gra_key, level, name, band_min_dkk, band_max_dkk, band_min_eur and band_max_eur.

    Returns:
        pandas.DataFrame: a copy with the columns gra_key, level, name, band_min_dkk, band_max_dkk, band_min_eur and band_max_eur, one row per row of the grade frame; other columns of the input are left out.

    Raises:
        FrameError: the grade frame lacks one of the seven columns.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import grade_info
        >>> grade = pd.DataFrame({"gra_key": ["G1"], "level": [3], "name": ["Grade 3"], "band_min_dkk": [10], "band_max_dkk": [20], "band_min_eur": [1], "band_max_eur": [2], "extra": ["x"]})
        >>> grade_info(grade).columns.tolist()
        ['gra_key', 'level', 'name', 'band_min_dkk', 'band_max_dkk', 'band_min_eur', 'band_max_eur']
        >>> int(grade_info(grade)["band_max_dkk"].iloc[0])
        20
    """
    cols = ["gra_key", "level", "name", "band_min_dkk", "band_max_dkk", "band_min_eur", "band_max_eur"]
    _need(grade, cols, "hr.grade")
    return grade[cols].copy()


@function(sources=("hr.team.team_key", "hr.team.cost_centre_key"), oracle="py:../libs/halvaro-core/repo_tests/test_oracle_older_money_frames_org.py::test_cost_centre_of_team_oracle_every_team_of_the_baseline_against_a_dictionary")
def cost_centre_of_team(team: pd.DataFrame, team_key: str) -> str:
    """Use this when you need the cost centre key of one team.

    Rule: the team frame is searched for the team key and the cost centre key of that one row is returned. A team that is missing or listed more than once is refused, never guessed.

    Args:
        team: Team frame (hr.team) with team_key and cost_centre_key.
        team_key: The key of the team, for example "T1".

    Returns:
        str: the cost centre key of the team, for example "CC-1".

    Raises:
        FrameError: the frame lacks a column, or the team key does not match exactly one row.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import cost_centre_of_team
        >>> team = pd.DataFrame({"team_key": ["T1", "T2"], "cost_centre_key": ["CC-1", "CC-2"]})
        >>> cost_centre_of_team(team, "T2")
        'CC-2'
        >>> cost_centre_of_team(team, "T9")
        Traceback (most recent call last):
        ...
        halvaro.core.errors.FrameError: team T9 has 0 rows in hr.team; expected 1
    """
    _need(team, ["team_key", "cost_centre_key"], "hr.team")
    hit = team.loc[team["team_key"] == team_key, "cost_centre_key"]
    if len(hit) != 1:
        raise FrameError(f"team {team_key} has {len(hit)} rows in hr.team; expected 1")
    return cast(str, hit.iloc[0])


@function(sources=("hr.team.team_key", "hr.team.cost_centre_key"), oracle="py:../libs/halvaro-core/repo_tests/test_oracle_org_release.py::test_team_of_cost_centre_oracle_round_trip_with_cost_centre_of_team_for_every_team")
def team_of_cost_centre(team: pd.DataFrame, cost_centre_key: str) -> str:
    """Use this when you need the team that owns one cost centre.

    Rule: the team frame is searched for the cost centre key and the team key of that one row is returned. A cost centre that is missing or shared by several teams is refused, never guessed.

    Args:
        team: Team frame (hr.team) with team_key and cost_centre_key.
        cost_centre_key: The cost centre key, for example "CC-1".

    Returns:
        str: the key of the team that has the cost centre, for example "T1".

    Raises:
        FrameError: the frame lacks a column, or the cost centre does not belong to exactly one team.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import team_of_cost_centre
        >>> team = pd.DataFrame({"team_key": ["T1", "T2"], "cost_centre_key": ["CC-1", "CC-2"]})
        >>> team_of_cost_centre(team, "CC-2")
        'T2'
        >>> team_of_cost_centre(team, "CC-9")
        Traceback (most recent call last):
        ...
        halvaro.core.errors.FrameError: cost centre CC-9 belongs to 0 teams; expected 1
    """
    _need(team, ["team_key", "cost_centre_key"], "hr.team")
    hit = team.loc[team["cost_centre_key"] == cost_centre_key, "team_key"]
    if len(hit) != 1:
        raise FrameError(f"cost centre {cost_centre_key} belongs to {len(hit)} teams; expected 1")
    return cast(str, hit.iloc[0])


@function(sources=("hr.team.team_key", "hr.team.lead_emp_key", "hr.department.dep_key", "hr.site.site_key"), oracle="py:../libs/halvaro-core/repo_tests/test_oracle_older_money_frames_org.py::test_check_org_integrity_oracle_the_baseline_is_clean_and_each_defect_gives_its_own_rule")
def check_org_integrity(team: pd.DataFrame, department: pd.DataFrame, site: pd.DataFrame, cost_centre: pd.DataFrame | None = None,
                        expected: dict[str, int] | None = None) -> pd.DataFrame:
    """Use this when you need to check the organisation frames for broken references, missing leads and cost centres, and wrong counts.

    Rule: one violation row is written per broken rule, with the rule count (the row count differs from the expected count, or a key is repeated), no_cost_centre, cost_centre_not_unique (shared by several teams), no_lead, dangling (the department or site key of a team is not in its frame) or pairing (only when cost_centre is passed: the cost centre of a team is missing there or points to another team). A team without a cost centre therefore also gets a pairing row when cost_centre is passed. A clean organisation gives an empty frame.

    Args:
        team: Team frame (hr.team) with team_key, dep_key, cost_centre_key, site_key and lead_emp_key.
        department: Department frame (hr.department) with dep_key.
        site: Site frame (hr.site) with site_key.
        cost_centre: Optional cost centre frame (finance.cost_centre) with cc_key and team_key. Without it the pairing rule is not checked.
        expected: Optional expected row counts as a dict with the keys teams, departments and sites. Without it (or when empty) the counts of the snapshot are used.

    Returns:
        pandas.DataFrame: one row per violation with the columns table, key, rule and detail, sorted by those four columns; empty when nothing is broken.

    Raises:
        FrameError: the team frame lacks a column, or the cost centre frame lacks cc_key or team_key.
        KeyError: the department frame lacks dep_key, the site frame lacks site_key, or expected lacks one of teams, departments and sites.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import check_org_integrity
        >>> team = pd.DataFrame({"team_key": ["T1", "T2"], "dep_key": ["D1", "D1"], "cost_centre_key": ["CC-1", "CC-2"], "site_key": ["S1", "S1"], "lead_emp_key": ["EMP-X", None]})
        >>> department, site = pd.DataFrame({"dep_key": ["D1"]}), pd.DataFrame({"site_key": ["S1"]})
        >>> found = check_org_integrity(team, department, site, expected={"teams": 2, "departments": 1, "sites": 1})
        >>> found.to_dict("records")
        [{'table': 'hr.team', 'key': 'T2', 'rule': 'no_lead', 'detail': 'team has no lead'}]
    """
    _need(team, ["team_key", "dep_key", "cost_centre_key", "site_key", "lead_emp_key"], "hr.team")
    exp = expected or snapshot.load()["org_expected"]
    rows: list[tuple[Any, ...]] = []
    for name, frame, key in (("teams", team, "team_key"), ("departments", department, "dep_key"), ("sites", site, "site_key")):
        if len(frame) != exp[name] or frame[key].duplicated().any():
            rows.append((name, "", "count", f"{len(frame)} rows, {frame[key].nunique()} distinct, expected {exp[name]}"))
    for r in team[team["cost_centre_key"].isna()].itertuples():
        rows.append(("hr.team", r.team_key, "no_cost_centre", "team has no cost centre"))
    for cc, grp in team[team["cost_centre_key"].notna()].groupby("cost_centre_key"):
        if len(grp) > 1:
            rows.append(("hr.team", cc, "cost_centre_not_unique", f"shared by {', '.join(grp.team_key)}"))
    for r in team[team["lead_emp_key"].isna()].itertuples():
        rows.append(("hr.team", r.team_key, "no_lead", "team has no lead"))
    for col, ref, label in (("dep_key", department["dep_key"], "department"), ("site_key", site["site_key"], "site")):
        for r in team[~team[col].isin(ref)].itertuples():
            rows.append(("hr.team", r.team_key, "dangling", f"{label} {getattr(r, col)} is not in the {label} frame"))
    if cost_centre is not None:
        _need(cost_centre, ["cc_key", "team_key"], "finance.cost_centre")
        pair = team.merge(cost_centre[["cc_key", "team_key"]], left_on="cost_centre_key", right_on="cc_key", how="left", suffixes=("", "_fin"))
        for r in pair[pair["team_key_fin"] != pair["team_key"]].itertuples():
            rows.append(("finance.cost_centre", r.team_key, "pairing", f"{r.cost_centre_key} points to {r.team_key_fin}"))
    return violations.frame(rows)
