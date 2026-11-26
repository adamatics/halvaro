"""Reporting basis (plan 5.10): the statement of the basis with its VERIFY flags, size evidence against provisional thresholds, and the provenance of a result computed from other results.

The basis statement never claims that a mandatory EU sustainability reporting standard applies. Thresholds are core facts (VERIFY); the size evidence draws no conclusion.
"""
from __future__ import annotations

import dataclasses
import re
from typing import Any, Mapping, NamedTuple, cast

import pandas as pd

from halvaro.core import Envelope, FrameError, combine_status, fact, make_envelope
from halvaro.core.registry import function

from ._guard import staged
from ._util import Provenance, _need

_CLAIM = re.compile(r"csrd|esrs|omnibus|directive", re.I)                      # the generated statement must never contain these words
_ALLOWED = re.compile(r"voluntary(?P<stat> and national statutory statement)?(?:, no mandatory eu (?:sustainability reporting )?standard assumed)?(?: \(verify\))?")
_COUNTRY = {"LE-01": "DK", "LE-02": "DE"}                                      # PROPOSED: country of the legal entity (hr.legal_entity.country)
_THRESHOLD = {"DK": ("average_full_time_employees", "net_revenue"), "DE": ("average_employees", "net_revenue")}


class BasisStatement(NamedTuple):
    """The statement of the reporting basis: the decision text as given, the framework class (voluntary, voluntary_with_statutory_statement), the statement text, and the VERIFY flags that go with it."""
    decision: str
    framework: str
    statement: str
    verify: tuple[str, ...]


@staged(sources=("energy-esg.esg_data_request.standard",), oracle="py:tests/test_energy_esg.py::test_safety_and_wording")
def reporting_basis(decision: str) -> BasisStatement:
    """Use this when you need the statement of the reporting basis, with its VERIFY flags, from the policy decision text.

    The statement of the basis from the policy decision text (config data_requests.reporting_framework: 'voluntary', or a text such as 'voluntary and national statutory statement, no mandatory EU standard assumed'). Only the classes voluntary and voluntary with a statutory statement are produced; the statement says that no mandatory EU sustainability reporting standard is assumed and that this is to be verified. Only a closed list of wordings is accepted (an allow list, not a scan for claims): any other text, including one that claims or denies that CSRD, ESRS or the Omnibus rules apply, raises FrameError and is never echoed. The library does not decide legal applicability.

    Args:
        decision: The policy decision text; case and spacing are not significant, and ', no mandatory EU standard assumed' and '(VERIFY)' may follow the class.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A BasisStatement with the fields decision (the canonical class text, not the input), framework (voluntary or voluntary_with_statutory_statement), statement (the statement text) and verify (a tuple of VERIFY flags).

    Raises:
        FrameError: decision is not a text or is empty.
        FrameError: decision is not one of the accepted wordings; the text is not echoed.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> from halvaro.core import Context
        >>> from halvaro.esg import reporting_basis
        >>> ctx = Context(stage="month12", role="analyst")
        >>> b = reporting_basis("Voluntary and national statutory statement", context=ctx)
        >>> b.framework
        'voluntary_with_statutory_statement'
        >>> b.decision
        'voluntary and national statutory statement'
        >>> reporting_basis("voluntary", context=ctx).statement.startswith("Voluntary sustainability reporting.")
        True
    """
    if not isinstance(decision, str) or not decision.strip():
        raise FrameError("the decision must be a non-empty text")
    m = _ALLOWED.fullmatch(" ".join(decision.lower().split()))
    if m is None:
        raise FrameError("the decision text is not one of the two accepted wordings ('voluntary' or 'voluntary and national statutory statement', each optionally followed by ', no mandatory EU "
                         "standard assumed (VERIFY)'); other texts are not echoed and no other basis is produced")
    stat = m.group("stat") is not None
    framework = "voluntary_with_statutory_statement" if stat else "voluntary"
    text = ("Voluntary sustainability reporting" + (" with a national statutory statement where the annual report requires one" if stat else "") +
            ". No mandatory EU sustainability reporting standard is assumed. Whether any duty applies is to be verified (VERIFY).")
    assert not _CLAIM.search(text)
    return BasisStatement("voluntary and national statutory statement" if stat else "voluntary", framework, text, ("VERIFY: legal reporting duty and its scope are not established by the data",))


@staged(sources=("finance-reporting.statutory_report.le_key", "finance-reporting.statutory_report.fiscal_year", "finance-reporting.statutory_report.average_employees",
                 "finance-reporting.statutory_report.revenue", "finance-reporting.statutory_report.reporting_class", "finance-reporting.statutory_report.scope"),
        facts=("frep.annual_reports.DK.size_thresholds.net_revenue", "frep.annual_reports.DE.size_thresholds.net_revenue", "frep.annual_reports.DK.size_thresholds.average_full_time_employees",
               "frep.annual_reports.DE.size_thresholds.average_employees"), oracle="py:tests/test_oracle_basis.py::test_oracle_size_evidence_every_route")
def size_evidence(SR: pd.DataFrame, *, country_of: Mapping[str, Any] = _COUNTRY) -> Provenance:
    """Use this when you need the employees and revenue of each legal entity and year set against the provisional size thresholds of its country, as evidence only.

    Employees and revenue of each legal entity and year against the provisional size thresholds of its country (core facts, VERIFY; the revenue is in the currency of the entity). A null employee count or revenue gives a null (unknown) comparison, never false. The balance sheet criterion is not evaluated here (employees and revenue only, as the plan lists). Evidence only: no column says that a duty applies. Group rows (scope other than entity) are left out. The thresholds are read from the core facts, which are listed in the facts used of the result.

    Args:
        SR: The finance-reporting.statutory_report table with the columns le_key, fiscal_year, average_employees, revenue and reporting_class, and scope when group rows are present.
        country_of: Mapping from le_key to the country code of the legal entity (PROPOSED: the default maps the two legal entities of hr.legal_entity.country); only DK and DE have thresholds.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        Provenance whose value is a DataFrame with the columns le_key, fiscal_year, country, average_employees, threshold_employees, exceeds_employees, revenue, threshold_revenue, exceeds_revenue and reporting_class (as stored), sorted by le_key and fiscal_year; the facts used are the thresholds, and a warning says that the evidence is provisional.

    Raises:
        FrameError: SR lacks le_key, fiscal_year, average_employees, revenue or reporting_class.
        FrameError: SR has no entity rows, an entity row has no le_key, or an entity and year has more than one row.
        FrameError: an entity has no country in `country_of`.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.esg import size_evidence
        >>> ctx = Context(stage="month12", role="analyst")
        >>> SR = pd.DataFrame({"le_key": ["LE-900001", "LE-900001"], "fiscal_year": [2024, 2025], "average_employees": [5.0, None],
        ...                    "revenue": [1000.0, 2000.0], "reporting_class": ["small", "small"], "scope": ["entity", "entity"]})
        >>> r = size_evidence(SR, country_of={"LE-900001": "DK"}, context=ctx)
        >>> r.value["country"].tolist()
        ['DK', 'DK']
        >>> r.value["exceeds_revenue"].tolist()
        [False, False]
        >>> bool(r.value["exceeds_employees"].isna().tolist()[1])
        True
    """
    _need(SR, ["le_key", "fiscal_year", "average_employees", "revenue", "reporting_class"], "finance-reporting.statutory_report")
    x = SR[SR["scope"] == "entity"] if "scope" in SR.columns else SR
    if x.empty:
        raise FrameError("finance-reporting.statutory_report has no entity rows (scope 'entity')")
    if x["le_key"].isna().any():
        raise FrameError("an entity row has no le_key")
    if x.duplicated(["le_key", "fiscal_year"]).any():
        raise FrameError("finance-reporting.statutory_report has more than one row for an entity and year")
    miss = sorted(set(x["le_key"]) - set(country_of))
    if miss:
        raise FrameError(f"no country for the entity {miss[0]}")
    facts = {c: (fact(f"frep.annual_reports.{c}.size_thresholds.{e}"), fact(f"frep.annual_reports.{c}.size_thresholds.{r}")) for c, (e, r) in _THRESHOLD.items()}
    rows = []
    r: Any
    for r in x.sort_values(["le_key", "fiscal_year"]).itertuples():
        c = country_of[r.le_key]
        te, tr = (float(facts[c][0].value), float(facts[c][1].value))
        rows.append({"le_key": r.le_key, "fiscal_year": int(r.fiscal_year), "country": c, "average_employees": r.average_employees, "threshold_employees": te, "exceeds_employees": (pd.NA if pd.isna(r.average_employees) else bool(r.average_employees > te)),
                     "revenue": r.revenue, "threshold_revenue": tr, "exceeds_revenue": (pd.NA if pd.isna(r.revenue) else bool(r.revenue > tr)), "reporting_class": r.reporting_class})
    env = make_envelope(pd.DataFrame(rows), "halvaro.esg.basis.size_evidence", facts=[f for pair in facts.values() for f in pair], sources=("finance-reporting.statutory_report",), cls=Provenance,
                        warnings=("evidence only: thresholds are provisional (VERIFY) and no conclusion about a reporting duty is drawn",))
    return cast(Provenance, env)


@function(sources=(), oracle="py:tests/test_oracle_basis.py::test_oracle_provenance_every_route")
def provenance(*results: Envelope) -> Provenance:
    """Use this when you need the provenance of a result computed from other results: their factor sets, VERIFY notes, facts and status joined.

    The Provenance of a result computed from the given results (each a Provenance or a core Envelope): factor sets and VERIFY notes joined, facts used joined, status by the core combine_status, synthetic true if any input is. The value is the number of results; a caller attaches its own value with dataclasses.replace.

    Args:
        results: One or more results, each a Provenance or a core Envelope.

    Returns:
        A Provenance whose value is the number of results, with the sorted factor sets and VERIFY notes, the sources, warnings and facts used of all inputs without repeats, the status combined from the statuses of the inputs, synthetic true if any input is, and the latest as_of of the inputs (none when no input has one).

    Raises:
        FrameError: no result is given.
        FrameError: a result is not an Envelope or a Provenance.

    Example:
        >>> from halvaro.core import make_envelope
        >>> from halvaro.esg import provenance
        >>> a = make_envelope(1, "demo.a", sources=("energy-esg.emission_line",))
        >>> b = make_envelope(2, "demo.b", sources=("energy-esg.emission_line", "energy-esg.target"))
        >>> p = provenance(a, b)
        >>> p.value
        2
        >>> list(p.sources)
        ['energy-esg.emission_line', 'energy-esg.target']
    """
    if not results:
        raise FrameError("provenance needs at least one result")
    for r in results:
        if not isinstance(r, Envelope):
            raise FrameError(f"provenance takes Envelope or Provenance results, not {type(r).__name__}")
    status = combine_status([p for r in results for p in str(r.status).split("+")])
    sets = tuple(sorted({s for r in results for s in getattr(r, "factor_sets", ())}))
    verify = tuple(sorted({s for r in results for s in getattr(r, "verify_facts", ())}))
    as_ofs = {r.as_of for r in results if r.as_of is not None}
    env = make_envelope(len(results), "halvaro.esg.basis.provenance", facts=(), as_of=(max(as_ofs) if as_ofs else None), sources=tuple(dict.fromkeys(s for r in results for s in r.sources)), cls=Provenance,
                        warnings=tuple(dict.fromkeys(w for r in results for w in r.warnings)), factor_sets=sets, verify_facts=verify)
    return cast(Provenance, dataclasses.replace(env, status=status, synthetic=any(bool(r.synthetic) for r in results), facts_used=tuple(dict.fromkeys(f for r in results for f in r.facts_used))))
