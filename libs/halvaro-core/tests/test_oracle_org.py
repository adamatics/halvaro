"""Oracles of halvaro.core.org (lane L1). The baseline tables are read with pyarrow into plain dictionaries and the expected rows are built with dictionary lookups and loops; the library
functions use pandas merges. Hand worked frames cover the refusals."""
import pandas as pd
import pytest

import halvaro.core as core


def test_grade_info_oracle_a_missing_column_is_refused_with_its_name():
    """halvaro.core.org.grade_info: a frame without a band column raises FrameError naming the column."""
    frame = pd.DataFrame({"gra_key": ["GRA-01"], "level": [1], "name": ["x"], "band_min_dkk": [1], "band_max_dkk": [2], "band_min_eur": [1]})
    with pytest.raises(core.FrameError, match="band_max_eur"):
        core.grade_info(frame)


def test_role_info_oracle_hand_worked_unknown_grade_and_missing_column():
    """halvaro.core.org.role_info: a role whose grade is not in the grade frame stays with empty grade columns (left join); a role frame without dep_key is refused."""
    role = pd.DataFrame({"role_key": ["R1", "R2"], "name": ["a", "b"], "dep_key": ["D1", "D1"], "gra_key": ["G1", "G9"]})
    grade = pd.DataFrame({"gra_key": ["G1"], "level": [3], "name": ["g"], "band_min_dkk": [1], "band_max_dkk": [2], "band_min_eur": [1], "band_max_eur": [2]})
    got = core.role_info(role, grade)
    assert got["role_key"].tolist() == ["R1", "R2"] and got["level"].tolist()[0] == 3 and pd.isna(got["level"].tolist()[1]) and got["name_grade"].tolist()[0] == "g"
    with pytest.raises(core.FrameError, match="dep_key"):
        core.role_info(role.drop(columns="dep_key"), grade)


def test_team_context_oracle_hand_worked_unknown_site_and_missing_columns():
    """halvaro.core.org.team_context: the country comes from the site frame and the region from the library's own site map; a team on a site the library does not know is refused by region_of, a team
    on a known site that is missing from the site frame keeps its region and gets no country; missing columns are named."""
    team = pd.DataFrame({"team_key": ["T1"], "dep_key": ["D"], "cost_centre_key": ["C"], "legal_entity_key": ["L"], "site_key": ["SITE-77"]})
    site = pd.DataFrame({"site_key": ["SITE-01"], "country": ["DK"]})
    with pytest.raises(core.UnknownRegion):
        core.team_context(team, site)
    known = core.team_context(team.assign(site_key="SITE-01"), site.assign(site_key="SITE-02"))
    assert known["region"].tolist() == ["DK"] and known["country"].isna().all(), "the site frame lacks SITE-01: no country, but the region is the library's"
    with pytest.raises(core.FrameError, match="country"):
        core.team_context(team, site.drop(columns="country"))
    with pytest.raises(core.FrameError, match="cost_centre_key"):
        core.team_context(team.drop(columns="cost_centre_key"), site)


def test_team_of_cost_centre_oracle_unknown_and_shared_cost_centres_are_refused():
    """halvaro.core.org.team_of_cost_centre: an unknown cost centre and a cost centre shared by two teams raise FrameError saying how many teams match."""
    team = pd.DataFrame({"team_key": ["T1", "T2", "T3"], "cost_centre_key": ["C1", "C2", "C2"]})
    assert core.team_of_cost_centre(team, "C1") == "T1"
    with pytest.raises(core.FrameError, match="0 teams"):
        core.team_of_cost_centre(team, "C9")
    with pytest.raises(core.FrameError, match="2 teams"):
        core.team_of_cost_centre(team, "C2")
    with pytest.raises(core.FrameError, match="cost_centre_key"):
        core.team_of_cost_centre(team.drop(columns="cost_centre_key"), "C1")


def test_cost_centre_of_team_oracle_unknown_and_duplicated_team_rows_are_refused():
    """halvaro.core.org.cost_centre_of_team: a team with one row gives its cost centre; an unknown team and a team with two rows raise FrameError saying how many rows match (the pointer of the
    index stays on the generator test of rule 2; this case was found by a mutation that the older tests did not catch)."""
    team = pd.DataFrame({"team_key": ["T1", "T2", "T2"], "cost_centre_key": ["C1", "C2", "C3"]})
    assert core.cost_centre_of_team(team, "T1") == "C1"
    with pytest.raises(core.FrameError, match="0 rows"):
        core.cost_centre_of_team(team, "T9")
    with pytest.raises(core.FrameError, match="2 rows"):
        core.cost_centre_of_team(team, "T2")
