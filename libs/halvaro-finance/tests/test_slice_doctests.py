"""The docstring examples of the standard slice (cash, vat_tax, reconcile) run as doctests (standard 3.7, issue #201, lane V). Limited to these three modules."""
import doctest

import halvaro.finance.cash as cash
import halvaro.finance.reconcile as reconcile
import halvaro.finance.subledgers as subledgers
import halvaro.finance.vat_tax as vat_tax

SLICE = {cash: ("cash_forecast_checks", "liquidity_headroom", "forecast_accuracy"),
         vat_tax: ("vat_return_from_ledger", "vat_code_check", "vat_settlement", "vat_filing_calendar", "tax_provision", "einvoice_format_share", "einvoice_gap"),
         reconcile: ("rebuild_subledger_reconciliation", "fixed_asset_rollforward", "inventory_valuation_check", "bank_reconciliation", "intercompany_agreement"),
         subledgers: ("open_items_ar", "open_items_ap", "retention_receivable", "ageing", "bad_debt_candidates", "customer_exposure")}


def test_every_docstring_example_of_the_slice_runs():
    runner = doctest.DocTestRunner(optionflags=doctest.ELLIPSIS | doctest.NORMALIZE_WHITESPACE)
    seen = set()
    for module in SLICE:
        for test in doctest.DocTestFinder(exclude_empty=True).find(module, module.__name__):
            runner.run(test)
            if test.examples:
                seen.add(test.name.rsplit(".", 1)[-1])
    result = runner.summarize(verbose=False)
    assert result.failed == 0, f"{result.failed} docstring example(s) of the slice fail (run python -m doctest on the module to see them)"
    want = {n for names in SLICE.values() for n in names}
    assert want <= seen, f"no example in the docstring of {sorted(want - seen)}"
