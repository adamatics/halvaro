"""Ledger functions, part b: trial balance rebuilt from the lines, journal integrity, retained earnings roll, statutory lines. Synthetic frames, then the baseline release (stored trial balance, T16)."""

import numpy as np
import pandas as pd
import pytest

import halvaro.finance as fin
from halvaro.core import Context, FrameError, StageRefusal

CTX = Context(stage="month3", role="r")


# ---- synthetic ledger


def _gl():
    return pd.DataFrame({"gl_key": ["GL-1000", "GL-2000", "GL-3300", "GL-4000", "GL-5000"], "statement": ["BS", "BS", "BS", "IS", "IS"], "normal_balance": ["debit", "credit", "credit", "credit", "debit"],
                         "dk_statutory_map": ["DK-A", "DK-B", "DK-C", "DK-D", "DK-E"], "de_statutory_map": ["DE-A", "DE-B", "DE-C", "DE-D", "DE-E"]})


def _lines(rows):
    """rows: (journal_no, period, gl_key, amount, source) in DKK."""
    return pd.DataFrame({"le_key": "LE-01", "journal_no": [r[0] for r in rows], "line_no": list(range(1, len(rows) + 1)), "gl_key": [r[2] for r in rows], "amount": [float(r[3]) for r in rows],
                         "amount_dkk": [float(r[3]) for r in rows], "currency": "DKK", "period": [r[1] for r in rows], "source": [r[4] for r in rows], "prj_key": None})


def _ledger():
    jl = _lines([(1, "2023-11", "GL-1000", 1000, "opening"), (1, "2023-11", "GL-3300", -1000, "opening"),
                 (2, "2023-11", "GL-1000", 300, "ar"), (2, "2023-11", "GL-4000", -300, "ar"),
                 (3, "2023-12", "GL-5000", 100, "ap"), (3, "2023-12", "GL-1000", -100, "ap"),
                 (4, "2024-01", "GL-1000", 50, "ar"), (4, "2024-01", "GL-4000", -50, "ar"),
                 (5, "2024-02", "GL-1000", 10, "ar"), (5, "2024-02", "GL-4000", -10, "ar")])
    ob = pd.DataFrame({"le_key": "LE-01", "gl_key": ["GL-1000", "GL-3300"], "amount": [1000.0, -1000.0], "amount_dkk": [1000.0, -1000.0]})
    return jl, ob, _gl()


def _tb(carry=True, **kw):
    jl, ob, gl = _ledger()
    return fin.rebuild_trial_balance(jl, ob, gl, context=CTX, carry_results=carry, **kw)


def _row(tb, period, gl):
    r = tb[(tb.period == period) & (tb.gl_key == gl)]
    assert len(r) == 1, (period, gl, len(r))
    return r.iloc[0]


def test_trial_balance_rebuild_balance_sheet_carries_result_accounts_restart_and_retained_earnings_takes_the_result():
    env = _tb()
    tb = env.value
    assert env.status == "VERIFY" and env.stage == "month3" and list(tb.columns) == ["le_key", "period", "gl_key", "opening_balance", "debit", "credit", "closing_balance", "currency", "closing_balance_dkk"]
    assert tuple(_row(tb, "2023-11", "GL-1000")[["opening_balance", "debit", "credit", "closing_balance"]]) == (1000, 300, 0, 1300)
    assert tuple(_row(tb, "2023-12", "GL-1000")[["opening_balance", "debit", "credit", "closing_balance"]]) == (1300, 0, 100, 1200)
    assert tuple(_row(tb, "2023-12", "GL-4000")[["opening_balance", "credit", "closing_balance"]]) == (-300, 0, -300), "a result account with a balance but no movement keeps its row"
    assert tuple(_row(tb, "2023-12", "GL-5000")[["opening_balance", "debit", "closing_balance"]]) == (0, 100, 100)
    assert tuple(_row(tb, "2024-01", "GL-4000")[["opening_balance", "credit", "closing_balance"]]) == (0, 50, -50), "result accounts restart at the fiscal year start"
    assert tb[(tb.period == "2024-01") & (tb.gl_key == "GL-5000")].empty, "zero opening, zero movement, zero closing: no row"
    re = tb[tb.gl_key == "GL-3300"].set_index("period")
    assert re.closing_balance.to_dict() == {"2023-11": -1000, "2023-12": -1000, "2024-01": -1200, "2024-02": -1200} and re.opening_balance["2024-01"] == -1200 and (re.debit == 0).all()
    assert (tb.groupby("period")["closing_balance"].sum().abs() < 1e-9).all() and (tb.groupby("period")["closing_balance_dkk"].sum().abs() < 1e-9).all()
    assert _row(tb, "2024-02", "GL-4000").closing_balance == -60 and (tb.currency == "DKK").all()


def test_opening_journals_are_not_movements_and_carry_results_false_leaves_the_roll_out():
    tb = _tb(carry=False).value
    assert _row(tb, "2023-11", "GL-1000").debit == 300
    re = tb[tb.gl_key == "GL-3300"]
    assert (re.closing_balance == -1000).all() and (tb.groupby("period")["closing_balance"].sum().round(2) != 0).any()
    no_opening = _ledger()
    jl = no_opening[0].assign(source="ar")
    assert _row(fin.rebuild_trial_balance(jl, no_opening[1], no_opening[2], context=CTX).value, "2023-11", "GL-1000").debit == 1300


def test_dkk_residue_rows_cleared_accounts_and_half_cent_inputs():
    jl, ob, gl = _ledger()
    jl.loc[(jl.journal_no == 4) & (jl.gl_key == "GL-4000"), "amount_dkk"] = -50.01
    tb = fin.rebuild_trial_balance(jl, ob, gl, context=CTX).value
    assert _row(tb, "2024-01", "GL-4000").closing_balance_dkk == -50.01
    jl2 = _lines([(1, "2023-11", "GL-1000", 1000, "opening"), (1, "2023-11", "GL-3300", -1000, "opening"), (2, "2023-11", "GL-5000", 100, "ap"), (2, "2023-11", "GL-1000", -100, "ap"),
                  (3, "2023-12", "GL-5000", -100, "ap"), (3, "2023-12", "GL-1000", 100, "ap")])
    jl2["amount_dkk"] = jl2["amount"]
    jl2.loc[2, "amount_dkk"] = 99.99                                       # EUR style rounding residue: local nets to zero, DKK does not
    t = fin.rebuild_trial_balance(jl2, ob, gl, context=CTX).value
    assert _row(t, "2023-12", "GL-5000").closing_balance == 0 and abs(_row(t, "2023-12", "GL-5000").closing_balance_dkk - (-0.01)) < 1e-9


def test_trial_balance_refusals():
    jl, ob, gl = _ledger()
    with pytest.raises(FrameError, match="not in finance.gl_account.*GL-9999"):
        fin.rebuild_trial_balance(jl.assign(gl_key="GL-9999"), ob, gl, context=CTX)
    with pytest.raises(FrameError, match="more than one currency"):
        fin.rebuild_trial_balance(jl.assign(currency=["DKK", "EUR"] * 5), ob, gl, context=CTX)
    with pytest.raises(FrameError, match="GL-4000 is not a balance sheet account"):
        fin.rebuild_trial_balance(jl, ob, gl, context=CTX, retained_earnings_gl="GL-4000")
    with pytest.raises(FrameError, match="lacks column.*source"):
        fin.rebuild_trial_balance(jl.drop(columns="source"), ob, gl, context=CTX)


def test_roll_equals_the_carry_and_refuses_a_table_that_already_rolled():
    jl, ob, gl = _ledger()
    raw = fin.rebuild_trial_balance(jl, ob, gl, context=CTX, carry_results=False).value
    stored = fin.rebuild_trial_balance(jl, ob, gl, context=CTX).value
    env = fin.roll_retained_earnings(raw, gl, context=CTX)
    r = env.value
    assert env.status == "VERIFY" and len(r) == len(stored)
    m = r.merge(stored, on=["le_key", "period", "gl_key"], suffixes=("", "_s"))
    assert (m.rolled_closing_balance - m.closing_balance_s).abs().max() == 0 and (m.rolled_opening_balance - m.opening_balance_s).abs().max() == 0 and (m.rolled_closing_balance_dkk - m.closing_balance_dkk_s).abs().max() == 0
    assert (r.loc[r.gl_key != "GL-3300", "rolled_closing_balance"] == r.loc[r.gl_key != "GL-3300", "closing_balance"]).all()
    with pytest.raises(FrameError, match="already carries the results into GL-3300"):
        fin.roll_retained_earnings(stored, gl, context=CTX)
    two_years = _tb(carry=False).value
    assert fin.roll_retained_earnings(two_years[two_years.period < "2024-01"], gl, context=CTX).value.eval("rolled_closing_balance - closing_balance").abs().max() == 0, "an unfinished first year rolls nothing"


def test_roll_adds_the_retained_earnings_row_when_the_account_has_no_balance():
    jl, ob, gl = _ledger()
    ob2 = ob.assign(amount=[1000.0, 0.0], amount_dkk=[1000.0, 0.0])
    jl2 = jl[jl.source != "opening"]
    raw = fin.rebuild_trial_balance(jl2, ob2, gl, context=CTX, carry_results=False).value
    assert raw[raw.gl_key == "GL-3300"].empty
    r = fin.roll_retained_earnings(raw, gl, context=CTX).value
    re = r[r.gl_key == "GL-3300"].set_index("period")
    assert set(re.index) == {"2023-11", "2023-12", "2024-01", "2024-02"}
    assert re.loc["2024-01", "rolled_closing_balance"] == -200 and re.loc["2023-11", "rolled_closing_balance"] == 0 and (re.currency == "DKK").all()


# ---- journal integrity


def _journals():
    h = pd.DataFrame({"le_key": "LE-01", "journal_no": [1, 2, 3], "line_count": [2, 2, 3]})
    ln = pd.DataFrame({"le_key": "LE-01", "journal_no": [1, 1, 2, 2, 3, 3, 3], "line_no": [1, 2, 1, 2, 1, 2, 3], "amount": [100.0, -100.0, 5.5, -5.5, 10.0, 20.0, -30.0], "currency": "DKK"})
    ln["amount_dkk"] = ln["amount"]
    return h, ln


def _rules(h, ln):
    env = fin.journal_integrity(h, ln, context=CTX)
    return sorted(zip(env.value["key"], env.value["rule"])), env


def test_clean_ledger_has_no_violations_and_carries_the_status_of_the_numbering_fact():
    h, ln = _journals()
    rules, env = _rules(h, ln)
    assert rules == [] and env.status == "VERIFY" and env.facts_used[0][0] == "fin.bookkeeping.journal_numbering" and list(env.value.columns) == ["table", "key", "rule", "detail"]


def test_each_integrity_rule_fires_on_its_defect():
    h, ln = _journals()
    cases = {
        "unbalanced_local": (h, ln.assign(amount=[100.0, -99.99, 5.5, -5.5, 10.0, 20.0, -30.0])),
        "unbalanced_dkk": (h, ln.assign(amount_dkk=[100.0, -100.0, 5.5, -5.0, 10.0, 20.0, -30.0])),
        "line_count": (h.assign(line_count=[2, 3, 3]), ln),
        "header_without_lines": (pd.concat([h, pd.DataFrame({"le_key": ["LE-01"], "journal_no": [4], "line_count": [2]})]), ln),
        "orphan_lines": (h.iloc[:2], ln),
        "duplicate_line": (h, ln.assign(line_no=[1, 1, 1, 2, 1, 2, 3])),
        "numbering_gap": (h.assign(journal_no=[1, 2, 5]), ln.assign(journal_no=[1, 1, 2, 2, 5, 5, 5])),
        "duplicate_header": (pd.concat([h, h.iloc[:1]]), ln),
    }
    for rule, (hh, ll) in cases.items():
        rules, _ = _rules(hh, ll)
        assert rule in {r for _, r in rules}, (rule, rules)
    assert _rules(h, ln.assign(amount=[100.0, -99.99, 5.5, -5.5, 10.0, 20.0, -30.0]))[0][0][0] == "LE-01 1"
    assert {r for _, r in _rules(h, ln)[0]} == set()


def _eur_journal():
    """Three EUR lines that balance locally but whose rounded DKK conversions do not: the residual belongs on the largest line (as the generator posts it)."""
    from halvaro.core import convert

    for a, b in ((1.01, 2.03), (5.07, 3.11), (10.13, 7.21), (0.07, 0.11), (3.33, 1.17)):
        amts = [round(a + b, 2), -a, -b]
        conv = [int(convert(pd.Series([int(round(x * 100))]), "EUR", "DKK", basis="booking").iloc[0]) for x in amts]
        if sum(conv) != 0:
            return amts, conv
    raise AssertionError("no rounding residual found")


def _eur_frames(dkk_cents):
    amts, _ = _eur_journal()
    h = pd.DataFrame({"le_key": "LE-02", "journal_no": [1], "line_count": [3]})
    ln = pd.DataFrame({"le_key": "LE-02", "journal_no": 1, "line_no": [1, 2, 3], "amount": amts, "currency": "EUR", "amount_dkk": [c / 100 for c in dkk_cents]})
    return h, ln


def test_dkk_conversion_rule_residual_on_the_largest_line_only():
    amts, conv = _eur_journal()
    residual = -sum(conv)
    clean = conv[:]
    clean[0] += residual                                                    # the largest line (index 0 is the sum of the other two)
    assert _rules(*_eur_frames(clean))[0] == []
    moved = conv[:]
    moved[1] += residual                                                    # residual on a smaller line
    rules = _rules(*_eur_frames(moved))[0]
    assert ("LE-02 1", "dkk_conversion") in rules and ("LE-02 1", "unbalanced_dkk") not in rules
    two = clean[:]
    two[1], two[2] = two[1] + 1, two[2] - 1                                 # two more lines off the rounded conversion, still balanced
    assert ("LE-02 1", "dkk_conversion") in _rules(*_eur_frames(two))[0]
    big = clean[:]
    big[0] += 5                                                             # the residual larger than half a cent per other line
    big[1] -= 5
    r = _rules(*_eur_frames(big))[0]
    assert ("LE-02 1", "dkk_conversion") in r and ("LE-02 1", "unbalanced_dkk") not in r
    dk = pd.DataFrame({"le_key": "LE-01", "journal_no": 1, "line_no": [1, 2], "amount": [10.0, -10.0], "currency": "DKK", "amount_dkk": [10.01, -10.01]})
    r4, _ = _rules(pd.DataFrame({"le_key": "LE-01", "journal_no": [1], "line_count": [2]}), dk)
    assert ("LE-01 1", "dkk_conversion") in r4, "a DKK journal has no residual"


# ---- statutory lines


def _map():
    rows = []
    for c in ("DK", "DE"):
        for k in "ABCDE":
            rows.append({"map_code": f"{c}-{k}", "country": c, "statement": "BS", "line_order": ord(k), "line_code": k, "label": f"line {k}", "normal_side": "debit"})
    return pd.DataFrame(rows)


def test_statutory_line_of_gives_one_row_per_account_and_country_and_refuses_gaps():
    s = fin.statutory_line_of(_gl(), _map(), context=CTX)
    assert len(s) == 10 and s.groupby("gl_key").country.apply(list).iloc[0] == ["DE", "DK"] and s.set_index(["gl_key", "country"]).loc[("GL-3300", "DK"), "line_code"] == "C"
    with pytest.raises(FrameError, match="no dk_statutory_map.*GL-1000"):
        fin.statutory_line_of(_gl().assign(dk_statutory_map=[None, "DK-B", "DK-C", "DK-D", "DK-E"]), _map(), context=CTX)
    with pytest.raises(FrameError, match="not in finance.statutory_map_line.*DE-Z"):
        fin.statutory_line_of(_gl().assign(de_statutory_map=["DE-Z", "DE-B", "DE-C", "DE-D", "DE-E"]), _map(), context=CTX)
    with pytest.raises(FrameError, match="duplicate map_code"):
        fin.statutory_line_of(_gl(), pd.concat([_map(), _map().iloc[:1]]), context=CTX)
    swapped = _gl().assign(dk_statutory_map=["DE-A", "DK-B", "DK-C", "DK-D", "DK-E"])
    with pytest.raises(FrameError, match="other country"):
        fin.statutory_line_of(swapped, _map(), context=CTX)


def test_statutory_lines_refuse_duplicate_accounts():
    with pytest.raises(FrameError, match="duplicate gl_key"):
        fin.statutory_line_of(pd.concat([_gl(), _gl()]), _map(), context=CTX)


def test_rebuild_refuses_empty_ledgers_result_account_openings_and_lonely_entities():
    jl, ob, gl = _ledger()
    with pytest.raises(FrameError, match="is empty"):
        fin.rebuild_trial_balance(jl.iloc[:0], ob, gl, context=CTX)
    with pytest.raises(FrameError, match="opening items are on result accounts.*GL-4000"):
        fin.rebuild_trial_balance(jl, pd.concat([ob, ob.iloc[:1].assign(gl_key="GL-4000")]), gl, context=CTX)
    with pytest.raises(FrameError, match="entities .*LE-09.* have opening items but no journal lines"):
        fin.rebuild_trial_balance(jl, pd.concat([ob, ob.iloc[:1].assign(le_key="LE-09")]), gl, context=CTX)
    with pytest.raises(FrameError, match="amounts are null"):
        fin.rebuild_trial_balance(jl.assign(amount=[1.0, 1.0, np.nan] + [1.0] * 7), ob, gl, context=CTX)


def test_roll_output_has_no_helper_columns():
    jl, ob, gl = _ledger()
    raw = fin.rebuild_trial_balance(jl, ob, gl, context=CTX, carry_results=False).value
    r = fin.roll_retained_earnings(raw, gl, context=CTX).value
    assert list(r.columns) == list(raw.columns) + ["rolled_opening_balance", "rolled_closing_balance", "rolled_closing_balance_dkk"]


def test_integrity_numbering_null_counts_unknown_currency_and_duplicate_headers():
    h, ln = _journals()
    rules = lambda hh, ll: sorted(r for _, r in _rules(hh, ll)[0])
    assert rules(h.assign(journal_no=[2, 3, 4]), ln.assign(journal_no=[2, 2, 3, 3, 4, 4, 4])) == ["numbering_gap"], "numbering starts at 1"
    assert rules(h.assign(line_count=[2, None, 3]), ln) == ["line_count"], "a null count is a count mismatch, not an orphan"
    dup = pd.concat([h, h.iloc[:1]])
    assert rules(dup, ln) == ["duplicate_header"], "a duplicate header is reported once and does not double count"
    assert rules(h, ln.assign(currency=["XXX"] * 2 + ["DKK"] * 5)) == ["unknown_currency"]
    lines_only = ln.assign(journal_no=[1, 1, 2, 2, 3, 3, 4])
    assert "orphan_lines" in rules(h, lines_only) and "numbering_gap" not in rules(h, lines_only)


def test_other_numbering_rules_in_the_fact_raise(monkeypatch):
    import halvaro.finance.ledger as led_mod

    real = led_mod.fact
    monkeypatch.setattr(led_mod, "fact", lambda i: type("F", (), {"id": i, "value": "per_year", "status": "VERIFY"})() if i == "fin.bookkeeping.journal_numbering" else real(i))
    h, ln = _journals()
    with pytest.raises(FrameError, match="only gapless_per_entity is checked"):
        fin.journal_integrity(h, ln, context=CTX)


# ---- stage and registry


def test_every_function_refuses_day1_and_names_finance():
    jl, ob, gl = _ledger()
    h, ln = _journals()
    day1 = Context(stage="day1", role="r")
    calls = [lambda: fin.rebuild_trial_balance(jl, ob, gl, context=day1), lambda: fin.journal_integrity(h, ln, context=day1),
             lambda: fin.roll_retained_earnings(_tb(carry=False).value, gl, context=day1), lambda: fin.statutory_line_of(gl, _map(), context=day1)]
    for c in calls:
        with pytest.raises(StageRefusal, match="finance"):
            c()


# ---- survivors of the mutation review


def _dkk_journal(amounts, dkk):
    h = pd.DataFrame({"le_key": ["LE-01"], "journal_no": [1], "line_count": [len(amounts)]})
    ln = pd.DataFrame({"le_key": "LE-01", "journal_no": 1, "line_no": range(1, len(amounts) + 1), "amount": amounts, "currency": "DKK", "amount_dkk": dkk})
    return h, ln


def test_integrity_negative_sums_count_mismatches_and_dkk_journal_rule():
    h, ln = _journals()
    r = lambda hh, ll: sorted(x for _, x in _rules(hh, ll)[0])
    assert r(h, ln.assign(amount=[100.0, -100.01, 5.5, -5.5, 10.0, 20.0, -30.0], amount_dkk=[100.0, -100.01, 5.5, -5.5, 10.0, 20.0, -30.0])) == ["unbalanced_dkk", "unbalanced_local"], "a journal that sums negative is flagged"
    got = r(h, ln.assign(amount_dkk=[100.0, -100.0, 5.5, -5.6, 10.0, 20.0, -30.0]))
    assert "unbalanced_dkk" in got and "unbalanced_local" not in got, "negative in DKK"
    assert r(h.assign(line_count=[1, 2, 3]), ln) == ["line_count"], "a header that claims fewer lines than there are"
    one_off = _dkk_journal([10.0, -4.0, -6.0], [10.0, -4.0, -6.0])
    assert r(*one_off) == []
    off_by_cent = _dkk_journal([10.0, -4.0, -6.0], [10.01, -4.01, -6.0])
    assert set(r(*off_by_cent)) == {"dkk_conversion"}, "two lines off in a DKK journal"
    single = _dkk_journal([10.0, -4.0, -6.0], [10.01, -4.0, -6.01])
    assert set(r(*single)) == {"dkk_conversion"}, "a DKK journal has no residual line, even one"


def test_integrity_residual_size_and_sign_on_the_largest_line():
    amts, conv = _eur_journal()
    resid = -sum(conv)
    base = conv[:]
    base[0] += resid
    for extra in (3, -3):
        big = base[:]
        big[0] += extra                                                     # the largest line carries the residual, now too large for three lines (limit 1 cent)
        big[1] -= extra
        assert ("LE-02 1", "dkk_conversion") in _rules(*_eur_frames(big))[0], extra
    ok = base[:]
    assert _rules(*_eur_frames(ok))[0] == []


def test_integrity_numbering_gaps_are_per_entity_and_start_at_one():
    h = pd.DataFrame({"le_key": ["LE-01", "LE-01", "LE-02", "LE-02", "LE-02"], "journal_no": [1, 2, 1, 2, 4], "line_count": 1})
    ln = pd.DataFrame({"le_key": h.le_key, "journal_no": h.journal_no, "line_no": 1, "amount": 0.0, "amount_dkk": 0.0, "currency": "DKK"})
    env = fin.journal_integrity(h, ln, context=CTX).value
    assert env[env.rule == "numbering_gap"].key.tolist() == ["LE-02"], "LE-01 is complete, the gap of LE-02 is not hidden by it"
    assert "first 3" in env[env.rule == "numbering_gap"].detail.iloc[0]
    h2 = h.assign(journal_no=[2, 3, 1, 2, 3])
    assert fin.journal_integrity(h2, ln.assign(journal_no=h2.journal_no), context=CTX).value.key.tolist() == ["LE-01"], "a first number above 1 is a gap"
    dup = ln.iloc[:2].copy()
    two = fin.journal_integrity(h, pd.concat([ln, dup.assign(line_no=1)]), context=CTX).value
    assert (two.rule == "duplicate_line").sum() == 2


def test_roll_refuses_a_stored_table_after_a_loss_year_and_unsorted_input_works():
    jl, ob, gl = _ledger()
    loss = jl.copy()
    loss.loc[(loss.gl_key == "GL-4000") & (loss.journal_no == 2), "amount"] = 300.0           # a debit instead of a credit: the first year makes a loss
    loss.loc[(loss.gl_key == "GL-1000") & (loss.journal_no == 2), "amount"] = -300.0
    stored = fin.rebuild_trial_balance(loss, ob, gl, context=CTX).value
    with pytest.raises(FrameError, match="already carries"):
        fin.roll_retained_earnings(stored, gl, context=CTX)
    raw = fin.rebuild_trial_balance(jl, ob, gl, context=CTX, carry_results=False).value
    shuffled = raw.sample(frac=1, random_state=4)
    a, b = fin.roll_retained_earnings(raw, gl, context=CTX).value, fin.roll_retained_earnings(shuffled, gl, context=CTX).value
    pd.testing.assert_frame_equal(a.reset_index(drop=True), b.reset_index(drop=True))
    assert a.index.tolist() == list(range(len(a))) and a[["le_key", "period", "gl_key"]].values.tolist() == sorted(a[["le_key", "period", "gl_key"]].values.tolist())
    with pytest.raises(FrameError, match="GL-4000 is not a balance sheet account"):
        fin.roll_retained_earnings(raw, gl, retained_earnings_gl="GL-4000", context=CTX)


def test_rebuild_checks_opening_items_and_carries_into_a_new_retained_earnings_row():
    jl, ob, gl = _ledger()
    with pytest.raises(FrameError, match="not in finance.gl_account.*GL-9999"):
        fin.rebuild_trial_balance(jl, pd.concat([ob, ob.iloc[:1].assign(gl_key="GL-9999")]), gl, context=CTX)
    no_re = ob[ob.gl_key != "GL-3300"].assign(amount=[1000.0], amount_dkk=[1000.0])
    tb = fin.rebuild_trial_balance(jl[jl.source != "opening"], no_re, gl, context=CTX).value
    re = tb[tb.gl_key == "GL-3300"].set_index("period")
    assert re.closing_balance.to_dict() == {"2024-01": -200.0, "2024-02": -200.0}, "the carry opens the retained earnings row in the new fiscal year"


def test_statutory_lines_are_ordered_by_account_then_country():
    s = fin.statutory_line_of(_gl().iloc[::-1], _map(), context=CTX)
    assert s[["gl_key", "country"]].values.tolist() == sorted(s[["gl_key", "country"]].values.tolist()) and s.index.tolist() == list(range(len(s)))


def test_rebuild_refuses_lines_that_would_be_dropped_silently():
    jl, ob, gl = _ledger()
    for bad, msg in ((jl.assign(le_key=jl.le_key.where(jl.index != 2, None)), "every row"), (jl.assign(gl_key=jl.gl_key.where(jl.index != 2, None)), "every row"),
                     (jl.assign(period=jl.period.where(jl.index != 2, None)), "every row"), (jl.assign(period=jl.period.where(jl.index != 2, "2023-2")), "like 2025-02"),
                     (jl.assign(period=jl.period.where(jl.index != 2, "2023-13")), "like 2025-02")):
        with pytest.raises(FrameError, match=msg):
            fin.rebuild_trial_balance(bad, ob, gl, context=CTX)
    with pytest.raises(FrameError, match="more than one row"):
        fin.rebuild_trial_balance(jl, ob, pd.concat([gl, gl.iloc[:1]]), context=CTX)
    with pytest.raises(FrameError, match="IS or BS"):
        fin.rebuild_trial_balance(jl, ob, gl.assign(statement=["BS", "BS", "BS", "OBS", "IS"]), context=CTX)
    with pytest.raises(FrameError, match="every row"):
        fin.rebuild_trial_balance(jl, ob.assign(le_key=[None, "LE-01"]), gl, context=CTX)


def test_journal_integrity_numbering_from_zero_and_null_numbers():
    h, ln = _journals()
    h0, ln0 = h.assign(journal_no=[0, 1, 2]), ln.assign(journal_no=ln.journal_no - 1)
    assert ("LE-01", "numbering_gap") not in _rules(h0, ln0)[0], "a numbering that starts at 0 is gapless (no crash, no gap)"
    h2, ln2 = h.assign(journal_no=[2, 3, 4]), ln.assign(journal_no=ln.journal_no + 1)
    assert ("LE-01", "numbering_gap") in _rules(h2, ln2)[0], "starting at 2 leaves journal 1 missing"
    h3, ln3 = h.assign(journal_no=[1, 2, 5]), ln.assign(journal_no=ln.journal_no.replace({3: 5}))
    env = _rules(h3, ln3)[1]
    assert "first 3" in env.value[env.value.rule == "numbering_gap"].detail.iloc[0]
    with pytest.raises(FrameError, match="every row"):
        fin.journal_integrity(h.assign(journal_no=[1, 2, None]), ln, context=CTX)
