"""Oracle of lane P1 for halvaro-delivery: contingency_advice reads the fact policy.delivery.contingency_method (value for the method text, status for the first caveat). Numbers are by hand."""
from collections import namedtuple

import pandas as pd

import halvaro.delivery as delivery
import halvaro.delivery.estimating as estimating
from halvaro.core import Context, fact

CTX = Context(stage="month12", role="r")
OD = pd.DataFrame({"measure": ["schedule"], "n": [10], "n_legacy": [4], "q25": [0.05], "median": [0.1], "q75": [0.2]})
CS = pd.DataFrame({"view": ["all_events"] * 3, "cause_code": ["ground_conditions", "ground_conditions", "weather"], "days": [10, 20, 70], "responsible_party": ["a", "b", "c"]})
LN = pd.DataFrame({"prj_key": ["P1", "P1"], "type": ["tender"] * 2, "cst_key": ["CST-100", "CST-830"], "amount": [950.0, 50.0]})
Fake = namedtuple("Fake", "value status")


def test_contingency_advice_oracle_the_method_text_and_the_status_come_from_the_fact(monkeypatch):
    """halvaro.delivery.estimating.contingency_advice: the method of the result is the value of policy.delivery.contingency_method and the first caveat names its status; with the fact replaced by a
    stand in (a different text, status decided) both change, and the numbers of the advice do not."""
    real = fact("policy.delivery.contingency_method")
    a = delivery.contingency_advice(OD, CS, LN, context=CTX)
    assert a.method == real.value and f"is {real.status} and" in a.caveats[0]
    monkeypatch.setattr(estimating, "fact", lambda fid: Fake("a test method text", "decided") if fid == "policy.delivery.contingency_method" else fact(fid))
    b = delivery.contingency_advice(OD, CS, LN, context=CTX)
    assert b.method == "a test method text" and "is decided and" in b.caveats[0]
    pd.testing.assert_frame_equal(a.rows, b.rows)
