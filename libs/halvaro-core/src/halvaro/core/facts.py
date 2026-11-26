"""Facts: values from config and authored decisions with their status, resolved from the snapshot."""
from __future__ import annotations

import dataclasses
import datetime as dt
import difflib
from typing import Any, Iterable

from . import snapshot
from .errors import FactNotFound
from .registry import function


@dataclasses.dataclass(frozen=True)
class Fact:
    id: str
    value: Any
    status: str          # verified, VERIFY, synthetic or proposed (an authored policy decision the owner has not made yet)
    file: str


@function(sources=(), oracle="py:../libs/halvaro-core/tests/test_oracle_status_banner.py::test_combine_status_oracle_every_subset_of_the_statuses_and_every_order")
def combine_status(statuses: Iterable[str]) -> str:
    """Use this when a result rests on several facts and needs one status for its envelope.

    Rule: VERIFY beats verified, synthetic is kept next to it, and both are reported. A proposed fact counts as VERIFY because the owner has not decided it. Without any fact the status is ok.

    Args:
        statuses: The statuses of the facts the result used (verified, VERIFY, synthetic or proposed).

    Returns:
        str: "ok", "synthetic", "VERIFY" or "VERIFY+synthetic".

    Raises:
        Nothing is raised: a text that is none of the four statuses is ignored.

    Example:
        >>> from halvaro.core import combine_status
        >>> combine_status(["verified", "VERIFY"]), combine_status([]), combine_status(["proposed", "synthetic"])
        ('VERIFY', 'ok', 'VERIFY+synthetic')
    """
    s = set(statuses)
    verify, synth = "VERIFY" in s or "proposed" in s, "synthetic" in s
    return "VERIFY+synthetic" if verify and synth else "VERIFY" if verify else "synthetic" if synth else "ok"


@function(sources=(), oracle="py:../libs/halvaro-core/repo_tests/test_oracle_older_keys_access_facts.py::test_fact_oracle_every_authored_fact_has_the_value_and_status_of_its_yaml_entry")
def fact(fact_id: str) -> Fact:
    """Use this when you need the value, the status and the source file of a fact by its id, for example a rate or a legal parameter that a function reads.

    Rule: the fact comes from the snapshot of the config files and the authored decisions. Its status (verified, VERIFY, synthetic or proposed) travels with the value, and the caller reports it. A fact that holds a date is returned as a datetime.date.

    Args:
        fact_id: The id of the fact, for example "world.fx_eur_dkk_fixed".

    Returns:
        Fact: id, value, status (verified, VERIFY, synthetic or proposed) and file of the fact.

    Raises:
        FactNotFound: the id is unknown. The message names up to three close ids.

    Example:
        >>> from halvaro.core import fact
        >>> f = fact("world.fx_eur_dkk_fixed")
        >>> f.id, f.status in ("verified", "VERIFY", "synthetic", "proposed")
        ('world.fx_eur_dkk_fixed', True)
    """
    facts = snapshot.load()["facts"]
    f = facts.get(fact_id)
    if f is None:
        near = difflib.get_close_matches(fact_id, facts, n=3)
        raise FactNotFound(f"unknown fact {fact_id}" + (f"; did you mean {', '.join(near)}?" if near else ""))
    value = dt.date.fromisoformat(f["value"]) if f.get("date") else f["value"]
    return Fact(fact_id, value, f["status"], f["file"])


@function(sources=(), oracle="py:../libs/halvaro-core/repo_tests/test_oracle_facts_repo.py::test_cfg_oracle_every_scalar_of_every_fact_file_equals_the_yaml_value")
def cfg(file: str, path: str) -> Fact:
    """Use this when you know the config file and the key path of a value but not its fact id.

    Rule: the file is mapped to the prefix of its facts and the call is the same as fact(prefix + "." + path).

    Args:
        file: The config file as the snapshot names it, for example "config/world.yaml".
        path: The key path inside the file, for example "fx_eur_dkk_fixed".

    Returns:
        Fact: the fact at that path (id, value, status and file).

    Raises:
        FactNotFound: the file is not a fact file (the message lists the known files), or no fact has that path.

    Example:
        >>> from halvaro.core import cfg
        >>> cfg("config/world.yaml", "fx_eur_dkk_fixed").id
        'world.fx_eur_dkk_fixed'
    """
    for prefix, rel in snapshot.load()["fact_files"].items():
        if rel == file:
            return fact(f"{prefix}.{path}")
    raise FactNotFound(f"{file} is not a fact file; known: {', '.join(sorted(snapshot.load()['fact_files'].values()))}")


# combine_status is registered (U2, plan 5.5) and re-exported by halvaro.core.
