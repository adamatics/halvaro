"""Documentation gate of halvaro-finance beyond the functions of the slice (standard 3.1.2, 3.1.3, 3.2.5 and 3.7.4, lane P2, issue #446).

A ratchet (the functions of the slice are also covered by test_slice_docs_quality.py): PASSING lists the functions that meet the gate (a first line "Use this when ...", the sections Args, Returns, Raises and Example, every parameter described and typed, a return type, the
registry summary equal to the first line, an example with a >>> line). The test fails when a listed function stops meeting the gate and when a function meets it without being listed, so the list
can only grow with the work. The examples of every docstring of the library run as doctests. Functions not listed are the open part of item F1 of issue #416."""
import doctest
import importlib
import inspect
import re

import halvaro.finance as core

SECTION = re.compile(r"^(Args|Returns|Raises|Example):\s*$", re.M)

PASSING = (
    "ageing", "approval_limit_breaches", "bad_debt_candidates", "bank_reconciliation", "budget_variance", "cash_forecast_checks", "committed_cost", "contract_position",
    "cost_centre_team_map", "cost_per_metre_by_cost_code", "cost_to_completion", "customer_exposure", "dkk_amount", "einvoice_format_share", "einvoice_gap", "eliminations",
    "employer_oncosts", "exposure_bridge", "filing_status", "finance_exposure", "fixed_asset_rollforward", "forecast_accuracy", "forecast_vs_budget", "group_trial_balance",
    "intercompany_agreement", "intercompany_match", "inventory_valuation_check", "journal_integrity", "labour_absorption_check", "labour_cost_overrun", "ledger_gross_pay", "liquidity_headroom",
    "loss_provision", "manual_journals", "margin_trail", "mgmt_pl_check", "open_exposure", "open_items_ap", "open_items_ar", "order_book_check",
    "percent_complete", "price_steps", "price_variance_report", "prior_year_column", "project_margin", "rebuild_subledger_reconciliation", "rebuild_trial_balance", "recoverable",
    "retention_receivable", "revenue_recognised", "roll_retained_earnings", "size_class", "statement_from_ledger", "statements_check", "statutory_line_of", "supplier_spend",
    "tax_provision", "three_way_match", "tie_out", "to_natural_sign", "translation_check", "utilisation", "vat_code_check", "vat_filing_calendar",
    "vat_return_from_ledger", "vat_settlement", "write_down_journal",
)


def doc_problems(name: str, fn) -> list:
    """Everything that is missing in the documentation of one function; an empty list means it passes."""
    doc = inspect.getdoc(fn) or ""
    if not doc:
        return [f"{name}: no docstring"]
    out = []
    first = doc.splitlines()[0]
    if not (first.startswith("Use this when") and first.endswith(".")):
        out.append(f"{name}: the first line must be one sentence that starts with 'Use this when'")
    found = SECTION.findall(doc)
    out += [f"{name}: no {s} section" for s in ("Args", "Returns", "Raises", "Example") if s not in found]
    if "Example" in found and ">>>" not in doc:
        out.append(f"{name}: the Example has no >>> line, so it cannot run")
    sig = inspect.signature(fn)
    if "Args" in found:
        block = re.split(r"^(?:Returns|Raises|Example):\s*$", doc.split("Args:", 1)[1], flags=re.M)[0]
        out += [f"{name}: parameter {p} is not described in Args" for p in sig.parameters if not re.search(rf"^\s+{p}:", block, re.M)]
    out += [f"{name}: parameter {p.name} has no type" for p in sig.parameters.values() if p.annotation is p.empty]
    if sig.return_annotation is sig.empty:
        out.append(f"{name}: no return type")
    meta = getattr(fn, "__halvaro__", None)
    if meta is not None and meta.summary != first:
        out.append(f"{name}: the registry summary is not the first docstring line")
    return out


def registered_functions() -> dict:
    return {n: getattr(core, n) for n in core.__all__ if hasattr(getattr(core, n, None), "__halvaro__")}


def test_every_listed_function_passes_the_documentation_gate():
    fns = registered_functions()
    problems = [p for n in PASSING for p in doc_problems(n, fns[n])]
    assert not problems, "\n".join(problems)


def test_the_list_is_exactly_the_set_of_functions_that_pass():
    now = {n for n, fn in registered_functions().items() if not doc_problems(n, fn)}
    assert now == set(PASSING), f"add to PASSING: {sorted(now - set(PASSING))}; remove from PASSING: {sorted(set(PASSING) - now)}"


def test_the_gate_fails_when_a_section_is_missing():
    def no_returns(x: int) -> int:
        """Use this when you need a test.

        Args:
            x: A number.

        Raises:
            ValueError: never.

        Example:
            >>> no_returns(1)
            1
        """
        return x

    def bad_first_line(x) -> int:
        """Gives a number.

        Args:
            y: Not the parameter.

        Returns:
            A number.

        Raises:
            ValueError: never.

        Example:
            text without a prompt
        """
        return x

    text = " ".join(doc_problems("f", no_returns))
    assert "no Returns section" in text and "no Raises" not in text and "no Example" not in text
    text = " ".join(doc_problems("g", bad_first_line))
    assert "Use this when" in text and "has no >>> line" in text and "parameter x is not described" in text and "parameter x has no type" in text
    assert doc_problems("h", lambda: None) == ["h: no docstring"]


def test_every_docstring_example_of_the_library_runs():
    flags = doctest.ELLIPSIS | doctest.NORMALIZE_WHITESPACE
    runner = doctest.DocTestRunner(optionflags=flags)
    seen = set()
    for module in sorted({fn.__module__ for fn in registered_functions().values()}):
        mod = importlib.import_module(module)
        for test in doctest.DocTestFinder(exclude_empty=True).find(mod, module):
            runner.run(test)
            if test.examples:
                seen.add(test.name.rsplit(".", 1)[-1])
    result = runner.summarize(verbose=False)
    assert result.failed == 0, f"{result.failed} docstring example(s) fail (run the module with python -m doctest to see them)"
    assert set(PASSING) <= seen, f"no example in the docstring of {sorted(set(PASSING) - seen)}"
