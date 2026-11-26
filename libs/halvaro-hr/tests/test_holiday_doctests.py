"""The docstring examples of the holiday module run as doctests (standard 3.7, issue #196). Limited to holiday.py: the other modules have no examples yet."""
import doctest

import halvaro.hr.holiday as holiday

FUNCTIONS = ("holiday_year_label", "holiday_year_bounds", "holiday_balance", "holiday_ledger", "carry_over_position", "carry_over_projection",
             "accrual_expected", "leave_vs_ledger", "high_carry_over")


def test_every_docstring_example_of_the_holiday_functions_runs():
    flags = doctest.ELLIPSIS | doctest.NORMALIZE_WHITESPACE
    runner = doctest.DocTestRunner(optionflags=flags)
    seen = set()
    for test in doctest.DocTestFinder(exclude_empty=True).find(holiday, "halvaro.hr.holiday"):
        runner.run(test)
        if test.examples:
            seen.add(test.name.rsplit(".", 1)[-1])
    result = runner.summarize(verbose=False)
    assert result.failed == 0, f"{result.failed} docstring example(s) of holiday.py fail (run the module with python -m doctest to see them)"
    assert set(FUNCTIONS) <= seen, f"no example in the docstring of {sorted(set(FUNCTIONS) - seen)}"
