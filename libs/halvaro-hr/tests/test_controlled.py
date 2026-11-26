"""controlled_work_audit on synthetic frames (the baseline tests are in the closed repository)."""
import datetime as dt

import numpy as np
import pandas as pd
import pytest

import halvaro.hr as hr
from halvaro.core import FrameError, PeriodError, registry
from halvaro.hr.controlled import controlled_work_audit

D = dt.date
ROLE = pd.DataFrame({"role_key": ["R1", "R2"], "name": ["Pipe fitter", "Office clerk"]})
EMP = pd.DataFrame({"emp_key": ["EMP-1", "EMP-2", "EMP-3"], "legal_entity_key": ["LE-01", "LE-01", "LE-02"], "hire_date": [D(2020, 1, 1)] * 3})
TERM = pd.DataFrame({"emp_key": ["EMP-1", "EMP-2", "EMP-3"], "valid_from": [D(2024, 1, 1)] * 3, "valid_to": [None, None, None], "role_key": ["R1", "R2", "R1"]})
PRJ = pd.DataFrame({"prj_key": ["P1", "P2"], "type": ["dh_network", "substation"]})
CERT = pd.DataFrame({"emp_key": ["EMP-1", "EMP-3"], "qual_key": ["Q4", "Q4"], "issued": [D(2024, 1, 10), D(2024, 1, 10)], "expires": [D(2024, 12, 31), None]})
RULES = pd.DataFrame([dict(rule_id="pipework", qual_key="Q4", roles=["pipe_crew"], entity=None, project_types=["dh_network"], cst=[430], allocation=True)])
GROUPS = {"pipe_crew": ["Pipe fitter"]}


def _te(rows):
    return pd.DataFrame(rows, columns=["emp_key", "prj_key", "work_date", "cst_key"])


NOALC = pd.DataFrame({"emp_key": [], "prj_key": [], "start": [], "end": []})


def _audit(te=None, al=None, rules=RULES, cert=CERT, term=TERM, emp=EMP, as_of=D(2026, 1, 1), **k):
    return controlled_work_audit(te if te is not None else _te([]), al if al is not None else NOALC, PRJ, term, ROLE, emp, cert, rules, as_of, role_groups=GROUPS, **k)


def _ck(a, kind):
    return a.checked[a.checked.kind == kind].checked.sum()


def test_a_time_entry_needs_a_certificate_valid_on_the_day_both_ends_inclusive():
    te = _te([("EMP-1", "P1", D(2024, 1, 10), "CST-430"), ("EMP-1", "P1", D(2024, 1, 9), "CST-430"), ("EMP-1", "P1", D(2024, 12, 31), "CST-430"), ("EMP-1", "P1", D(2025, 1, 1), "CST-430")])
    a = _audit(te)
    assert a.violations.work_date.tolist() == [pd.Timestamp(2024, 1, 9), pd.Timestamp(2025, 1, 1)], "issued and expiry day count; the day before and the day after do not"
    assert _ck(a, "time_entry") == 4 and a.checked[a.checked.kind == "time_entry"].violations.sum() == 2
    assert a.violations.iloc[0][["kind", "rule_id", "emp_key", "prj_key", "cst_key", "qual_key", "planned"]].tolist() == ["time_entry", "pipework", "EMP-1", "P1", "CST-430", "Q4", False]
    late = _audit(_te([("EMP-1", "P1", pd.Timestamp("2024-12-31 10:00"), "CST-430")]))
    assert late.violations.empty, "a time of day on the expiry day is still that day"


def test_only_rows_the_rule_controls_are_checked():
    te = _te([("EMP-1", "P1", D(2025, 6, 1), "CST-120"),        # other cost code
              ("EMP-1", "P2", D(2025, 6, 1), "CST-430"),        # other project type
              ("EMP-2", "P1", D(2025, 6, 1), "CST-430"),        # role not in the group
              ("EMP-3", "P1", D(2030, 6, 1), "CST-430")])       # open certificate, valid
    a = _audit(te)
    assert a.violations.empty and _ck(a, "time_entry") == 1
    assert len(_audit(te, rules=RULES.assign(cst="any")).violations) == 1, "cst any controls every cost code: the CST-120 entry of EMP-1 has no valid certificate in 2025"
    assert _ck(_audit(te, rules=RULES.assign(cst=[[430]])), "time_entry") == 1 and _ck(_audit(te, rules=RULES.assign(cst="CST-430")), "time_entry") == 1
    assert _ck(_audit(te, rules=RULES.assign(cst=np.nan, project_types=np.nan)), "time_entry") == 3, "empty cst and project_types mean any: EMP-1 twice (two cost codes, two types) and EMP-3"
    ent = RULES.assign(entity="LE-02")
    assert _ck(_audit(_te([("EMP-1", "P1", D(2025, 6, 1), "CST-430"), ("EMP-3", "P1", D(2025, 6, 1), "CST-430")]), rules=ent), "time_entry") == 1, "the entity of the rule limits to its people"
    assert _ck(_audit(_te([("EMP-1", "P1", D(2025, 6, 1), "CST-430"), ("EMP-3", "P1", D(2025, 6, 1), "CST-430")]), rules=RULES.assign(entity=pd.NA)), "time_entry") == 2
    r = _audit(_te([("EMP-1", "P2", D(2025, 6, 1), "CST-120"), ("EMP-2", "P1", D(2025, 6, 1), "CST-430")]), rules=RULES.assign(project_types="any", cst="any", roles="Pipe fitter"))
    assert _ck(r, "time_entry") == 1, "a role name, not only a group; any project type and cost code; the clerk is not a pipe fitter"
    assert _ck(_audit(te, rules=RULES.assign(roles="*", cst="any", project_types="any")), "time_entry") == 4, "'*' is every role"


def test_two_certificates_of_one_person_count_once_and_one_valid_is_enough():
    cert = pd.concat([CERT, pd.DataFrame({"emp_key": ["EMP-1"], "qual_key": ["Q4"], "issued": [D(2025, 1, 1)], "expires": [D(2025, 12, 31)]})])
    a = _audit(_te([("EMP-1", "P1", D(2025, 6, 1), "CST-430"), ("EMP-1", "P1", D(2024, 6, 1), "CST-430"), ("EMP-1", "P1", D(2026, 6, 1), "CST-430")]), cert=cert)
    assert a.violations.work_date.tolist() == [pd.Timestamp(2026, 6, 1)] and _ck(a, "time_entry") == 3


def test_allocations_start_end_and_planned_days():
    al = pd.DataFrame({"emp_key": ["EMP-1"] * 5, "prj_key": ["P1"] * 5,
                       "start": [D(2024, 6, 1), D(2024, 6, 1), D(2025, 6, 1), D(2026, 3, 1), D(2025, 12, 1)],
                       "end": [D(2024, 12, 31), D(2025, 3, 1), D(2025, 7, 1), D(2026, 4, 1), D(2026, 6, 1)]})
    a = _audit(al=al, as_of=D(2026, 1, 1))
    vd = lambda x, kind: x.violations[x.violations.kind == kind].work_date.tolist()
    T = pd.Timestamp
    assert _ck(a, "allocation_start") == 4 and _ck(a, "allocation_end") == 4, "the stint that starts after the date is not a start/end check"
    assert vd(a, "allocation_start") == [T(2025, 6, 1), T(2025, 12, 1)]
    assert vd(a, "allocation_end") == [T(2025, 3, 1), T(2025, 7, 1), T(2026, 1, 1)], "the end day is the end, never later than the date: the fifth stint is checked on 1 January 2026"
    assert vd(a, "allocation_planned") == [T(2026, 3, 1), T(2026, 4, 1), T(2026, 6, 1)] and a.violations.planned.eq(a.violations.kind == "allocation_planned").all()
    off = _audit(al=al, rules=RULES.assign(allocation=False))
    assert off.violations.empty and _ck(off, "allocation_start") == 0 and _ck(off, "allocation_planned") == 0, "rules without allocation do not look at allocations"
    on_date = _audit(al=al, as_of=D(2026, 3, 1))
    assert vd(on_date, "allocation_planned") == [T(2026, 4, 1), T(2026, 6, 1)] and T(2026, 3, 1) in vd(on_date, "allocation_start"), "a stint that starts on the date is no longer planned"
    ends_today = al.iloc[[1]].assign(end=D(2026, 1, 1))
    assert vd(_audit(al=ends_today, as_of=D(2026, 1, 1)), "allocation_planned") == [] and vd(_audit(al=ends_today, as_of=D(2026, 1, 1)), "allocation_end") == [T(2026, 1, 1)], "a stint that ends on the date is checked, not planned"
    open_end = al.iloc[[2]].assign(end=None)
    o = _audit(al=open_end, as_of=D(2026, 1, 1))
    assert vd(o, "allocation_start") == [T(2025, 6, 1)] and vd(o, "allocation_end") == [T(2026, 1, 1)], "an open stint counts to the date"


def test_an_allocation_uses_the_role_at_its_start_for_all_its_days():
    term = pd.DataFrame({"emp_key": ["EMP-1", "EMP-1"], "valid_from": [D(2024, 1, 1), D(2025, 6, 1)], "valid_to": [D(2025, 5, 31), None], "role_key": ["R1", "R2"]})
    al = pd.DataFrame({"emp_key": ["EMP-1"], "prj_key": ["P1"], "start": [D(2025, 5, 1)], "end": [D(2025, 7, 1)]})
    cert = CERT.assign(expires=[D(2025, 6, 15), None])
    a = _audit(al=al, term=term, cert=cert)
    assert _ck(a, "allocation_start") == 1 and _ck(a, "allocation_end") == 1 and a.violations.kind.tolist() == ["allocation_end"], "the end day is checked with the pipe fitter role of the start"


def test_the_first_term_counts_from_the_hire_date_unless_told_otherwise():
    te = _te([("EMP-1", "P1", D(2023, 12, 31), "CST-430")])
    a = _audit(te)
    assert _ck(a, "time_entry") == 1 and a.violations.work_date.tolist() == [pd.Timestamp(2023, 12, 31)], "before the first term: the role of the first term, no certificate yet"
    b = _audit(te, first_term_from_hire=False)
    assert _ck(b, "time_entry") == 0 and b.unchecked.set_index("kind").loc["time_entry", "unchecked"] == 1
    assert _ck(_audit(te, emp=EMP.assign(hire_date=D(2024, 1, 1))), "time_entry") == 0, "before the hire date there is no role"
    assert _ck(_audit(_te([("EMP-1", "P1", D(2024, 1, 1), "CST-430")]), emp=EMP.assign(hire_date=D(2024, 1, 1))), "time_entry") == 1


def test_the_role_is_that_of_the_term_valid_on_the_day_last_day_included():
    term = pd.DataFrame({"emp_key": ["EMP-1", "EMP-1"], "valid_from": [D(2024, 1, 1), D(2025, 6, 1)], "valid_to": [D(2025, 5, 31), None], "role_key": ["R1", "R2"]})
    te = _te([("EMP-1", "P1", D(2025, 5, 31), "CST-430"), ("EMP-1", "P1", D(2025, 6, 1), "CST-430")])
    a = _audit(te, term=term)
    assert a.violations.work_date.tolist() == [pd.Timestamp(2025, 5, 31)], "last day of the pipe fitter term is controlled (certificate expired), the first day as clerk is not"
    assert _ck(a, "time_entry") == 1


def test_inputs_that_are_refused():
    te = _te([("EMP-1", "P1", D(2024, 6, 1), "CST-430")])
    al = pd.DataFrame({"emp_key": ["EMP-1"], "prj_key": ["P9"], "start": [D(2024, 6, 1)], "end": [D(2024, 7, 1)]})
    for kw, m in ((dict(rules=pd.concat([RULES, RULES])), "more than one row for a rule_id"), (dict(rules=RULES.assign(roles=[[]])), "has no roles"), (dict(rules=RULES.assign(roles=np.nan)), "has no roles"),
                  (dict(rules=RULES.assign(roles=["Pipe fiter"])), "hr.role does not have"), (dict(rules=RULES.assign(allocation=np.nan)), "allocation flag"),
                  (dict(te=_te([("EMP-1", "P9", D(2024, 6, 1), "CST-430")])), "projects.time_entry has projects"), (dict(al=al), "hr.allocation has projects"),
                  (dict(term=TERM.assign(role_key="R9")), "hr.role does not have"), (dict(term=pd.concat([TERM, TERM.iloc[:1]])), "two terms valid"),
                  (dict(te=_te([("EMP-1", "P1", None, "CST-430")])), "nulls"), (dict(as_of="garbage"), None),
                  (dict(cert=CERT.assign(expires=[D(2023, 1, 1), None])), "expires before"), (dict(rules=RULES.drop(columns="cst")), "lacks column")):
        with pytest.raises((FrameError, PeriodError), match=m):
            _audit(**{"te": te, **kw})
    with pytest.raises(FrameError, match="ends before it starts"):
        _audit(al=al.assign(prj_key="P1", end=D(2024, 1, 1)))


def test_registered_and_in_the_index():
    m = registry.registered()["halvaro.hr.controlled.controlled_work_audit"]
    assert m.oracle.startswith("py:") and m.sources and hr.controlled_work_audit is controlled_work_audit and registry.check() == []


# --- review round 3 -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

T = pd.Timestamp
ALC = pd.DataFrame({"emp_key": ["EMP-1"], "prj_key": ["P1"], "start": [D(2025, 6, 1)], "end": [D(2025, 7, 1)]})


def _run(te=None, al=None, prj=PRJ, term=TERM, role=ROLE, emp=EMP, cert=CERT, rules=RULES, as_of=D(2026, 1, 1), **k):
    return controlled_work_audit(te if te is not None else _te([]), al if al is not None else NOALC, prj, term, role, emp, cert, rules, as_of, role_groups=GROUPS, **k)


def _f64(frame):
    return pd.DataFrame({c: pd.Series([], dtype="float64") for c in frame.columns})


def _vd(a, kind):
    return a.violations[a.violations.kind == kind].work_date.tolist()


def _u(a, kind):
    return a.unchecked.set_index("kind").loc[kind].to_dict()


def test_empty_frames_of_any_dtype_are_empty_frames():
    te = _te([("EMP-1", "P1", D(2025, 6, 1), "CST-430")])
    nocert = CERT.assign(qual_key="Q9")
    for kw in (dict(cert=nocert), dict(cert=_f64(CERT)), dict(cert=nocert, te=_f64(_te([]))), dict(cert=_f64(CERT), te=_f64(_te([]))), dict(te=_f64(_te([]))),
               dict(term=_f64(TERM)), dict(term=_f64(TERM), cert=_f64(CERT)), dict(prj=_f64(PRJ), emp=_f64(EMP)), dict(prj=_f64(PRJ), emp=_f64(EMP), term=_f64(TERM), cert=_f64(CERT))):
        a = _run(al=_f64(NOALC), **kw)
        assert a.violations.empty and a.checked.checked.sum() == 0, kw.keys()
        assert a.unchecked.unchecked.sum() == 0
    a = _run(te, al=_f64(NOALC), cert=nocert)
    assert len(a.violations) == 1 and _ck(a, "time_entry") == 1, "no certificate of the qualification: the entry is a violation, but the empty allocation frame does not break the merge"
    a = _run(te, al=_f64(NOALC), cert=_f64(CERT))
    assert len(a.violations) == 1
    a = _run(te, al=ALC, term=_f64(TERM))
    assert a.violations.empty and _u(a, "time_entry")["unchecked"] == 1 and _u(a, "allocation_start")["unchecked"] == 1, "no employment term: nothing has a role, and that is reported"
    a = _run(te=_f64(_te([])), al=ALC)
    assert _ck(a, "allocation_start") == 1 and len(a.violations) == 2
    assert _run(te, al=_f64(NOALC), term=_f64(TERM), first_term_from_hire=False).violations.empty


def test_unchecked_reports_what_no_rule_could_judge():
    prj = pd.concat([PRJ, pd.DataFrame({"prj_key": ["P3"], "type": [None]})], ignore_index=True)
    emp = pd.concat([EMP, pd.DataFrame({"emp_key": ["EMP-5", "EMP-6"], "legal_entity_key": [None, "LE-01"], "hire_date": [D(2020, 1, 1)] * 2})], ignore_index=True)
    term = pd.concat([TERM, pd.DataFrame({"emp_key": ["EMP-5", "EMP-6"], "valid_from": [D(2024, 1, 1)] * 2, "valid_to": [None, None], "role_key": ["R1", "R2"]})], ignore_index=True)
    rule2 = RULES.assign(rule_id="pipework2")
    rules = pd.concat([RULES, rule2], ignore_index=True)
    te = _te([("EMP-1", "P3", D(2025, 6, 1), "CST-430"),         # no project type
              ("EMP-1", "P1", D(2025, 6, 2), None),              # no cost code
              ("EMP-1", "P1", D(2025, 6, 3), np.nan),            # no cost code
              ("EMP-2", "P3", D(2025, 6, 4), None),              # a clerk: no rule names the role
              ("EMP-1", "P1", D(2025, 6, 5), "CST-430")])        # fine
    a = _run(te, prj=prj, emp=emp, term=term, rules=rules)
    assert _u(a, "time_entry") == dict(unchecked=0, no_project_type=1, no_cst_key=2, no_entity=0), "a row counts once however many rules it escapes"
    assert _ck(a, "time_entry") == 2 and a.unchecked.columns.tolist() == ["kind", "unchecked", "no_project_type", "no_cst_key", "no_entity"]
    assert a.unchecked.kind.tolist() == ["time_entry", "allocation_start", "allocation_end", "allocation_planned"]
    ent = rules.assign(entity="LE-01")
    b = _run(_te([("EMP-5", "P1", D(2025, 6, 1), "CST-430"), ("EMP-3", "P1", D(2025, 6, 1), "CST-430"), ("EMP-6", "P1", D(2025, 6, 1), "CST-430")]), prj=prj, emp=emp, term=term, rules=ent)
    assert _u(b, "time_entry")["no_entity"] == 1, "EMP-5 has no legal entity (EMP-3 has another one, which is a plain 'not controlled'); EMP-6 is a clerk"
    assert _ck(b, "time_entry") == 0
    gone = _run(_te([("EMP-7", "P1", D(2025, 6, 1), "CST-430")]), prj=prj, emp=emp, term=pd.concat([term, pd.DataFrame({"emp_key": ["EMP-7"], "valid_from": [D(2024, 1, 1)], "valid_to": [None], "role_key": ["R1"]})]), rules=ent)
    assert _u(gone, "time_entry")["no_entity"] == 1, "no hr.employee row is no entity either"
    # rules without the filter are not blocked by the null
    free = RULES.assign(project_types="any", cst="any")
    c = _run(te, prj=prj, emp=emp, term=term, rules=free)
    assert _ck(c, "time_entry") == 4 and _u(c, "time_entry") == dict(unchecked=0, no_project_type=0, no_cst_key=0, no_entity=0)
    assert _u(_run(te, prj=prj, emp=emp, term=term, rules=RULES.assign(project_types="any")), "time_entry")["no_project_type"] == 0
    assert _u(_run(te, prj=prj, emp=emp, term=term, rules=RULES.assign(cst="any")), "time_entry")["no_cst_key"] == 0
    # allocations: the project type counts, the cost code and the rule's allocation flag are no concern
    al = pd.DataFrame({"emp_key": ["EMP-1", "EMP-1"], "prj_key": ["P3", "P3"], "start": [D(2025, 6, 1), D(2026, 3, 1)], "end": [D(2025, 7, 1), D(2026, 4, 1)]})
    d = _run(al=al, prj=prj, emp=emp, term=term)
    assert [_u(d, k)["no_project_type"] for k in _KINDS_] == [0, 1, 1, 2] and [_u(d, k)["no_cst_key"] for k in _KINDS_] == [0, 0, 0, 0]
    assert _u(_run(al=al, prj=prj, emp=emp, term=term, rules=RULES.assign(allocation=False)), "allocation_start")["no_project_type"] == 0
    # a row without a role is counted under unchecked and nowhere else
    e = _run(_te([("EMP-1", "P3", D(2023, 6, 1), None)]), prj=prj, first_term_from_hire=False)
    assert _u(e, "time_entry") == dict(unchecked=1, no_project_type=0, no_cst_key=0, no_entity=0)


_KINDS_ = ("time_entry", "allocation_start", "allocation_end", "allocation_planned")


def test_integer_and_float_cost_codes_are_read_as_cst_numbers():
    te = _te([("EMP-1", "P1", D(2025, 6, 1), 430), ("EMP-1", "P1", D(2025, 6, 2), np.int64(430)), ("EMP-1", "P1", D(2025, 6, 3), 430.0), ("EMP-1", "P1", D(2025, 6, 4), "430"), ("EMP-1", "P1", D(2025, 6, 5), 120)])
    a = _run(te)
    assert _ck(a, "time_entry") == 4 and a.violations.cst_key.tolist() == ["CST-430"] * 4 and a.unchecked.no_cst_key.sum() == 0
    ints = _run(_te([("EMP-1", "P1", D(2025, 6, 1), 430), ("EMP-3", "P1", D(2025, 6, 1), 430)]))
    assert _ck(ints, "time_entry") == 2 and len(ints.violations) == 1 and ints.violations.cst_key.iloc[0] == "CST-430", "integer codes only: the old code checked nothing and said nothing"


def test_numbers_are_not_dates():
    te = _te([("EMP-1", "P1", D(2025, 6, 1), "CST-430")])
    bad_alloc = lambda **k: ALC.assign(**k)
    for what, kw in (("work_date", dict(te=_te([("EMP-1", "P1", 20250601, "CST-430")]))), ("work_date", dict(te=_te([("EMP-1", "P1", 20250601.0, "CST-430")]))),
                     ("work_date", dict(te=_te([("EMP-1", "P1", 20250601, "CST-430"), ("EMP-1", "P1", D(2025, 6, 1), "CST-430")]))), ("work_date", dict(te=_te([("EMP-1", "P1", True, "CST-430")]))),
                     ("start", dict(al=bad_alloc(start=20250601))), ("end", dict(al=bad_alloc(end=20250701.0))), ("end", dict(al=pd.concat([ALC, bad_alloc(end=20250701)], ignore_index=True).astype({"end": object}))),
                     ("valid_from", dict(term=TERM.assign(valid_from=20240101))), ("valid_to", dict(term=TERM.assign(valid_to=20250101))), ("issued", dict(cert=CERT.assign(issued=20240110))),
                     ("expires", dict(cert=CERT.assign(expires=[20241231, None]))), ("hire_date", dict(emp=EMP.assign(hire_date=20200101)))):
        with pytest.raises(FrameError, match=f"{what} holds numbers, not dates"):
            _run(**{"te": te, **kw})
    assert _run(te, al=ALC.assign(end=np.nan)).checked.checked.sum() > 0, "an open end that is a column of NaN is no number"
    assert _run(te, term=TERM.assign(valid_to=np.nan)).checked.checked.sum() == 1
    for bad in (20250601, 20250601.0, 2025, True, np.int64(20250601), np.float64(1.0)):
        with pytest.raises(PeriodError, match="number"):
            _run(te, as_of=bad)


def test_rule_values_are_read_strictly():
    te = _te([("EMP-1", "P1", D(2025, 6, 1), "CST-430"), ("EMP-1", "P1", D(2025, 6, 2), "CST-120")])
    for cst in (430.0, [430.0], np.float64(430.0), [430.0, 999], "430", ["CST-430", 999.0]):
        assert _ck(_run(te, rules=RULES.assign(cst=[cst] if isinstance(cst, list) else cst).astype({"cst": object})), "time_entry") == 1, cst
    for cst in (430.5, [430, 120.5], True, [False], "abc", "CST-x", ["CST-"], [None]):
        with pytest.raises(FrameError, match="cost code"):
            _run(te, rules=RULES.assign(cst=[cst] if isinstance(cst, list) else cst).astype({"cst": object}))
    for flag in ("false", "False", "true", "yes", 2, -1, 0.5, [True], "0"):
        with pytest.raises(FrameError, match="allocation flag"):
            _run(te, al=ALC, rules=RULES.assign(allocation=[flag]).astype({"allocation": object}))
    for flag, n in ((True, 1), (np.bool_(True), 1), (1, 1), (1.0, 1), (False, 0), (np.bool_(False), 0), (0, 0), (0.0, 0)):
        assert _ck(_run(al=ALC, rules=RULES.assign(allocation=[flag]).astype({"allocation": object})), "allocation_start") == n, flag
    term = pd.DataFrame({"emp_key": ["EMP-1"], "valid_from": [D(2025, 6, 1)], "valid_to": [D(2025, 5, 31)], "role_key": ["R1"]})
    with pytest.raises(FrameError, match="term that ends before it starts"):
        _run(te, term=term)
    one_day = term.assign(valid_to=D(2025, 6, 1))
    a = _run(te, term=one_day, first_term_from_hire=False)
    assert _ck(a, "time_entry") == 1 and a.unchecked.set_index("kind").loc["time_entry", "unchecked"] == 1, "a one-day term is a term: only the 1st has the role"


def test_time_entries_after_as_of_are_audited_unless_told_otherwise_and_violations_are_in_kind_order():
    te = _te([("EMP-1", "P1", D(2025, 6, 1), "CST-430"), ("EMP-1", "P1", D(2026, 1, 1), "CST-430"), ("EMP-1", "P1", D(2026, 1, 2), "CST-430")])
    assert _ck(_run(te), "time_entry") == 3, "default: entries after the date are audited as time_entry"
    a = _run(te, time_entries_until_as_of=True)
    assert _ck(a, "time_entry") == 2 and a.violations.work_date.tolist() == [T(2025, 6, 1), T(2026, 1, 1)], "the date itself is in"
    b = _run(te, time_entries_until_as_of=False)
    assert len(b.violations) == 3
    nocert = CERT.assign(qual_key="Q9")
    rules = pd.concat([RULES.assign(rule_id="b_rule", project_types="any", cst="any"), RULES.assign(rule_id="a_rule", project_types="any", cst="any")], ignore_index=True)
    te2 = _te([("EMP-3", "P1", D(2025, 6, 2), "CST-430"), ("EMP-1", "P2", D(2025, 6, 1), "CST-430"), ("EMP-1", "P1", D(2025, 6, 1), "CST-430"), ("EMP-1", "P1", D(2025, 5, 1), "CST-430")])
    al = pd.DataFrame({"emp_key": ["EMP-3", "EMP-1", "EMP-1"], "prj_key": ["P1", "P1", "P2"], "start": [D(2025, 2, 1), D(2025, 3, 1), D(2026, 6, 1)], "end": [D(2025, 2, 10), D(2025, 4, 1), D(2026, 7, 1)]})
    v = _run(te2, al=al, cert=nocert, rules=rules).violations
    got = list(zip(v.kind, v.rule_id, v.emp_key, v.work_date, v.prj_key))
    assert len(got) == 20
    assert got == sorted(got, key=lambda r: (_KINDS_.index(r[0]), r[1], r[2], r[3], r[4])), "kind in the order of the audit (not alphabetical), then rule, person, day, project"
    assert [k for i, k in enumerate(v.kind) if i == 0 or k != v.kind.iloc[i - 1]] == list(_KINDS_)
    assert v.index.tolist() == list(range(20))


def test_stints_on_the_boundaries_of_the_date_and_one_day_stints():
    al = ALC.assign(start=D(2026, 1, 1), end=D(2026, 2, 1))
    a = _run(al=al, as_of=D(2026, 1, 1))
    assert _vd(a, "allocation_start") == [T(2026, 1, 1)] and _vd(a, "allocation_end") == [T(2026, 1, 1)] and _vd(a, "allocation_planned") == [T(2026, 2, 1)], "a stint that starts on the date: start and end (clipped to the date) are checked, its real end is planned"
    assert _ck(a, "allocation_end") == 1
    b = _run(al=al, as_of=D(2025, 12, 31))
    assert _ck(b, "allocation_start") == 0 and _ck(b, "allocation_end") == 0 and _vd(b, "allocation_planned") == [T(2026, 1, 1), T(2026, 2, 1)]
    one = ALC.assign(end=D(2025, 6, 1))
    c = _run(al=one)
    assert _vd(c, "allocation_start") == [T(2025, 6, 1)] and _vd(c, "allocation_end") == [T(2025, 6, 1)] and _vd(c, "allocation_planned") == []
    d = _run(al=ALC.assign(start=D(2026, 3, 1), end=D(2026, 3, 1)))
    assert _vd(d, "allocation_planned") == [T(2026, 3, 1), T(2026, 3, 1)], "a one-day stint in the future: its start and its end day are both planned"
    e = _run(al=one, as_of=D(2025, 6, 1))
    assert _vd(e, "allocation_start") == [T(2025, 6, 1)] and _vd(e, "allocation_end") == [T(2025, 6, 1)] and _vd(e, "allocation_planned") == []


def test_a_certificate_that_expires_on_the_day_it_is_issued_is_valid_that_day():
    cert = pd.DataFrame({"emp_key": ["EMP-1"], "qual_key": ["Q4"], "issued": [D(2025, 6, 1)], "expires": [D(2025, 6, 1)]})
    te = _te([("EMP-1", "P1", D(2025, 5, 31), "CST-430"), ("EMP-1", "P1", D(2025, 6, 1), "CST-430"), ("EMP-1", "P1", D(2025, 6, 2), "CST-430")])
    a = _run(te, cert=cert)
    assert a.violations.work_date.tolist() == [T(2025, 5, 31), T(2025, 6, 2)]


def test_the_entity_of_the_rule_limits_asymmetrically():
    te = _te([("EMP-1", "P1", D(2025, 6, 1), "CST-430"), ("EMP-1", "P1", D(2025, 6, 2), "CST-430"), ("EMP-3", "P1", D(2025, 6, 1), "CST-430")])
    assert _ck(_run(te, rules=RULES.assign(entity="LE-01")), "time_entry") == 2 and _ck(_run(te, rules=RULES.assign(entity="LE-02")), "time_entry") == 1
    assert _ck(_run(te, rules=RULES.assign(entity="LE-09")), "time_entry") == 0 and _ck(_run(te, rules=RULES.assign(entity="")), "time_entry") == 3


def test_a_null_project_type_or_cost_code_is_not_controlled_by_a_filter_but_by_any():
    prj = pd.concat([PRJ, pd.DataFrame({"prj_key": ["P3"], "type": [None]})], ignore_index=True)
    te = _te([("EMP-1", "P3", D(2025, 6, 1), "CST-430"), ("EMP-1", "P1", D(2025, 6, 2), None)])
    a = _run(te, prj=prj)
    assert _ck(a, "time_entry") == 0 and a.violations.empty
    b = _run(te, prj=prj, rules=RULES.assign(project_types="any"))
    assert _ck(b, "time_entry") == 1
    assert _ck(_run(te, prj=prj, rules=RULES.assign(cst="any")), "time_entry") == 1
    assert _ck(_run(te, prj=prj, rules=RULES.assign(cst="any", project_types="any")), "time_entry") == 2
    assert _vd(_run(te, prj=prj, rules=RULES.assign(cst="any", project_types="any")), "time_entry") == [T(2025, 6, 1), T(2025, 6, 2)]


def test_time_zones_are_refused():
    tz = T("2025-06-01", tz="UTC")
    te = _te([("EMP-1", "P1", D(2025, 6, 1), "CST-430")])
    for kw in (dict(te=_te([("EMP-1", "P1", tz, "CST-430")])), dict(al=ALC.assign(start=tz)), dict(al=ALC.assign(end=tz)), dict(term=TERM.assign(valid_from=tz)), dict(term=TERM.assign(valid_to=tz)),
               dict(cert=CERT.assign(issued=tz)), dict(cert=CERT.assign(expires=tz)), dict(emp=EMP.assign(hire_date=tz))):
        with pytest.raises(FrameError, match="time zone"):
            _run(**{"te": te, **kw})
    with pytest.raises(PeriodError):
        _run(te, as_of=tz)


def test_duplicate_keys_in_project_role_and_employee_are_refused():
    te = _te([("EMP-1", "P1", D(2025, 6, 1), "CST-430")])
    for kw, m in ((dict(prj=pd.concat([PRJ, PRJ.iloc[:1]])), "projects.project has more than one row for a prj_key"), (dict(role=pd.concat([ROLE, ROLE.iloc[:1]])), "hr.role has more than one row for a role_key"),
                  (dict(emp=pd.concat([EMP, EMP.iloc[:1]])), "hr.employee has more than one row for a emp_key")):
        with pytest.raises(FrameError, match=m):
            _run(te, **kw)


def test_a_hire_date_after_the_first_term_never_moves_the_start_later():
    te = _te([("EMP-1", "P1", D(2024, 3, 1), "CST-430"), ("EMP-1", "P1", D(2024, 1, 5), "CST-430")])
    a = _run(te, emp=EMP.assign(hire_date=D(2024, 6, 1)))
    assert _ck(a, "time_entry") == 2 and a.unchecked.unchecked.sum() == 0 and a.violations.work_date.tolist() == [T(2024, 1, 5)], "the term starts 1 January; the later hire date does not shorten it"
    term = pd.DataFrame({"emp_key": ["EMP-1", "EMP-1"], "valid_from": [D(2024, 1, 1), D(2025, 6, 1)], "valid_to": [D(2025, 5, 31), None], "role_key": ["R1", "R1"]})
    b = _run(_te([("EMP-1", "P1", D(2023, 6, 1), "CST-430"), ("EMP-1", "P1", D(2025, 5, 1), "CST-430")]), term=term, emp=EMP.assign(hire_date=[D(2023, 1, 1), D(2020, 1, 1), D(2020, 1, 1)]))
    assert _ck(b, "time_entry") == 2, "only the first term is moved earlier, and only to the hire date"
    c = _run(_te([("EMP-1", "P1", D(2023, 6, 1), "CST-430"), ("EMP-1", "P1", D(2022, 6, 1), "CST-430")]), term=term, emp=EMP.assign(hire_date=[D(2023, 1, 1), D(2020, 1, 1), D(2020, 1, 1)]))
    assert _ck(c, "time_entry") == 1, "the day before the hire date has no role"


def test_role_keys_of_different_dtypes_still_join():
    role = pd.DataFrame({"role_key": [1, 2], "name": ["Pipe fitter", "Office clerk"]})
    term = TERM.assign(role_key=pd.Series([1, 2, 1], dtype=object))
    a = _run(_te([("EMP-1", "P1", D(2025, 6, 1), "CST-430")]), role=role, term=term)
    assert _ck(a, "time_entry") == 1
    b = _run(_te([("EMP-1", "P1", D(2025, 6, 1), "CST-430")]), role=role, term=TERM.assign(role_key=[1, 2, 1]))
    assert _ck(b, "time_entry") == 1


def test_an_open_stint_that_starts_after_the_date_is_planned_with_no_end_row_and_no_error():
    future_open = ALC.assign(start=D(2026, 6, 1), end=None)
    a = _run(al=future_open, as_of=D(2026, 1, 1))
    assert _vd(a, "allocation_planned") == [T(2026, 6, 1)], "only the planned start day: the open end is unknown"
    assert _ck(a, "allocation_start") == 0 and _ck(a, "allocation_end") == 0 and _ck(a, "allocation_planned") == 1
    assert a.violations.planned.all()
    mixed = pd.concat([future_open, ALC.assign(end=None)], ignore_index=True)
    b = _run(al=mixed, as_of=D(2026, 1, 1))
    assert _vd(b, "allocation_planned") == [T(2026, 6, 1)] and _vd(b, "allocation_start") == [T(2025, 6, 1)] and _vd(b, "allocation_end") == [T(2026, 1, 1)]
    with pytest.raises(FrameError, match="ends before it starts"):
        _run(al=ALC.assign(start=D(2025, 6, 1), end=D(2025, 5, 1)))
