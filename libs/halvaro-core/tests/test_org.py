"""C2: reference organisation."""
import pandas as pd
import pytest

import halvaro.core as core


def _org():
    team = pd.DataFrame({"team_key": ["TEAM-001", "TEAM-002", "TEAM-003"], "name": list("abc"), "dep_key": ["DEP-01", "DEP-01", "DEP-02"],
                         "cost_centre_key": ["CC-0001", "CC-0002", "CC-0003"], "legal_entity_key": ["LE-01", "LE-01", "LE-02"],
                         "site_key": ["SITE-01", "SITE-02", "SITE-05"], "lead_emp_key": ["EMP-000001", "EMP-000002", "EMP-000003"]})
    dep = pd.DataFrame({"dep_key": ["DEP-01", "DEP-02"]})
    site = pd.DataFrame({"site_key": ["SITE-01", "SITE-02", "SITE-05"], "country": ["DK", "DK", "DE"]})
    return team, dep, site


def test_team_context_adds_country_and_region():
    team, _, site = _org()
    out = core.team_context(team, site)
    assert out.set_index("team_key").loc["TEAM-003", ["country", "region", "dep_key"]].tolist() == ["DE", "DE-HH", "DEP-02"]
    assert out.set_index("team_key").loc["TEAM-001", "region"] == "DK"
    with pytest.raises(core.FrameError, match="hr.site"):
        core.team_context(team, site.drop(columns="country"))


def test_role_and_grade_info():
    grade = pd.DataFrame({"gra_key": ["GRA-01"], "level": [1], "name": ["Entry"], "band_min_dkk": [1], "band_max_dkk": [2], "band_min_eur": [3], "band_max_eur": [4]})
    role = pd.DataFrame({"role_key": ["ROLE-001"], "name": ["Welder"], "dep_key": ["DEP-02"], "gra_key": ["GRA-01"]})
    out = core.role_info(role, grade)
    assert out.iloc[0][["role_key", "level", "band_max_eur", "name_grade"]].tolist() == ["ROLE-001", 1, 4, "Entry"]
    assert list(core.grade_info(grade).columns)[:3] == ["gra_key", "level", "name"]


def test_cost_centre_lookups_both_ways():
    team, _, _ = _org()
    assert core.cost_centre_of_team(team, "TEAM-002") == "CC-0002" and core.team_of_cost_centre(team, "CC-0003") == "TEAM-003"
    for call in (lambda: core.cost_centre_of_team(team, "TEAM-999"), lambda: core.team_of_cost_centre(pd.concat([team, team]), "CC-0001")):
        with pytest.raises(core.FrameError):
            call()


def test_check_org_integrity_rules():
    team, dep, site = _org()
    exp = {"teams": 3, "departments": 2, "sites": 3}
    assert len(core.check_org_integrity(team, dep, site, expected=exp)) == 0
    bad = team.copy()
    bad.loc[1, "cost_centre_key"] = "CC-0001"
    bad.loc[2, ["lead_emp_key", "site_key", "dep_key"]] = [None, "SITE-09", "DEP-09"]
    got = core.check_org_integrity(bad, dep, site, expected=exp)
    assert sorted(set(got.rule)) == ["cost_centre_not_unique", "dangling", "no_lead"]
    assert [r.rule for r in core.check_org_integrity(team, dep, site, expected={**exp, "teams": 51}).itertuples()] == ["count"]
    fin = pd.DataFrame({"cc_key": ["CC-0001", "CC-0002", "CC-0003"], "team_key": ["TEAM-001", "TEAM-003", "TEAM-003"]})
    assert [(r.rule, r.key) for r in core.check_org_integrity(team, dep, site, fin, exp).itertuples()] == [("pairing", "TEAM-002")]
