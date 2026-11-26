"""Oracle of halvaro.core.facts.cfg (lane L1): the config files are read with yaml, the library reads them through the snapshot."""

import pytest

import halvaro.core as core

FILES = {"fin": "config/finance-parameters.provisional.yaml", "frep": "config/finance-reporting-parameters.provisional.yaml", "legal": "config/legal-parameters.provisional.yaml",
         "qual": "config/qualification-parameters.provisional.yaml", "world": "config/world.yaml"}


def test_cfg_oracle_refusals_name_the_problem():
    """halvaro.core.facts.cfg: a file that is not a fact file, a path that is not in the file and an empty file name raise FactNotFound; the first one lists the fact files."""
    with pytest.raises(core.FactNotFound, match="not a fact file") as e:
        core.cfg("config/gis.yaml", "anything")
    assert all(rel in str(e.value) for rel in FILES.values())
    with pytest.raises(core.FactNotFound):
        core.cfg("config/world.yaml", "no.such.path")
    with pytest.raises(core.FactNotFound):
        core.cfg("", "fx_eur_dkk_fixed")
