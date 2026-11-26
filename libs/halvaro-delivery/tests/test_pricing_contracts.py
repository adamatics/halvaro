"""price_list_on, price_gaps, framework_for, contracts_for_project, clauses_on, price_adjustment_terms, notification_clauses_on, obligation_status, legal_flags: synthetic boundaries, then the baseline (plan oracles O21 to O25)."""
import datetime as dt

import numpy as np
import pandas as pd
import pytest

import halvaro.delivery as delivery
from halvaro.core import AmbiguousKey, Context, FrameError, StageRefusal, registry

CTX = Context(stage="month12", role="r")
D = dt.date


def _pl(rows):
    return pd.DataFrame(rows, columns=["sup_key", "itm_key", "valid_from", "valid_to", "unit_price", "currency", "con_key", "change_reason"])


def _row(sup, itm, f, t, price=10.0, reason="indexation"):
    return (sup, itm, f, t, price, "DKK", "CON-1", reason)


def test_price_on_a_date_is_inclusive_on_both_ends_and_filters():
    p = _pl([_row("S1", "I1", D(2023, 1, 1), D(2023, 12, 31), 10.0), _row("S1", "I1", D(2024, 1, 1), None, 11.0), _row("S1", "I2", D(2023, 6, 1), D(2023, 6, 30)), _row("S2", "I1", D(2023, 1, 1), None, 99.0)])
    on = lambda d, **k: delivery.price_list_on(p, d, context=CTX, **k)
    assert on(D(2023, 12, 31), sup_key="S1", itm_key="I1").unit_price.tolist() == [10.0], "valid_to is the last valid day"
    assert on(D(2024, 1, 1), sup_key="S1", itm_key="I1").unit_price.tolist() == [11.0], "valid_from is the first valid day"
    assert on(D(2022, 12, 31), sup_key="S1").empty
    assert on(D(2023, 6, 30)).values[:, :2].tolist() == [["S1", "I1"], ["S1", "I2"], ["S2", "I1"]] and on(D(2023, 7, 1)).itm_key.tolist() == ["I1", "I1"]
    assert on("2024-06-01", sup_key="S2").unit_price.tolist() == [99.0] and list(on(D(2023, 1, 1)).columns)[:2] == ["sup_key", "itm_key"]


def test_price_on_a_date_refuses_overlap_bad_dates_and_bad_input():
    p = _pl([_row("S1", "I1", D(2023, 1, 1), D(2023, 12, 31)), _row("S1", "I1", D(2023, 12, 31), None)])
    with pytest.raises(AmbiguousKey):
        delivery.price_list_on(p, D(2023, 12, 31), context=CTX)
    assert delivery.price_list_on(p, D(2023, 12, 30), context=CTX).shape[0] == 1
    with pytest.raises(FrameError, match="not a date"):
        delivery.price_list_on(p, "zzz", context=CTX)
    with pytest.raises(FrameError, match="lacks column.*currency"):
        delivery.price_list_on(p.drop(columns="currency"), D(2023, 1, 1), context=CTX)
    with pytest.raises(FrameError, match="unit_price must be numeric"):
        delivery.price_list_on(p.assign(unit_price="1"), D(2023, 1, 1), context=CTX)
    with pytest.raises(FrameError, match="without sup_key"):
        delivery.price_list_on(p.assign(sup_key=[None, "S1"]), D(2023, 1, 1), context=CTX)


def test_gaps_overlaps_and_two_open_rows_and_the_window():
    p = _pl([_row("S1", "I1", D(2023, 1, 1), D(2023, 3, 31)), _row("S1", "I1", D(2023, 4, 10), D(2023, 12, 31)),       # gap 9 days (1 to 9 April)
             _row("S1", "I2", D(2023, 1, 1), D(2023, 6, 30)), _row("S1", "I2", D(2023, 6, 30), None),                    # overlap on 30 June
             _row("S2", "I1", D(2023, 1, 1), None), _row("S2", "I1", D(2023, 2, 1), None)])                              # two open rows
    g = delivery.price_gaps(p, context=CTX)
    assert g.gaps.values.tolist() == [["S1", "I1", pd.Timestamp(2023, 4, 1), pd.Timestamp(2023, 4, 9), 9]]
    assert {"gap", "overlap", "two_open"} <= set(g.violations.rule)
    w = delivery.price_gaps(p, window=(D(2022, 12, 1), D(2024, 1, 31)), context=CTX).gaps
    s1 = w[(w.sup_key == "S1") & (w.itm_key == "I1")]
    assert s1.days.tolist() == [31, 9, 31] and s1.gap_start.tolist()[0] == pd.Timestamp(2022, 12, 1), "31 days before the first row, the 9 day gap, 31 days after the last closed row"
    assert delivery.price_gaps(p.iloc[4:5], window=(D(2023, 1, 1), D(2025, 1, 1)), context=CTX).gaps.empty, "an open row covers the rest of the window"
    with pytest.raises(FrameError, match="window ends before"):
        delivery.price_gaps(p, window=(D(2024, 1, 1), D(2023, 1, 1)), context=CTX)


def _ct(rows):
    return pd.DataFrame(rows, columns=["con_key", "type", "cus_key", "sup_key", "prj_key", "parent_con_key", "price_type", "status", "start", "end", "legal_entity_key"])


def _c(key, type_="customer_project", cus=None, sup=None, prj=None, parent=None, price="fixed_price", status="active", start=D(2023, 1, 1), end=None, le="LE-01"):
    return (key, type_, cus, sup, prj, parent, price, status, start, end, le)


def test_framework_valid_on_a_date_excludes_drafts_and_refuses_two():
    ct = _ct([_c("F1", "supplier_framework", sup="S1", start=D(2023, 1, 1), end=D(2024, 12, 31)), _c("F2", "supplier_framework", sup="S1", status="draft", start=D(2023, 1, 1)),
              _c("F3", "supplier_framework", sup="S2", start=D(2023, 1, 1), end=D(2025, 1, 1)), _c("F4", "supplier_framework", sup="S2", start=D(2024, 6, 1))])
    f = lambda sup, d: delivery.framework_for(ct, sup, d, context=CTX)
    assert f("S1", D(2024, 12, 31)).con_key.tolist() == ["F1"] and f("S1", D(2025, 1, 1)).empty and f("S1", D(2022, 12, 31)).empty, "the draft is never a framework in force"
    assert f("S2", D(2024, 5, 31)).con_key.tolist() == ["F3"]
    with pytest.raises(AmbiguousKey):
        f("S2", D(2024, 6, 1))
    assert f("S9", D(2024, 1, 1)).empty


def test_contracts_of_a_project_follow_the_parent_chain_and_count_orders():
    ct = _ct([_c("C1", prj="P1", parent="C0", cus="CUS-1"), _c("C0", "customer_framework", cus="CUS-1"), _c("F1", "supplier_framework", sup="S1"), _c("F2", "supplier_framework", sup="S2")])
    proj = pd.DataFrame({"prj_key": ["P1", "P2"], "contract_key": ["C1", None]})
    po = pd.DataFrame({"prj_key": ["P1", "P1", "P1", "P2"], "con_key": ["F1", "F1", "F2", "F2"]})
    r = delivery.contracts_for_project(proj, ct, po, "P1", context=CTX)
    assert r.kind.tolist() == ["customer_contract", "parent_framework", "supplier_framework", "supplier_framework"] and r.con_key.tolist() == ["C1", "C0", "F1", "F2"] and r.orders.tolist() == [0, 0, 2, 1]
    assert delivery.contracts_for_project(proj, ct, po, "P2", context=CTX).con_key.tolist() == ["F2"], "no customer contract, one framework"
    loop = ct.assign(parent_con_key=["C0", "C1", None, None])
    with pytest.raises(FrameError, match="loops at"):
        delivery.contracts_for_project(proj, loop, po, "P1", context=CTX)
    with pytest.raises(FrameError, match="exactly once"):
        delivery.contracts_for_project(proj, ct, po, "P9", context=CTX)
    with pytest.raises(FrameError, match="not in contracts.contract"):
        delivery.contracts_for_project(proj, ct.iloc[1:], po, "P1", context=CTX)


def _cl(rows):
    return pd.DataFrame(rows, columns=["con_key", "clause_no", "clause_type", "variant", "param_name", "param_value", "param2_name", "param2_value", "valid_from", "valid_to", "verify", "legal_note"])


def test_clauses_on_a_date_and_price_terms_read_by_name_not_position():
    cl = _cl([("C1", 1, "price_adjustment", "indexed", "pass_through_percent", 50.0, "threshold_percent", 3.0, D(2023, 1, 1), None, False, None),
              ("C2", 1, "price_adjustment", "fixed", "pass_through_percent", 0.0, None, np.nan, D(2023, 1, 1), None, False, None),
              ("S1", 1, "price_adjustment", "price_list", "price_notice_days", 30.0, "price_change_percent", 18.0, D(2023, 1, 1), D(2023, 12, 31), False, None),
              ("S1", 2, "price_adjustment", "revision", "price_change_percent", 79.0, None, np.nan, D(2024, 1, 1), None, False, None),
              ("C1", 2, "notification", "incident", "notification_hours", 24.0, None, np.nan, D(2025, 3, 3), None, True, "law")])
    ct = pd.DataFrame({"con_key": ["C1", "C2", "C3", "S1"], "type": ["customer_project", "customer_project", "customer_project", "supplier_framework"], "price_type": ["indexed", "fixed_price", "unit_price", None]})
    assert delivery.clauses_on(cl, D(2023, 12, 31), con_key="S1", context=CTX).clause_no.tolist() == [1] and delivery.clauses_on(cl, D(2024, 1, 1), con_key="S1", context=CTX).clause_no.tolist() == [2]
    assert delivery.clauses_on(cl, D(2025, 3, 2), clause_type="notification", context=CTX).empty and len(delivery.clauses_on(cl, D(2025, 3, 3), clause_type="notification", context=CTX)) == 1
    t = delivery.price_adjustment_terms(cl, ct, context=CTX)
    c1 = t.terms.set_index(["con_key", "clause_no"]).loc[("C1", 1)]
    assert (c1.pass_through_percent, c1.threshold_percent, c1.n_price_clauses) == (50.0, 3.0, 1)
    s1 = t.terms[t.terms.con_key == "S1"]
    assert s1.n_price_clauses.tolist() == [2, 2] and s1.pass_through_percent.isna().all() and s1.threshold_percent.isna().all(), "the parameters of a supplier clause are not pass through or threshold"
    assert t.without_clause.con_key.tolist() == ["C3"], "a customer project contract without a price clause is reported"
    at = delivery.price_adjustment_terms(cl, ct, as_of=D(2025, 1, 1), context=CTX).terms
    assert sorted(at.clause_no.tolist()) == [1, 1, 2], "as of 2025: the C1 and C2 clauses and the revision of S1 (the price list clause ended in 2023)"
    n = delivery.notification_clauses_on(cl, ct.assign(cus_key=["CUS-1", "CUS-2", None, None]), D(2025, 6, 1), context=CTX)
    assert n.values[:, :3].tolist() == [["C1", "CUS-1", 24.0]]
    with pytest.raises(FrameError, match="more than one notification clause"):
        delivery.notification_clauses_on(pd.concat([cl, cl.iloc[[4]].assign(clause_no=9)]), ct.assign(cus_key="X"), D(2025, 6, 1), context=CTX)


def _ob(rows):
    return pd.DataFrame(rows, columns=["con_key", "obligation_no", "due_date", "status", "completed_date", "triggered_on", "deadline_value", "deadline_unit", "met_deadline"])


def test_obligation_status_on_a_date_and_the_recomputed_deadline():
    o = _ob([("C1", 1, D(2026, 1, 10), "completed", D(2026, 1, 9), None, np.nan, None, None),                        # done before the date
             ("C1", 2, D(2026, 1, 10), "completed", D(2026, 1, 15), None, np.nan, None, None),                       # completed after the date: overdue on it
             ("C1", 3, D(2026, 1, 20), "open", None, None, np.nan, None, None),                                      # due after the date: open
             ("C1", 4, D(2026, 1, 12), "open", None, None, np.nan, None, None),                                      # due on the date asked: open
             ("C1", 5, D(2026, 1, 10), "open", None, None, np.nan, None, None),                                      # due on the date: open
             ("C1", 6, D(2026, 1, 1), "waived", None, None, np.nan, None, None),
             ("C2", 1, D(2025, 11, 14), "completed", D(2025, 11, 12), D(2025, 11, 12), 24, "hours", True),           # 24 hours: same day or the next
             ("C2", 2, D(2025, 11, 14), "completed", D(2025, 11, 14), D(2025, 11, 12), 24, "hours", True)])          # two days later: late
    r = delivery.obligation_status(o, D(2026, 1, 12), context=CTX).set_index(["con_key", "obligation_no"])
    assert r.status_on.to_dict() == {("C1", 1): "completed", ("C1", 2): "overdue", ("C1", 3): "open", ("C1", 4): "open", ("C1", 5): "overdue", ("C1", 6): "waived", ("C2", 1): "completed", ("C2", 2): "completed"}
    assert delivery.obligation_status(o, D(2026, 1, 10), context=CTX).set_index(["con_key", "obligation_no"]).status_on[("C1", 5)] == "open", "due on the date: not overdue yet"
    assert r.loc[("C2", 1), "met_recomputed"] == True and r.loc[("C2", 2), "met_recomputed"] == False and pd.isna(r.loc[("C1", 1), "met_recomputed"])  # noqa: E712
    assert r.stored_status[("C1", 2)] == "completed" and r.stored_met_deadline[("C2", 2)] == True  # noqa: E712
    with pytest.raises(FrameError, match="more than one row"):
        delivery.obligation_status(pd.concat([o, o.iloc[:1]]), D(2026, 1, 12), context=CTX)


def test_legal_flags_compare_warranty_years_with_the_fact_of_the_project_country():
    from halvaro.core import fact
    dk, de = fact("legal.contracts.warranty_years.DK").value, fact("legal.contracts.warranty_years.DE").value
    cl = _cl([("C1", 1, "warranty", "works", "warranty_years", float(dk), None, np.nan, D(2023, 1, 1), None, True, "note"), ("C2", 1, "warranty", "works", "warranty_years", float(dk), None, np.nan, D(2023, 1, 1), None, True, "note"),
              ("C1", 2, "payment_terms", "net", "payment_days", 30.0, None, np.nan, D(2023, 1, 1), None, False, None), ("C1", 3, "liability", "cap", "cap", 100.0, None, np.nan, D(2023, 1, 1), None, True, "note")])
    ct = pd.DataFrame({"con_key": ["C1", "C2"], "prj_key": ["P1", "P2"]})
    pr = pd.DataFrame({"prj_key": ["P1", "P2"], "country": ["DK", "DE"]})
    r = delivery.legal_flags(cl, ct, pr, context=CTX).set_index(["con_key", "clause_no"])
    assert list(r.index) == [("C1", 1), ("C1", 3), ("C2", 1)], "the payment clause carries no legal flag"
    assert r.loc[("C1", 1), "warranty_matches"] == True and r.loc[("C2", 1), "warranty_matches"] == (dk == de) and r.loc[("C1", 1), "fact_status"] == "VERIFY"  # noqa: E712
    assert pd.isna(r.loc[("C1", 3), "warranty_matches"]) and r.loc[("C2", 1), "warranty_expected"] == float(de)


def test_registered_staged_and_in_the_index():
    reg = registry.registered()
    names = ["pricing.price_list_on", "pricing.price_gaps", "contracts.framework_for", "contracts.contracts_for_project", "contracts.clauses_on", "contracts.price_adjustment_terms",
             "contracts.notification_clauses_on", "contracts.obligation_status", "contracts.legal_flags"]
    for n in names:
        m = reg[f"halvaro.delivery.{n}"]
        assert m.parameters[-1] == "context" and m.sources          # the oracle pointer of price_list_on is kept in a file of the closed repository
    assert reg["halvaro.delivery.contracts.legal_flags"].facts == ("legal.contracts.warranty_years.DK", "legal.contracts.warranty_years.DE")
    assert registry.check() == [] and {f"halvaro.delivery.{n}" for n in names} <= {r["id"] for r in registry.export_index(library="halvaro-delivery")}
    with pytest.raises(StageRefusal, match="procurement"):
        delivery.price_list_on(_pl([]), D(2023, 1, 1), context=Context(stage="month3", role="r"))


# the baseline


@pytest.mark.release
def test_price_list_contiguity_on_the_baseline_is_reported_not_assumed(load):
    g = delivery.price_gaps(load("procurement", "price_list"), context=CTX)
    assert not set(g.violations.rule) - {"gap"}, "no open row followed by another, no overlap, no reversed row (the generator test)"
    assert len(g.gaps) == len(g.violations) and g.gaps.days.min() >= 1, "measured: the baseline has gaps (asserted nowhere), they are reported"


@pytest.mark.release
def test_one_framework_per_supplier_on_a_sample_of_dates(load):
    ct = load("contracts", "contract")
    sups = sorted(ct[ct.type == "supplier_framework"].sup_key.dropna().unique())
    assert len(sups) > 100
    for d in (D(2023, 6, 1), D(2025, 1, 1), D(2026, 11, 30)):
        found = [len(delivery.framework_for(ct, s, d, context=CTX)) for s in sups[:120]]
        assert max(found) <= 1 and sum(found) > 30, d
    assert len(delivery.framework_for(ct, "SUP-000001", D(2026, 6, 1), context=CTX)) == 1


@pytest.mark.release
def test_price_clauses_of_customer_project_contracts_by_variant(load):
    cl, ct = load("contracts", "clause"), load("contracts", "contract")
    t = delivery.price_adjustment_terms(cl, ct, context=CTX)
    proj = t.terms[t.terms.type == "customer_project"]
    assert set(proj.variant) == {"fixed", "unit", "indexed"} and (proj.n_price_clauses == 1).all()
    assert (proj[proj.variant != "indexed"].pass_through_percent == 0).all() and (proj[proj.variant == "indexed"].pass_through_percent > 0).all()
    assert proj[proj.variant == "indexed"].threshold_percent.isin([0, 3, 5]).all(), "the threshold sits in param2 and is read by name"
    sup = t.terms[t.terms.type == "supplier_framework"]
    assert sup.groupby("con_key").size().max() >= 2, "a supplier contract can have several price clauses (the two of SUP-000001)"
    assert len(t.without_clause) == 0 or set(t.without_clause.type) == {"customer_project"}


@pytest.mark.release
def test_notification_hours_obligations_and_warranty_follow_the_generator(load):
    cl, ct, ob = load("contracts", "clause"), load("contracts", "contract"), load("contracts", "obligation")
    n = delivery.notification_clauses_on(cl, ct, D(2025, 11, 12), context=CTX)
    assert set(n.notification_hours) == {24.0, 48.0, 96.0} and n[n.notification_hours == 24].cus_key.nunique() >= 3
    assert n[(n.cus_key == "CUS-000001")].notification_hours.eq(24).all(), "the story customer is served from Odense"
    before = delivery.notification_clauses_on(cl, ct, D(2025, 3, 2), context=CTX)
    assert set(before[before.cus_key == "CUS-000001"].notification_hours) <= {48.0, 96.0}, "the old clause ends on 2025-03-02 and the 24 hour addendum starts the day after"
    addendum = n[n.notification_hours == 24]
    assert (addendum.valid_from == pd.Timestamp(2025, 3, 3)).any(), "the 24 hour addendum of 2025-03-03 is among them"
    o = delivery.obligation_status(ob, D(2026, 11, 30), context=CTX)
    inc = o[o.obligation_type == "incident_notification"]
    assert len(inc) >= 1 and (inc.triggered_on == pd.Timestamp(2025, 11, 12)).any()
    comp = o[(o.stored_status == "completed")]
    assert (comp.status_on == "completed").all() and (o[o.stored_status == "open"].status_on.isin(["open", "overdue"])).all()
    m = comp.dropna(subset=["stored_met_deadline"])
    assert ((m.completed_date <= m.due_date) == m.stored_met_deadline.astype(bool)).all(), "test_obligations_are_consistent: met_deadline is a date comparison"
    f = delivery.legal_flags(cl, ct, load("projects", "project"), context=CTX)
    assert len(f) > 500 and f.warranty_matches.dropna().all() and set(f.fact_status.dropna()) == {"VERIFY"}
    assert (cl.verify == cl.legal_note.notna()).all()


@pytest.mark.release
def test_contracts_of_the_story_project_and_clauses_with_qualifications(load):
    ct, po, pj, cl = load("contracts", "contract"), load("procurement", "purchase_order"), load("projects", "project"), load("contracts", "clause")
    r = delivery.contracts_for_project(pj, ct, po, "PRJ-000001", context=CTX)
    assert r.kind.iloc[0] == "customer_contract" and r.con_key.iloc[0] == pj.set_index("prj_key").loc["PRJ-000001", "contract_key"]
    q = delivery.clauses_on(cl, D(2026, 11, 30), clause_type="personnel_qualification", context=CTX)
    assert q.qual_key.notna().all() and len(q) > 100


# review fixes: window clipping, running end, kept statuses, weeks, validation and the boundaries mutations must break

def test_gap_window_is_clipped_and_nested_rows_do_not_make_false_gaps():
    p = _pl([_row("S", "I", D(2023, 1, 1), D(2023, 3, 31)), _row("S", "I", D(2023, 6, 1), None)])                       # gap 1 April to 31 May
    g = lambda w: delivery.price_gaps(p, window=w, context=CTX).gaps
    assert g((D(2024, 1, 1), D(2024, 1, 31))).empty, "the window is fully covered: the gap before it is not reported"
    assert g((D(2023, 5, 1), D(2023, 5, 10))).values.tolist() == [["S", "I", pd.Timestamp(2023, 5, 1), pd.Timestamp(2023, 5, 10), 10]], "clipped to the window"
    assert g((D(2023, 3, 31), D(2023, 4, 1))).days.tolist() == [1]
    assert delivery.price_gaps(p.iloc[:1], window=(D(2023, 6, 1), D(2023, 6, 30)), context=CTX).gaps.days.tolist() == [30], "a window after the last closed row: only its own days"
    assert delivery.price_gaps(p.iloc[:1], window=(D(2023, 3, 31), D(2023, 4, 2)), context=CTX).gaps.days.tolist() == [2], "the last valid day is covered; the window's last day counts"
    nested = _pl([_row("S", "I", D(2023, 1, 1), D(2023, 12, 31)), _row("S", "I", D(2023, 3, 1), D(2023, 3, 31)), _row("S", "I", D(2024, 2, 1), None)])
    r = delivery.price_gaps(nested, context=CTX)
    assert r.gaps.days.tolist() == [31], "January 2024 is the only gap; the nested March row does not shorten the covered year"
    assert "overlap" in set(r.violations.rule)
    for bad in (("zz", D(2023, 1, 1)), (None, D(2023, 1, 1)), (D(2023, 1, 1),)):
        with pytest.raises(FrameError, match="window"):
            delivery.price_gaps(p, window=bad, context=CTX)
    assert delivery.price_gaps(p, window=(D(2023, 4, 1), D(2023, 4, 1)), context=CTX).gaps.days.tolist() == [1], "a one day window"


def test_currency_changes_between_rows_are_reported_and_an_empty_list_is_fine():
    p = _pl([_row("S", "I", D(2023, 1, 1), D(2023, 12, 31)), _row("S", "I", D(2024, 1, 1), None)])
    assert delivery.price_gaps(p, context=CTX).currency_changes.empty
    q = p.assign(currency=["DKK", "EUR"])
    c = delivery.price_gaps(q, context=CTX).currency_changes
    assert c.values.tolist() == [["S", "I", pd.Timestamp(2024, 1, 1), "DKK", "EUR"]]
    assert delivery.price_list_on(_pl([]).astype({"unit_price": object}), D(2023, 1, 1), context=CTX).empty and delivery.price_gaps(_pl([]).astype({"unit_price": object}), context=CTX).gaps.empty
    with pytest.raises(FrameError, match="one key as text"):
        delivery.price_list_on(p, D(2023, 1, 1), sup_key=["S", "T", "U"], context=CTX)
    with pytest.raises(FrameError, match="is a number"):
        delivery.price_list_on(p, 20230101, context=CTX)


def test_obligation_keeps_breached_in_force_and_closed_reads_weeks_and_rounds_up():
    o = _ob([("C1", 1, D(2026, 1, 1), "breached", None, None, np.nan, None, False), ("C1", 2, D(2026, 1, 1), "in_force", None, None, np.nan, None, None),
             ("C1", 3, D(2026, 1, 1), "closed", D(2026, 1, 1), None, np.nan, None, None),
             ("C2", 1, D(2026, 1, 20), "completed", D(2026, 1, 8), D(2026, 1, 1), 1, "weeks", True),               # one week: 7 days, completed on the 8th: met
             ("C2", 2, D(2026, 1, 20), "completed", D(2026, 1, 9), D(2026, 1, 1), 1, "weeks", True),               # 8 days: late
             ("C2", 3, D(2026, 1, 20), "completed", D(2026, 1, 3), D(2026, 1, 1), 25, "hours", True),              # 25 hours round up to 2 days: 3 January is met
             ("C2", 4, D(2026, 1, 20), "completed", D(2026, 1, 4), D(2026, 1, 1), 25, "hours", True),              # 3 January is the last day
             ("C2", 5, D(2026, 1, 20), "completed", D(2026, 1, 3), D(2026, 1, 1), 1.5, "days", True),              # 1.5 days round up to 2
             ("C2", 6, D(2026, 1, 20), "completed", D(2026, 1, 4), D(2026, 1, 1), 2, "months", True)])             # unit not read: no recomputed result
    r = delivery.obligation_status(o, D(2026, 6, 1), context=CTX).set_index(["con_key", "obligation_no"])
    assert r.status_on[[("C1", 1), ("C1", 2), ("C1", 3)]].tolist() == ["breached", "in_force", "closed"], "the dates cannot derive these"
    assert [r.met_recomputed[("C2", n)] for n in (1, 2, 3, 4, 5)] == [True, False, True, False, True]
    assert pd.isna(r.met_recomputed[("C2", 6)])
    on_day = delivery.obligation_status(_ob([("C2", 1, D(2026, 1, 10), "completed", D(2026, 1, 10), D(2026, 1, 8), 2, "days", True)]), D(2026, 1, 10), context=CTX)
    assert on_day.met_recomputed.tolist() == [True] and on_day.status_on.tolist() == ["completed"]


def test_framework_not_in_force_notification_columns_contract_kinds_and_bad_keys():
    ct = _ct([_c("F1", "supplier_framework", sup="S1", status="awaiting_signature"), _c("F2", "supplier_framework", sup="S1", status="signed", start=D(2027, 1, 1)), _c("F3", "supplier_framework", sup="S1", status="active", end=D(2025, 1, 1)),
              _c("C1", prj="P1", cus="CUS-1"), _c("C9", "customer_project", cus="CUS-2")])
    f = lambda d: delivery.framework_for(ct, "S1", d, context=CTX).con_key.tolist()
    assert f(D(2024, 6, 1)) == ["F3"] and f(D(2026, 6, 1)) == [], "awaiting signature and signed-not-started are not frameworks in force"
    proj = pd.DataFrame({"prj_key": ["P1"], "contract_key": ["C1"]})
    po = pd.DataFrame({"prj_key": ["P1", "P1"], "con_key": ["F3", "C9"]})
    r = delivery.contracts_for_project(proj, ct, po, "P1", context=CTX)
    assert r.kind.tolist() == ["customer_contract", "other_contract", "supplier_framework"] and r.con_key.tolist() == ["C1", "C9", "F3"], "an order that points at a customer contract is not a supplier framework"
    with pytest.raises(FrameError, match="lacks column.*param_name"):
        delivery.notification_clauses_on(_cl([]).drop(columns="param_name"), ct, D(2025, 6, 1), context=CTX)
    with pytest.raises(FrameError, match="one value as text"):
        delivery.clauses_on(_cl([]), D(2025, 6, 1), con_key=["a", "b", "c"], context=CTX)
    with pytest.raises(FrameError, match="is a number"):
        delivery.framework_for(ct, "S1", 20250101, context=CTX)
    with pytest.raises(FrameError, match="one key as text"):
        delivery.framework_for(ct, ["S1"], D(2025, 1, 1), context=CTX)


def test_legal_flags_refuse_null_verify_and_handle_unknown_countries_and_call_offs():
    from halvaro.core import fact
    dk = float(fact("legal.contracts.warranty_years.DK").value)
    cl = _cl([("C1", 1, "warranty", "works", "warranty_years", dk, None, np.nan, D(2023, 1, 1), None, True, "n"), ("C2", 1, "warranty", "works", "warranty_years", dk, None, np.nan, D(2023, 1, 1), None, True, "n"),
              ("C3", 1, "warranty", "call_off", "warranty_years", dk, None, np.nan, D(2023, 1, 1), None, True, "n")])
    ct = pd.DataFrame({"con_key": ["C1", "C2", "C3"], "prj_key": ["P1", "P2", None]})
    pr = pd.DataFrame({"prj_key": ["P1", "P2"], "country": ["DK", "SE"]})
    r = delivery.legal_flags(cl, ct, pr, context=CTX).set_index("con_key")
    assert r.warranty_matches.tolist()[0] == True and pd.isna(r.warranty_matches["C2"]) and pd.isna(r.warranty_matches["C3"]), "an unknown country and a call-off have no check"  # noqa: E712
    with pytest.raises(FrameError, match="verify has nulls"):
        delivery.legal_flags(cl.assign(verify=[True, None, True]), ct, pr, context=CTX)


# second review: adjacent days, status-only fixtures, the vectorised gaps against the loop they replaced, NaN prices, customer notification summary and recomputed deadlines

def _gaps_reference(price_list, window=None):
    """The per pair loop price_gaps used before it was vectorised, kept as the reference: (gaps, currency_changes) of the checked frame."""
    from halvaro.delivery.pricing import _check
    p = _check(price_list)
    first = last = None
    if window is not None:
        first, last = (pd.Timestamp(w).normalize() for w in window)
    s = p.sort_values(["sup_key", "itm_key", "valid_from"], kind="stable")
    rows, changes = [], []
    open_end = pd.Timestamp("2262-01-01")
    for (sup, itm), g in s.groupby(["sup_key", "itm_key"], sort=True):
        ends = g["valid_to"].fillna(open_end)
        run = ends.cummax().shift(1)
        for f, r in zip(g["valid_from"], run):
            if pd.notna(r) and r < open_end and f > r + pd.DateOffset(days=1):
                rows.append((sup, itm, r + pd.DateOffset(days=1), f - pd.DateOffset(days=1)))
        if first is not None:
            if g["valid_from"].min() > first:
                rows.append((sup, itm, first, g["valid_from"].min() - pd.DateOffset(days=1)))
            if g["valid_to"].notna().all() and ends.max() < last:
                rows.append((sup, itm, ends.max() + pd.DateOffset(days=1), last))
        cur = g["currency"].tolist()
        for a, b, f in zip(cur[:-1], cur[1:], g["valid_from"].tolist()[1:]):
            if a != b:
                changes.append((sup, itm, f, a, b))
    out = []
    for sup, itm, a, b in rows:
        if first is not None:
            a, b = max(a, first), min(b, last)
            if b < a:
                continue
        out.append((sup, itm, a, b, int((b - a).days) + 1))
    gaps = pd.DataFrame(out, columns=["sup_key", "itm_key", "gap_start", "gap_end", "days"]).drop_duplicates().sort_values(["sup_key", "itm_key", "gap_start"]).reset_index(drop=True)
    return gaps, pd.DataFrame(changes, columns=["sup_key", "itm_key", "valid_from", "currency_before", "currency_after"])


def _same_as_reference(pl, window=None):
    new = delivery.price_gaps(pl, window=window, context=CTX)
    gaps, changes = _gaps_reference(pl, window)
    pd.testing.assert_frame_equal(new.gaps, gaps)
    pd.testing.assert_frame_equal(new.currency_changes, changes)
    return new


def _random_price_list(seed, pairs=60):
    rng = np.random.default_rng(seed)
    rows = []
    for k in range(pairs):
        day = D(2023, 1, 1) + dt.timedelta(days=int(rng.integers(0, 400)))
        for _ in range(int(rng.integers(1, 7))):
            length = int(rng.integers(0, 120))
            kind = rng.random()
            end = None if kind < 0.1 else day + dt.timedelta(days=length)           # open rows, some of them followed by others
            cur = ("DKK", "EUR", None)[int(rng.integers(0, 3)) if rng.random() < 0.3 else 0]
            rows.append(_row(f"S{k % 7}", f"I{k // 7}", day, end)[:5] + (cur,) + ("CON-1", "indexation"))
            step = int(rng.choice([-30, -1, 0, 1, 2, 5, length + 1, length + 2, length + 40]))      # overlap, adjacent, gap, nested
            day = day + dt.timedelta(days=max(step, 0))
    rng.shuffle(rows)
    return _pl(rows)


def test_a_row_the_day_after_the_previous_end_is_no_gap_and_a_one_day_hole_is():
    adjacent = _pl([_row("S", "I", D(2023, 1, 1), D(2023, 1, 31)), _row("S", "I", D(2023, 2, 1), D(2023, 2, 28)), _row("S", "I", D(2023, 3, 1), None)])
    assert delivery.price_gaps(adjacent, context=CTX).gaps.empty, "valid_from = previous valid_to + 1 day is contiguous"
    assert delivery.price_gaps(adjacent, window=(D(2023, 1, 1), D(2023, 12, 31)), context=CTX).gaps.empty
    hole = _pl([_row("S", "I", D(2023, 1, 1), D(2023, 1, 31)), _row("S", "I", D(2023, 2, 2), None)])
    assert delivery.price_gaps(hole, context=CTX).gaps.values.tolist() == [["S", "I", pd.Timestamp(2023, 2, 1), pd.Timestamp(2023, 2, 1), 1]], "one day without a price"
    nested = _pl([_row("S", "I", D(2023, 1, 1), D(2023, 3, 31)), _row("S", "I", D(2023, 2, 1), D(2023, 2, 28)), _row("S", "I", D(2023, 4, 1), None)])
    assert delivery.price_gaps(nested, context=CTX).gaps.empty, "the day after the running end, not after the nested row"


def test_signed_alone_is_not_a_framework_in_force():
    ct = _ct([_c("F1", "supplier_framework", sup="S1", status="signed", start=D(2023, 1, 1), end=None)])             # started, not ended: only the status keeps it out
    assert delivery.framework_for(ct, "S1", D(2024, 1, 1), context=CTX).empty
    assert delivery.framework_for(ct.assign(status="active"), "S1", D(2024, 1, 1), context=CTX).con_key.tolist() == ["F1"], "the same dates with another status are in force"
    for status in ("draft", "awaiting_signature"):
        assert delivery.framework_for(ct.assign(status=status), "S1", D(2024, 1, 1), context=CTX).empty


def test_vectorised_gaps_equal_the_loop_on_random_lists_with_and_without_a_window():
    for seed in range(4):
        pl = _random_price_list(seed)
        _same_as_reference(pl)
        for w in ((D(2022, 6, 1), D(2024, 6, 30)), (D(2023, 5, 1), D(2023, 5, 1)), (D(2026, 1, 1), D(2026, 12, 31))):
            _same_as_reference(pl, w)
    assert len(_same_as_reference(_random_price_list(1)).gaps) > 3 and len(_same_as_reference(_random_price_list(2)).currency_changes) > 3, "the random lists really have gaps and currency changes"
    _same_as_reference(_pl([]).astype({"unit_price": object}))
    _same_as_reference(_pl([]).astype({"unit_price": object}), (D(2023, 1, 1), D(2023, 2, 1)))
    _same_as_reference(_pl([_row("S", "I", D(2023, 1, 1), None)]), (D(2023, 1, 1), D(2023, 1, 5)))


def test_gap_modes_without_and_with_a_window_differ_on_leading_and_trailing_days():
    p = _pl([_row("S", "I", D(2023, 3, 1), D(2023, 3, 31)), _row("S", "I", D(2023, 4, 10), D(2023, 4, 30))])
    plain = delivery.price_gaps(p, context=CTX).gaps
    assert plain.values.tolist() == [["S", "I", pd.Timestamp(2023, 4, 1), pd.Timestamp(2023, 4, 9), 9]], "without a window only the hole between two rows"
    assert delivery.price_list_on(p, D(2023, 6, 1), context=CTX).empty, "no price on a later date although no gap is reported"
    w = delivery.price_gaps(p, window=(D(2023, 1, 1), D(2023, 6, 30)), context=CTX).gaps
    assert w.days.tolist() == [59, 9, 61] and w.gap_start.tolist()[0] == pd.Timestamp(2023, 1, 1) and w.gap_end.tolist()[-1] == pd.Timestamp(2023, 6, 30)


def test_price_on_a_date_refuses_a_missing_unit_price():
    p = _pl([_row("S1", "I1", D(2023, 1, 1), D(2023, 12, 31), price=np.nan), _row("S1", "I1", D(2024, 1, 1), None, price=5.0)])
    with pytest.raises(FrameError, match="no unit_price for S1, I1"):
        delivery.price_list_on(p, D(2023, 6, 1), context=CTX)
    assert delivery.price_list_on(p, D(2024, 6, 1), context=CTX).unit_price.tolist() == [5.0], "a row without a price that is not valid on the date is no problem"


def test_notification_hours_by_customer_summarises_mixed_hours_and_keeps_the_clause_rows():
    cl = _cl([("C1", 1, "notification", "incident", "notification_hours", 48.0, None, np.nan, D(2023, 1, 1), None, False, None), ("C2", 1, "notification", "incident", "notification_hours", 96.0, None, np.nan, D(2023, 1, 1), None, False, None),
              ("C3", 1, "notification", "incident", "notification_hours", 24.0, None, np.nan, D(2023, 1, 1), None, False, None), ("C4", 1, "notification", "incident", "notification_hours", 24.0, None, np.nan, D(2023, 1, 1), None, False, None),
              ("C5", 1, "notification", "incident", "notification_hours", 72.0, None, np.nan, D(2023, 1, 1), None, False, None), ("C6", 1, "notification", "incident", "notification_hours", 12.0, None, np.nan, D(2030, 1, 1), None, False, None)])
    ct = pd.DataFrame({"con_key": ["C1", "C2", "C3", "C4", "C5", "C6"], "cus_key": ["CUS-2", "CUS-2", "CUS-1", "CUS-1", None, "CUS-3"]})
    s = delivery.notification_hours_by_customer(cl, ct, D(2025, 1, 1), context=CTX)
    assert s.columns.tolist() == ["cus_key", "min_hours", "max_hours", "n_contracts", "mixed"]
    assert s.values.tolist() == [["CUS-1", 24.0, 24.0, 2, False], ["CUS-2", 48.0, 96.0, 2, True]], "mixed hours are flagged, equal hours are not, no customer and not yet valid are left out"
    n = delivery.notification_clauses_on(cl, ct, D(2025, 1, 1), context=CTX)
    assert n.columns.tolist() == ["con_key", "cus_key", "notification_hours", "valid_from"] and n.con_key.tolist() == ["C3", "C4", "C1", "C2", "C5"], "one row per contract, unchanged"
    assert delivery.notification_hours_by_customer(cl.iloc[:0], ct, D(2025, 1, 1), context=CTX).empty


def test_recomputed_deadline_without_a_trigger_is_a_date_comparison_on_every_stored_deadline():
    o = _ob([("C1", 1, D(2026, 1, 10), "completed", D(2026, 1, 10), None, np.nan, None, True),                       # on the due date: met
             ("C1", 2, D(2026, 1, 10), "completed", D(2026, 1, 11), None, np.nan, None, False),                     # one day late
             ("C1", 3, D(2026, 1, 10), "completed", D(2026, 1, 9), None, np.nan, None, False),                      # stored value wrong: the recomputation says met
             ("C1", 4, D(2026, 1, 10), "overdue", None, None, np.nan, None, True),                                   # not completed: null
             ("C1", 5, D(2026, 1, 10), "completed", D(2026, 1, 9), None, np.nan, None, None),                        # no stored deadline result: null
             ("C1", 6, D(2026, 1, 10), "completed", D(2026, 1, 20), None, np.nan, None, True),                       # completed after the date asked: not completed on it
             ("C2", 1, D(2026, 1, 10), "completed", D(2026, 1, 9), D(2026, 1, 1), 2, "months", True),                # trigger with an unread unit: stays null
             ("C2", 2, D(2026, 1, 10), "completed", D(2026, 1, 4), D(2026, 1, 1), 24, "hours", True)])               # the trigger rule decides: 2 January is the limit, 4 January is late
    r = delivery.obligation_status(o, D(2026, 1, 15), context=CTX).set_index(["con_key", "obligation_no"]).met_recomputed
    assert r[("C1", 1)] == True and r[("C1", 2)] == False and r[("C1", 3)] == True  # noqa: E712
    assert all(pd.isna(r[k]) for k in (("C1", 4), ("C1", 5), ("C1", 6), ("C2", 1))) and r[("C2", 2)] == False  # noqa: E712


@pytest.mark.release
def test_vectorised_gaps_equal_the_loop_on_the_baseline(load):
    pl = load("procurement", "price_list")
    _same_as_reference(pl)
    new = _same_as_reference(pl, (D(2023, 1, 1), D(2026, 11, 30)))
    assert len(new.gaps) == 6 and new.gaps.days.max() == 1387, "the 2 pairs with a hole, with leading and trailing days"


@pytest.mark.release
def test_recomputed_deadline_agrees_with_the_stored_one_on_every_row_with_both_dates(load):
    ob = load("contracts", "obligation")
    o = delivery.obligation_status(ob, D(2026, 11, 30), context=CTX)
    both = o.dropna(subset=["completed_date", "due_date", "stored_met_deadline"])
    assert len(both) > 2000 and both.met_recomputed.notna().all(), "recomputed for every obligation with both dates and a stored result, not only the four incident rows"
    assert (both.met_recomputed.astype(bool) == both.stored_met_deadline.astype(bool)).all()
    assert (o.loc[o.triggered_on.notna() & o.completed_date.notna(), "met_recomputed"].notna()).all()


@pytest.mark.release
def test_notification_hours_by_customer_flags_the_customers_with_mixed_hours(load):
    cl, ct = load("contracts", "clause"), load("contracts", "contract")
    s = delivery.notification_hours_by_customer(cl, ct, D(2025, 11, 12), context=CTX).set_index("cus_key")
    n = delivery.notification_clauses_on(cl, ct, D(2025, 11, 12), context=CTX)
    assert len(s) == n.cus_key.nunique() == 18 and s.n_contracts.sum() == n.cus_key.notna().sum()
    assert s.loc["CUS-000001", ["min_hours", "max_hours"]].tolist() == [24.0, 24.0] and not s.loc["CUS-000001", "mixed"]
    assert s.loc["CUS-000002", ["min_hours", "max_hours"]].tolist() == [48.0, 96.0] and s.loc["CUS-000002", "mixed"]
    assert s.mixed.sum() == 2 and (s.mixed == (s.min_hours != s.max_hours)).all()


# third review: the window dates are refused as numbers and with a time zone, like as_of

def test_gap_window_refuses_numbers_and_time_zones_with_a_frame_error():
    p = _pl([_row("S", "I", D(2023, 1, 1), D(2023, 3, 31)), _row("S", "I", D(2023, 4, 10), None)])
    for bad in ((20230101, 20261130), (2023, 2026), (D(2023, 1, 1), 20261130), (True, D(2023, 6, 1)), (1.5, D(2023, 6, 1))):
        with pytest.raises(FrameError, match="window .* is a number"):
            delivery.price_gaps(p, window=bad, context=CTX)
    for bad in ((pd.Timestamp("2023-01-01", tz="UTC"), "2023-06-30"), ("2023-01-01", "2023-06-30T00:00:00+02:00")):
        with pytest.raises(FrameError, match="without a time zone"):
            delivery.price_gaps(p, window=bad, context=CTX)
    assert delivery.price_gaps(p, window=("2023-01-01", pd.Timestamp("2023-06-30 15:00")), context=CTX).gaps.days.tolist() == [9], "text and time stamps stay accepted"
