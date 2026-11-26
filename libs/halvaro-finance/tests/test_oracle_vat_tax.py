"""Oracle tests of vat_tax.einvoice_gap: hand worked invoices around the window edges, the two facts read through their ids, and the baseline invoices filtered with plain loops."""
import datetime as dt

import pandas as pd
import pytest

import halvaro.finance as fin
from halvaro.core import Context, FrameError, PeriodError, fact

M3 = Context(stage="month3", role="r")
MAND, ALLOWED = "fin.e_invoicing.DE.mandatory_issue_from", "fin.e_invoicing.DE.pdf_allowed_until"
COLS = ["cus_key", "n_pdf", "n_invoices", "last_invoice_date", "last_format", "days_to_mandatory"]


def _facts():
    mand, allowed = fact(MAND), fact(ALLOWED)
    return mand, allowed, f"{MAND} read as {mand.value} ({mand.status}), {ALLOWED} read as {allowed.value} ({allowed.status})"


def _inv(rows):
    """rows: (inv_key, le_key, cus_key, invoice_date, invoice_format, counterpart_le_key)."""
    return pd.DataFrame(rows, columns=["inv_key", "le_key", "cus_key", "invoice_date", "invoice_format", "counterpart_le_key"])


def test_oracle_einvoice_gap_hand_window_edges_ordering_and_the_two_facts():
    """route: hand worked invoices around the window edges (a window of three months ending 2026-11-30), the listed customers and counts written out by hand, the days from the fact date."""
    mand, allowed, msg = _facts()
    inv = _inv([
        ("I01", "LE-02", "C1", "2026-08-30", "pdf", None), ("I02", "LE-02", "C1", "2026-08-31", "pdf", None), ("I03", "LE-02", "C1", "2026-11-30", "xrechnung", None),
        ("I04", "LE-02", "C2", "2026-12-01", "pdf", None),
        ("I06", "LE-02", "C3", "2026-10-15", "zugferd", None), ("I05", "LE-02", "C3", "2026-10-15", "pdf", None), ("I07", "LE-02", "C3", "2026-09-01", "pdf", None),
        ("I08", "LE-02", "C4", "2026-11-01", "xrechnung", None), ("I09", "LE-02", "C4", "2026-11-02", "peppol_bis", None),
        ("I10", "LE-01", "C5", "2026-11-01", "pdf", None),
        ("I11", "LE-02", None, "2026-11-01", "pdf", "LE-01"),
        ("I12", "LE-02", "C6", "2026-11-03", "pdf", "LE-01"),
        ("I13", "LE-02", "C7", "2026-09-10", "pdf", None), ("I14", "LE-02", "C7", "2026-10-10", "pdf", None), ("I15", "LE-02", "C7", "2026-11-10", "pdf", None),
        ("I16", "LE-02", "C8", "2026-11-01", "pdf", None),
    ])
    kept = inv.copy(deep=True)
    r = fin.einvoice_gap(inv, dt.date(2026, 11, 30), months=3, context=M3)
    v = r.value
    assert list(v.columns) == COLS
    assert v[COLS[:5]].values.tolist() == [
        ["C7", 3, 3, dt.date(2026, 11, 10), "pdf"],
        ["C3", 2, 3, dt.date(2026, 10, 15), "zugferd"],
        ["C1", 1, 2, dt.date(2026, 11, 30), "xrechnung"],
        ["C8", 1, 1, dt.date(2026, 11, 1), "pdf"],
    ], f"C1: the invoice of 2026-08-30 is outside, 2026-08-31 and the day of as_of inside; C2 is after as_of; C3: two on one day, the later key is the last; C4 has no pdf; C5 is the other entity; C6 and the null customer are intercompany; {msg}"
    assert v.days_to_mandatory.tolist() == [(mand.value - dt.date(2026, 11, 30)).days] * 4, msg
    assert r.facts_used == ((MAND, mand.value, mand.status), (ALLOWED, allowed.value, allowed.status)), msg
    assert r.status == ("VERIFY" if "VERIFY" in (mand.status, allowed.status) else "ok"), msg
    assert [type(x) for x in v.last_invoice_date] == [dt.date] * 4 and v.n_pdf.dtype.kind == "i" and v.n_invoices.dtype.kind == "i"
    pd.testing.assert_frame_equal(inv, kept)
    other = fin.einvoice_gap(inv, "2026-11-30", months=3, le_key="LE-01", context=M3).value
    assert other[COLS[:5]].values.tolist() == [["C5", 1, 1, dt.date(2026, 11, 1), "pdf"]], "the entity is a parameter"


def test_oracle_einvoice_gap_hand_month_lengths_clipping_and_year_boundary():
    """route: hand invoices on the day before and the day after the lower edge of the window for a month end, a leap day and a window of twelve months."""
    inv = _inv([
        ("A1", "LE-02", "X", "2025-02-28", "pdf", None), ("A2", "LE-02", "Y", "2025-03-01", "pdf", None),
        ("B1", "LE-02", "Z", "2024-02-29", "pdf", None), ("B2", "LE-02", "W", "2024-03-01", "pdf", None),
        ("C1", "LE-02", "U", "2024-01-31", "pdf", None), ("C2", "LE-02", "V", "2024-02-01", "pdf", None),
    ])
    mar = fin.einvoice_gap(inv, dt.date(2025, 3, 31), months=1, context=M3).value
    assert mar.cus_key.tolist() == ["Y"], "one month ending 2025-03-31 starts after 2025-02-28"
    leap = fin.einvoice_gap(inv, dt.date(2024, 3, 31), months=1, context=M3).value
    assert leap.cus_key.tolist() == ["W"], "one month ending 2024-03-31 starts after 2024-02-29"
    year = fin.einvoice_gap(inv, dt.date(2025, 1, 31), months=12, context=M3).value
    assert year.cus_key.tolist() == ["V", "W", "Z"], "twelve months ending 2025-01-31 start after 2024-01-31: U is outside, V, Z and W inside"


def test_oracle_einvoice_gap_hand_empty_window_and_refusals():
    """route: hand frames: a window without a pdf gives no rows but the columns, a months value that is not a whole number of one or more is refused, a date that is not a date is refused."""
    inv = _inv([("A1", "LE-02", "X", "2025-03-01", "xrechnung", None), ("A2", "LE-02", "Y", "2024-01-01", "pdf", None)])
    empty = fin.einvoice_gap(inv, dt.date(2025, 3, 31), months=1, context=M3).value
    assert empty.empty and list(empty.columns) == COLS
    for bad in (0, -1, 1.5, True, "6", None):
        with pytest.raises(FrameError, match="months"):
            fin.einvoice_gap(inv, dt.date(2025, 3, 31), months=bad, context=M3)
    for bad in (20250331, 2025.5, "not a date"):
        with pytest.raises(PeriodError):
            fin.einvoice_gap(inv, bad, context=M3)
    with pytest.raises(FrameError, match="lacks column"):
        fin.einvoice_gap(inv.drop(columns="counterpart_le_key"), dt.date(2025, 3, 31), context=M3)
