"""Documentation quality gate of the standard slice (standard 1.5 and 3.7, issue #201, lane V): fails when one of the 15 public functions of cash, vat_tax and reconcile lacks a use-this-when line,
Args, Returns, Raises or an Example, when a parameter is undocumented or untyped, or when a legal number is typed in the prose. The other functions of the library are not checked yet."""
import inspect
import re

import halvaro.finance as fin
from halvaro.core import registry, snapshot

SLICE = ("cash_forecast_checks", "liquidity_headroom", "forecast_accuracy", "vat_return_from_ledger", "vat_code_check", "vat_settlement", "vat_filing_calendar", "tax_provision",
         "einvoice_format_share", "einvoice_gap", "rebuild_subledger_reconciliation", "fixed_asset_rollforward", "inventory_valuation_check", "bank_reconciliation", "intercompany_agreement", "open_items_ar", "open_items_ap", "retention_receivable", "ageing", "bad_debt_candidates", "customer_exposure")
SECTION = re.compile(r"^(Args|Returns|Raises|Example):\s*$", re.M)


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
    return out


def test_every_function_of_the_slice_passes_the_documentation_gate():
    problems = [p for n in SLICE for p in doc_problems(n, getattr(fin, n))]
    assert not problems, "\n".join(problems)


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


def test_the_first_line_is_the_summary_of_the_index_and_the_functions_are_exported_and_registered():
    assert registry.check() == []
    for n in SLICE:
        fn = getattr(fin, n)
        assert n in fin.__all__ and fn.__halvaro__.summary == inspect.getdoc(fn).splitlines()[0]


def test_no_legal_number_is_typed_in_the_prose_of_a_docstring():
    facts = snapshot.load()["facts"]
    legal = {float(f["value"]) for i, f in facts.items() if i.startswith(("fin.vat.", "frep.vat.", "frep.corporate_tax.", "fin.e_invoicing.", "fin.finance_planning_and_registers.inventory_valuation."))
             and isinstance(f["value"], (int, float)) and not isinstance(f["value"], bool)} - {0.0, 1.0}
    assert {0.25, 0.19} <= legal
    for n in SLICE:
        prose = inspect.getdoc(getattr(fin, n)).split("Example:", 1)[0]
        numbers = {float(w) for w in re.findall(r"(?<![\w/.-])\d+(?:\.\d+)?(?![\w/-])", prose)}
        assert not numbers & legal, f"{n}: the docstring states {sorted(numbers & legal)}, which equals a legal fact: name the fact instead"


def test_no_docstring_states_a_count_of_the_baseline():
    for n in SLICE:
        doc = inspect.getdoc(getattr(fin, n)).split("Example:", 1)[0]
        assert not re.search(r"\b(?:in|on|for) the baseline\b", doc), f"{n}: a docstring must not carry a number or claim taken from the baseline release (standard 1.7)"


def test_every_result_field_is_named_in_the_returns_text_and_the_typed_form_is_pointed_to():
    from halvaro.finance.results import RESULT_MODELS
    problems = []
    for name, model in RESULT_MODELS.items():
        returns = inspect.getdoc(getattr(fin, name)).split("Returns:", 1)[1].split("Raises:", 1)[0]
        problems += [f"{name}: the Returns text does not name the field {c.name}" for c in model.columns() if not re.search(rf"\b{c.name}\b", returns)]
        if model.__name__ not in returns:
            problems.append(f"{name}: the Returns text does not point to the typed form {model.__name__}")
    assert not problems, "\n".join(problems)
