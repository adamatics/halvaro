"""The structured share counts invoices, not credit notes, when the frame says which is which."""
import pandas as pd
import pytest

import halvaro.finance as fin
from halvaro.core import Context, FrameError

M12 = Context(stage="month12", role="r")


def _ci(rows):
    return pd.DataFrame(rows, columns=["le_key", "invoice_date", "invoice_format", "counterpart_le_key", "invoice_type"])


def test_credit_notes_count_by_default_and_can_be_left_out():
    ci = _ci([("LE-02", "2026-10-03", "xrechnung", None, "invoice"), ("LE-02", "2026-10-09", "pdf", None, "invoice"), ("LE-02", "2026-10-20", "pdf", None, "credit_note")])
    s = fin.einvoice_format_share(ci, invoice_types=("invoice",), context=M12).set_index("period")
    assert s.loc["2026-10", "n_invoices"] == 2 and s.loc["2026-10", "share"] == 0.5
    both = fin.einvoice_format_share(ci, context=M12).set_index("period")
    assert both.loc["2026-10", "n_invoices"] == 3 and both.loc["2026-10", "share"] == 0.3333


def test_a_frame_without_invoice_type_counts_every_row_and_a_text_for_the_types_is_refused():
    ci = _ci([("LE-02", "2026-10-03", "xrechnung", None, "invoice")]).drop(columns="invoice_type")
    assert fin.einvoice_format_share(ci, context=M12).n_invoices.tolist() == [1]
    with pytest.raises(FrameError, match="tuples"):
        fin.einvoice_format_share(_ci([("LE-02", "2026-10-03", "pdf", None, "invoice")]), invoice_types="invoice", context=M12)
