"""HF-03: finance.recoverable reads only the contracts it is given and takes the price clause in force on the invoice date (library-plans/halvaro-finance.md 5.4)."""
import numpy as np
import pandas as pd
import pytest

import halvaro.finance as fin
from halvaro.core import Context, FrameError

M12 = Context(stage="month12", role="r")


def _terms_two_rows():
    return pd.DataFrame({"con_key": ["C1", "C1", "C9", "C9", "C2"], "pass_through_percent": [50.0, 80.0, 10.0, 20.0, 70.0], "threshold_percent": [np.nan] * 5,
                         "valid_from": pd.to_datetime(["2022-01-01", "2026-04-01", "2022-01-01", "2022-01-01", "2022-01-01"]), "valid_to": pd.to_datetime([pd.NaT, pd.NaT, pd.NaT, pd.NaT, pd.NaT])})


def test_recoverable_reads_only_the_contracts_it_is_given_and_takes_the_clause_in_force():
    """HF-03: a contract with two clause rows elsewhere in the book is no error; one used contract with two rows needs the date and takes one clause, never both."""
    exp = pd.DataFrame({"prj_key": ["P1", "P2"], "exposure_dkk": [1000.0, 2000.0], "step_percent_max": [18.0, 18.0]})
    con = pd.DataFrame({"prj_key": ["P1", "P2"], "con_key": ["C2", "C1"], "price_type": ["indexed", "indexed"]})
    one = fin.recoverable(exp.iloc[:1], _terms_two_rows(), con.iloc[:1], context=M12)
    assert one.recoverable_dkk.tolist() == [700.0], "C9 has two rows and is not used: no refusal"
    with pytest.raises(FrameError, match="pass on="):
        fin.recoverable(exp, _terms_two_rows(), con, context=M12)
    after = fin.recoverable(exp, _terms_two_rows(), con, on="2026-06-01", context=M12).set_index("prj_key")
    before = fin.recoverable(exp, _terms_two_rows(), con, on="2025-06-01", context=M12).set_index("prj_key")
    assert after.loc["P2", "recoverable_dkk"] == 1600.0 and before.loc["P2", "recoverable_dkk"] == 1000.0, "the latest clause in force on the date: 80 percent after 2026-04-01 and 50 before"
    assert after.recoverable_dkk.sum() == 700.0 + 1600.0, "one clause per contract: nothing is counted twice"


def test_recoverable_refuses_two_clauses_with_the_same_start_or_none_in_force():
    exp = pd.DataFrame({"prj_key": ["P9"], "exposure_dkk": [1000.0], "step_percent_max": [18.0]})
    con = pd.DataFrame({"prj_key": ["P9"], "con_key": ["C9"], "price_type": ["indexed"]})
    with pytest.raises(FrameError, match="same date"):
        fin.recoverable(exp, _terms_two_rows(), con, on="2026-06-01", context=M12)
    with pytest.raises(FrameError, match="no price clause is in force"):
        fin.recoverable(exp, _terms_two_rows().assign(valid_from=pd.Timestamp("2030-01-01")), con, on="2026-06-01", context=M12)


def test_recoverable_reads_a_single_clause_on_the_date_and_refuses_bad_dates():
    exp = pd.DataFrame({"prj_key": ["P2"], "exposure_dkk": [1000.0], "step_percent_max": [18.0]})
    con = pd.DataFrame({"prj_key": ["P2"], "con_key": ["C2"], "price_type": ["indexed"]})
    t = _terms_two_rows()
    assert fin.recoverable(exp, t, con, on="2026-06-01", context=M12).recoverable_dkk.tolist() == [700.0]
    expired = t.assign(valid_to=pd.to_datetime([pd.NaT, pd.NaT, pd.NaT, pd.NaT, "2024-12-31"]))
    with pytest.raises(FrameError, match="no price clause is in force"):
        fin.recoverable(exp, expired, con, on="2026-06-01", context=M12)
    with pytest.raises(FrameError, match="time zone"):
        fin.recoverable(exp, t, con, on=pd.Timestamp("2026-06-01", tz="UTC"), context=M12)
    with pytest.raises(FrameError, match="valid_to before valid_from"):
        fin.recoverable(exp, t.assign(valid_to=pd.to_datetime([pd.NaT] * 4 + ["2021-01-01"])), con, on="2026-06-01", context=M12)
    with pytest.raises(FrameError, match="no valid_from"):
        fin.recoverable(exp, t.assign(valid_from=pd.to_datetime(["2022-01-01"] * 4 + [pd.NaT])), con, on="2026-06-01", context=M12)
    # without on, a single clause is read as it is
    assert fin.recoverable(exp, t, con, context=M12).recoverable_dkk.tolist() == [700.0]


def test_recoverable_names_the_missing_date_columns():
    exp = pd.DataFrame({"prj_key": ["P1"], "exposure_dkk": [1000.0], "step_percent_max": [18.0]})
    con = pd.DataFrame({"prj_key": ["P1"], "con_key": ["C1"], "price_type": ["indexed"]})
    with pytest.raises(FrameError, match="valid_from and valid_to"):
        fin.recoverable(exp, _terms_two_rows().drop(columns=["valid_from", "valid_to"]), con, on="2026-06-01", context=M12)
