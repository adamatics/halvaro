"""Parameters of the delivery rules that live in config files outside the core facts (plan 4.3). Read from the generated params.json on first use."""
from __future__ import annotations

import copy
import dataclasses
import functools
import json
from importlib import resources
from typing import Any

from halvaro.core import FactNotFound


@dataclasses.dataclass(frozen=True)
class Param:
    id: str            # file#path, for example procurement.yaml#stock.cover_weeks_min
    value: Any         # dates are ISO strings
    status: str        # verified, VERIFY or synthetic, as the plan table says
    file: str

    @property
    def fact_status(self) -> str:
        """The status in the vocabulary of core's combine_status: verified is ok."""
        return "ok" if self.status == "verified" else self.status


@functools.lru_cache(maxsize=None)
def _load() -> dict[str, Any]:
    out: dict[str, Any] = json.loads(resources.files("halvaro.delivery").joinpath("_data/params.json").read_text(encoding="utf-8"))
    return out


def params_hash() -> str:
    """Use this when you need to record which copy of the generator parameters a result was computed with.

    The hash is the sha256 of the parameter document without its own `hash` field, as compact JSON with sorted keys; tools/build_params.py computes it and stores it in `_data/params.json`. Hashing the shipped file itself does not give it.

    Args:
        (none)

    Returns:
        The hash as 64 hexadecimal characters.

    Raises:
        Nothing for a package that was built with its data file.

    Example:
        >>> from halvaro.delivery import params_hash
        >>> len(params_hash()), all(c in "0123456789abcdef" for c in params_hash())
        (64, True)
    """
    return str(_load()["hash"])


def param(param_id: str) -> Param:
    """Use this when a rule of this library needs a value of the generator configuration that has no fact id, such as the cover weeks of the stock rule.

    The parameters are the plan table of the library: a copy of the generator configuration, shipped in `_data/params.json` with the status the plan gives each value (verified,
    VERIFY or synthetic). The value is a copy, so a caller cannot change the cached file. Prefer a fact (`halvaro.core.fact`) when one exists.

    Args:
        param_id: The id `file#path`, for example 'procurement.yaml#stock.cover_weeks_min'.

    Returns:
        A Param with id, value (dates as ISO text), status and file; `fact_status` gives the status in the vocabulary of core's combine_status.

    Raises:
        FactNotFound: the id is not a parameter of the file; the message lists the first known ids.

    Example:
        >>> from halvaro.delivery import param
        >>> p = param("procurement.yaml#stock.cover_weeks_min")
        >>> p.file, p.status in ("verified", "VERIFY", "synthetic")
        ('config/procurement.yaml', True)
    """
    p = _load()["params"].get(param_id)
    if p is None:
        raise FactNotFound(f"unknown parameter {param_id}; known: {', '.join(sorted(_load()['params'])[:6])} ...")
    return Param(param_id, copy.deepcopy(p["value"]), p["status"], p["file"])      # a copy: the cached file content is never handed out to be changed


def all_param_ids() -> list[str]:
    """Use this when you need the ids of every generator parameter the library ships, for example to check that an id you pass to `param` exists.

    The ids are the keys of `_data/params.json`, in the form `file#path`, sorted.

    Args:
        (none)

    Returns:
        The sorted list of parameter ids.

    Raises:
        Nothing for a package that was built with its data file.

    Example:
        >>> from halvaro.delivery import all_param_ids
        >>> ids = all_param_ids()
        >>> "procurement.yaml#stock.cover_weeks_min" in ids, ids == sorted(ids)
        (True, True)
    """
    return sorted(_load()["params"])
