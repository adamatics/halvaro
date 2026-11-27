"""CFO scenarios lane (issue #668): intercompany_agreement refuses a tolerance that is negative, not a number or not finite, as its docstring says (Raises: FrameError). Before this change a negative
tolerance was accepted and every document that differed by any amount was listed, or none was, without a message."""
import numpy as np
import pandas as pd
import pytest

import halvaro.finance as fin
from halvaro.core import Context, FrameError

M12 = Context(stage="month12", role="analyst")
IC = pd.DataFrame({"ic_type": ["recharge"], "document_date": ["2025-01-31"], "creditor_amount": [100.0], "creditor_currency": ["DKK"], "debtor_amount": [100.0], "currency": ["DKK"],
                   "difference_dkk": [0.0], "matched": [True]})
ICB = pd.DataFrame({"period": ["2025-01"], "creditor_le_key": ["LE-01"], "debtor_le_key": ["LE-02"], "balance_type": ["trade"], "creditor_balance": [100.0], "creditor_currency": ["DKK"],
                    "debtor_balance": [100.0], "debtor_currency": ["DKK"], "difference_dkk": [0.0], "agrees": [True]})


@pytest.mark.parametrize("bad", [-1, -0.01, float("nan"), float("inf"), True, "1"])
def test_a_tolerance_that_is_negative_not_finite_or_not_a_number_is_refused(bad):
    with pytest.raises(FrameError, match="tolerance_dkk must be zero or more"):
        fin.intercompany_agreement(IC, ICB, tolerance_dkk=bad, context=M12)


@pytest.mark.parametrize("ok", [0, 0.0, 1, 1.0, np.float64(0.5), np.int64(2)])
def test_zero_and_positive_tolerances_give_the_result_they_gave_before(ok):
    assert fin.intercompany_agreement(IC, ICB, tolerance_dkk=ok, context=M12).value.empty
