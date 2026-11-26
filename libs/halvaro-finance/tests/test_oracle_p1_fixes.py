"""Oracles of lane P1 for halvaro-finance: the bridge identity check of exposure_bridge and the rules that the docstring of einvoice_gap states. Numbers are written by hand."""
import datetime as dt

import pandas as pd
import pytest

import halvaro.finance as fin
from halvaro.core import Context, FrameError, fact

M12 = Context(stage="month12", role="r")
M3 = Context(stage="month3", role="analyst")


def _open(rows):
    return pd.DataFrame(rows, columns=["prj_key", "exposure_po_dkk", "exposure_reserved_dkk", "exposure_dkk"])


def _fin(rows):
    return pd.DataFrame(rows, columns=["prj_key", "price_exposure_dkk"])


def test_exposure_bridge_oracle_an_inconsistent_open_result_is_refused_never_bridged_silently():
    """halvaro.finance.exposure.exposure_bridge: when exposure_dkk of the open result differs from exposure_po_dkk + exposure_reserved_dkk by more than half a cent the identity difference =
    received_or_timing - reserved cannot hold, so the bridge raises FrameError naming the count and the first project; a total of 15.004 against parts that sum to 15.0 (0.4 cent) passes, one of 0.6 cent does not, whether the total is above or below the parts."""
    bad = _open([("P1", 100.0, 40.0, 140.0), ("P2", 10.0, 5.0, 20.0), ("P3", 1.0, 1.0, 5.0)])
    with pytest.raises(FrameError, match=r"inconsistent.* 2 project\(s\), for example P2"):
        fin.exposure_bridge(bad, _fin([("P1", 150.0)]), context=M12)
    ok = _open([("P1", 0.1, 0.2, 0.3), ("P2", 10.0, 5.0, 15.004)])
    out = fin.exposure_bridge(ok, _fin([("P1", 0.3)]), context=M12).set_index("prj_key")
    assert out.loc["P2", "open_dkk"] == 15.004, "within half a cent of the sum of the parts"
    for total in (15.006, 14.994):
        with pytest.raises(FrameError, match="inconsistent"):
            fin.exposure_bridge(_open([("P2", 10.0, 5.0, total)]), _fin([]), context=M12)
    rows = list(fin.exposure_bridge(_open([("P1", 100.25, 40.5, 140.75)]), _fin([("P1", 150.0)]), context=M12).itertuples())
    assert len(rows) == 1
    r = rows[0]
    assert round(r.difference * 100) == round(r.received_or_timing_dkk * 100) - round(r.reserved_dkk * 100), "the identity of the docstring on a consistent result"


def _inv(rows):
    return pd.DataFrame(rows, columns=["le_key", "cus_key", "invoice_date", "invoice_format", "counterpart_le_key", "inv_key"])


def test_einvoice_gap_oracle_the_window_is_rolling_with_the_day_clipped_and_ties_follow_inv_key():
    """halvaro.finance.vat_tax.einvoice_gap: the window holds the invoices after as_of less `months` months (31 March less one month is 28 February, so 28 February is out and 1 March is in) up to as_of;
    of two invoices of one day the greater inv_key is the last one, whatever the row order; an invoice after the window end is not read."""
    rows = [("LE-02", "CUS-1", "2025-02-28", "pdf", None, "I-0"), ("LE-02", "CUS-2", "2025-03-01", "pdf", None, "I-1"), ("LE-02", "CUS-3", "2025-03-31", "xrechnung", None, "I-2"),
            ("LE-02", "CUS-4", "2025-04-01", "pdf", None, "I-3")]
    got = fin.einvoice_gap(_inv(rows), dt.date(2025, 3, 31), months=1, context=M3).value
    assert got["cus_key"].tolist() == ["CUS-2"], "28 February is before the window, 31 March has no pdf, 1 April is after as_of"
    tie = [("LE-02", "CUS-1", "2025-03-10", "pdf", None, "I-1"), ("LE-02", "CUS-1", "2025-03-10", "xrechnung", None, "I-2")]
    for order in (tie, tie[::-1]):
        r = fin.einvoice_gap(_inv(order), dt.date(2025, 3, 31), months=1, context=M3).value.iloc[0]
        assert (r["n_pdf"], r["n_invoices"], r["last_format"]) == (1, 2, "xrechnung"), "the greater inv_key decides"


def test_einvoice_gap_oracle_the_pdf_allowance_fact_is_carried_but_does_not_bound_the_list():
    """halvaro.finance.vat_tax.einvoice_gap: both facts are in the envelope with their status, and a pdf invoice dated more than a year after fin.e_invoicing.DE.pdf_allowed_until is still listed, so the
    fact does not bound the window or the list."""
    allowed = pd.Timestamp(fact("fin.e_invoicing.DE.pdf_allowed_until").value)
    as_of = (allowed + pd.Timedelta(days=400)).date()
    inv = _inv([("LE-02", "CUS-1", (as_of - dt.timedelta(days=10)).isoformat(), "pdf", None, "I-1")])
    env = fin.einvoice_gap(inv, as_of, months=1, context=M3)
    assert env.value["cus_key"].tolist() == ["CUS-1"]
    assert "VERIFY" in str(env.status) and len(env.facts_used) == 2


def test_einvoice_gap_oracle_a_pdf_invoice_dated_on_as_of_is_in_the_window():
    """halvaro.finance.vat_tax.einvoice_gap: the window runs up to and including as_of, so a pdf invoice dated 31 March with as_of 31 March lists its customer with the date of that invoice as last_invoice_date, and
    an invoice dated 1 April does not."""
    rows = [("LE-02", "CUS-5", "2025-03-31", "pdf", None, "I-4"), ("LE-02", "CUS-6", "2025-04-01", "pdf", None, "I-5")]
    got = fin.einvoice_gap(_inv(rows), dt.date(2025, 3, 31), months=1, context=M3).value
    assert got["cus_key"].tolist() == ["CUS-5"] and got["last_invoice_date"].tolist() == [dt.date(2025, 3, 31)] and got["n_pdf"].tolist() == [1]


def test_einvoice_gap_oracle_without_inv_key_the_last_row_of_a_day_is_the_last_invoice():
    """halvaro.finance.vat_tax.einvoice_gap: a frame without inv_key orders the invoices of one day by position: of two invoices of 10 March the second row is the last one (xrechnung), in both row orders. By hand."""
    base = [("LE-02", "CUS-1", "2025-03-10", "pdf", None), ("LE-02", "CUS-1", "2025-03-10", "xrechnung", None)]
    for order, last in ((base, "xrechnung"), (base[::-1], "pdf")):
        frame = pd.DataFrame(order, columns=["le_key", "cus_key", "invoice_date", "invoice_format", "counterpart_le_key"])
        r = fin.einvoice_gap(frame, dt.date(2025, 3, 31), months=1, context=M3).value.iloc[0]
        assert (r["n_pdf"], r["n_invoices"], r["last_format"]) == (1, 2, last)
