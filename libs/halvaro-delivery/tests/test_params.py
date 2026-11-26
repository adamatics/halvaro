"""The parameter file: every id resolves, status values, the hash of the content."""
import json
from pathlib import Path

import pytest

from halvaro.core import FactNotFound
from halvaro.delivery import params
from halvaro.delivery.params import Param, param

LIB = Path(__file__).resolve().parents[1]


def test_every_listed_id_resolves_and_carries_a_known_status():
    ids = params.all_param_ids()
    assert len(ids) == 26 and ids == sorted(ids)
    for pid in ids:
        p = param(pid)
        assert isinstance(p, Param) and p.id == pid and p.status in ("verified", "VERIFY", "synthetic") and p.file == "config/" + pid.split("#")[0]


def test_known_values_and_the_status_of_the_plan_table():
    assert param("procurement.yaml#critical_supply.lead_time_weeks").value == [16, 30] and param("procurement.yaml#critical_supply.lead_time_weeks").status == "verified"
    assert param("procurement.yaml#price_step.effective_from").value == "2026-04-01"
    assert param("inventory.yaml#critical_supply.zero_by").value == "2026-10-31"
    assert param("contracts.yaml#notification").status == "VERIFY"
    assert param("procurement.yaml#stock.cover_weeks_min").status == "synthetic"


def test_unknown_parameter_raises_fact_not_found_naming_known_ids():
    with pytest.raises(FactNotFound, match="unknown parameter nope.yaml#x"):
        param("nope.yaml#x")


def test_hash_is_the_hash_of_the_file_content():
    import hashlib

    doc = json.loads((LIB / "src/halvaro/delivery/_data/params.json").read_text())
    h = doc.pop("hash")
    assert params.params_hash() == h == hashlib.sha256(json.dumps(doc, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def test_the_file_is_marked_proposed_and_hashes_the_config_files():
    doc = json.loads((LIB / "src/halvaro/delivery/_data/params.json").read_text())
    assert "proposed" in doc and set(doc["files"]) >= {"config/procurement.yaml", "config/inventory.yaml", "config/contracts.yaml", "config/crm.yaml", "config/energy_esg.yaml"}


PLAN_STATUS = {
    "procurement.yaml#price_step.sup_key": "verified", "procurement.yaml#price_step.effective_from": "verified", "procurement.yaml#price_step.percent": "verified",
    "procurement.yaml#critical_supply.items": "verified", "procurement.yaml#critical_supply.min_qty": "verified", "procurement.yaml#critical_supply.max_qty": "verified", "procurement.yaml#critical_supply.slip_from": "verified", "procurement.yaml#critical_supply.lead_time_weeks": "verified",
    "procurement.yaml#stock.cover_weeks_min": "synthetic", "procurement.yaml#stock.cover_weeks_order": "synthetic", "procurement.yaml#stock.event_cover": "synthetic",
    "procurement.yaml#stock.project_end_grace_days": "synthetic",
    "inventory.yaml#critical_supply.blocked_need_horizon_days": "verified", "inventory.yaml#critical_supply.thin_cover": "verified", "inventory.yaml#critical_supply.site": "verified", "inventory.yaml#critical_supply.zero_by": "verified",
    "contracts.yaml#notification": "VERIFY", "contracts.yaml#nordvolt_framework": "verified", "contracts.yaml#kalmarsund_framework": "verified", "contracts.yaml#qualification_requirements": "verified",
    "contracts.yaml#qualification_keys": "verified", "contracts.yaml#project.pass_through_percent": "verified", "contracts.yaml#project.threshold_percent": "verified",
    "crm.yaml#story_tenders.fjordvarme_carbon": "synthetic", "crm.yaml#story_tenders.elbtal_tender": "verified", "energy_esg.yaml#calibration.comparable": "verified",
}


def test_every_status_is_the_one_of_the_plan_table_and_maps_to_core_statuses():
    assert {i: param(i).status for i in params.all_param_ids()} == PLAN_STATUS
    from halvaro.core import combine_status

    assert combine_status(param(i).fact_status for i in PLAN_STATUS) == "VERIFY+synthetic"
    assert param("procurement.yaml#critical_supply.items").fact_status == "ok" and param("contracts.yaml#notification").fact_status == "VERIFY"


def test_param_is_frozen_and_unknown_error_names_known_ids():
    import dataclasses

    with pytest.raises(dataclasses.FrozenInstanceError):
        param("procurement.yaml#critical_supply.items").value = 1
    with pytest.raises(FactNotFound, match="known: contracts.yaml#kalmarsund_framework"):
        param("nope")


def test_a_value_is_a_copy_the_cached_file_cannot_be_changed_through_it():
    first = param("procurement.yaml#critical_supply.lead_time_weeks")
    first.value[0] = 99
    assert param("procurement.yaml#critical_supply.lead_time_weeks").value == [16, 30]
    assert param("procurement.yaml#critical_supply.min_qty").value == {"ITM-000001": 8, "ITM-000002": 5} and param("procurement.yaml#critical_supply.max_qty").value == {"ITM-000001": 14, "ITM-000002": 9}
