"""Typed results of the finance slice (standard 3.1): one frozen model per result row, every field with a description and a unit.

The functions of `cash`, `vat_tax` and `reconcile` still return what they returned before (a frame, or an Envelope that holds a frame): existing code and the oracle tests read those. The models are
the typed form beside them: `VatReturnRow.from_frame(envelope.value)` gives one frozen `VatReturnRow` per row, and `Model.columns()` lists the fields with type, description and unit. A missing
value of the frame becomes None. Importing this module does no I/O.
"""
from __future__ import annotations

import dataclasses
from typing import Any, TypeVar

import pandas as pd

from halvaro.core import FrameError

# The units a field may carry. Money is "currency" (the currency of the entity, or the currency column of the row), a yes or no is "flag", a number of rows or weeks is "count".
UNITS = ("currency", "share", "days", "count", "date", "month", "flag", "key", "label", "status", "text")


def _field(description: str, unit: str) -> Any:
    """A dataclass field that carries its description and unit as metadata."""
    if unit not in UNITS:
        raise ValueError(f"unit {unit!r} is not one of {UNITS}")
    return dataclasses.field(metadata={"description": description, "unit": unit})


@dataclasses.dataclass(frozen=True)
class ColumnSpec:
    """One field of a result: its name, type as text, description and unit."""

    name: str
    type: str
    description: str
    unit: str


@dataclasses.dataclass(frozen=True)
class _Row:
    """Base of the models of one frame row."""

    @classmethod
    def columns(cls) -> tuple[ColumnSpec, ...]:
        """The fields of the model in order, each with type, description and unit."""
        return tuple(ColumnSpec(f.name, str(f.type), f.metadata["description"], f.metadata["unit"]) for f in dataclasses.fields(cls))

    @classmethod
    def from_frame(cls: type[R], frame: pd.DataFrame) -> tuple[R, ...]:
        """One frozen model per row of the frame returned by the function of this model; a missing value becomes None.

        Raises FrameError when the frame lacks a column of the model.
        """
        names = [c.name for c in cls.columns()]
        absent = [n for n in names if n not in frame.columns]
        if absent:
            raise FrameError(f"{cls.__name__}.from_frame: the frame lacks column(s) {', '.join(absent)}")
        return tuple(cls(**{str(k): (None if _missing(v) else v) for k, v in r.items()}) for r in frame[names].to_dict("records"))


R = TypeVar("R", bound=_Row)


def _missing(value: Any) -> bool:
    """True for None, NaN, NaT and pd.NA: a missing value of a frame."""
    if value is None or value is pd.NA:
        return True
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


@dataclasses.dataclass(frozen=True)
class ViolationRow(_Row):
    """One violation listed by `cash_forecast_checks`, `vat_code_check`, `inventory_valuation_check` or `intercompany_agreement`."""

    table: str = _field("Table the violation is in, for example finance.journal_line.", "text")
    key: str = _field("Key of the row or group the violation is about, for example an entity and a month.", "key")
    rule: str = _field("Name of the rule that is broken, for example rate_mismatch.", "label")
    detail: str = _field("What was found, in one sentence with the figures.", "text")


@dataclasses.dataclass(frozen=True)
class HeadroomRow(_Row):
    """One row of `liquidity_headroom`: the headroom of one forecast to the minimum cash floor."""

    le_key: str = _field("Key of the legal entity.", "key")
    forecast_date: str = _field("Date the forecast was made.", "date")
    weeks: int = _field("Number of forecast weeks.", "count")
    first_breach_week: float = _field("First week in which the 10th percentile closing cash is below the floor; empty when no week is.", "count")
    lowest_headroom_p10: float = _field("Lowest value of the 10th percentile closing cash less the floor.", "currency")
    lowest_headroom_week: int = _field("Week of the lowest headroom.", "count")
    rcf_available_at_lowest: float = _field("Facility limit less drawn in the week of the lowest headroom.", "currency")
    breach_weeks: int = _field("Number of weeks in which the 10th percentile closing cash is below the floor.", "count")
    agrees: bool = _field("True when the recomputed headroom, facility and breach flag equal the stored columns within the tolerance.", "flag")


@dataclasses.dataclass(frozen=True)
class AccuracyRow(_Row):
    """One row of `forecast_accuracy`: band coverage and error of a forecast horizon."""

    le_key: str = _field("Key of the legal entity.", "key")
    n: int = _field("Number of forecast weeks that have an actual closing cash.", "count")
    coverage: float = _field("Share of those weeks whose actual is inside the 10th to 90th percentile band, between 0 and 1.", "share")
    mean_abs_error: float = _field("Mean absolute error of the closing cash.", "currency")
    median_abs_error: float = _field("Median absolute error of the closing cash.", "currency")
    mean_error: float = _field("Mean of actual less forecast closing cash; positive when the forecast was too low.", "currency")
    week_no: int = _field("Forecast horizon in weeks; 0 is all horizons of the entity. It is the last column of a frame with rows and the second column of the empty frame.", "count")


@dataclasses.dataclass(frozen=True)
class VatReturnRow(_Row):
    """One row of `vat_return_from_ledger`: the VAT return of an entity and month."""

    le_key: str = _field("Key of the legal entity.", "key")
    period: str = _field("Month of the return as YYYY-MM.", "month")
    currency: str = _field("Currency of the entity; all amounts of the row are in it.", "label")
    output_vat_domestic: float = _field("Output VAT on domestic sales.", "currency")
    output_vat_acquisition_eu: float = _field("Output VAT on acquisitions from the EU (reverse charge).", "currency")
    output_vat_acquisition_non_eu: float = _field("Output VAT on acquisitions from outside the EU (reverse charge).", "currency")
    input_vat_domestic: float = _field("Input VAT on domestic purchases.", "currency")
    input_vat_acquisition_eu: float = _field("Input VAT on acquisitions from the EU.", "currency")
    input_vat_acquisition_non_eu: float = _field("Input VAT on acquisitions from outside the EU.", "currency")
    input_vat_import: float = _field("Input VAT on imports.", "currency")
    total_output_vat: float = _field("Sum of the output boxes.", "currency")
    total_input_vat: float = _field("Sum of the input boxes.", "currency")
    vat_payable: float = _field("total_output_vat less total_input_vat; negative is a refund.", "currency")
    taxable_base_domestic_sales: float = _field("Taxable base of the domestic sales.", "currency")
    taxable_base_acquisitions_eu: float = _field("Taxable base of the acquisitions from the EU.", "currency")
    taxable_base_acquisitions_non_eu: float = _field("Taxable base of the acquisitions from outside the EU.", "currency")
    taxable_base_domestic_purchases: float = _field("Taxable base of the domestic purchases.", "currency")


@dataclasses.dataclass(frozen=True)
class VatSettlementRow(_Row):
    """One row of `vat_settlement`: a return against the payment of the following month."""

    le_key: str = _field("Key of the legal entity.", "key")
    period: str = _field("Month of the return as YYYY-MM.", "month")
    vat_payable: float = _field("VAT payable of the return.", "currency")
    payment_month: str = _field("Month the payment is looked for in, the month after the period.", "month")
    paid_signed: float = _field("Signed VAT payment of the payment month: outgoing positive, incoming negative; empty without a payment.", "currency")
    paid_date: str = _field("Day of the payment; empty without a payment.", "date")
    settlement_difference: float = _field("vat_payable less the signed payment; empty without a payment.", "currency")
    stored_difference: float = _field("The settlement difference stored with the return.", "currency")
    agrees: bool = _field("True when the recomputed and the stored difference agree within the tolerance; empty without a payment.", "flag")
    day_agrees: bool = _field("True when the payment is on the day of the fact or the next working day; empty without a payment.", "flag")


@dataclasses.dataclass(frozen=True)
class FilingDateRow(_Row):
    """One row of `vat_filing_calendar`: the due date of a return."""

    le_key: str = _field("Key of the legal entity.", "key")
    period: str = _field("Month of the return as YYYY-MM.", "month")
    due_date: str = _field("Filing due date by the rule of the function.", "date")
    stored_due_date: str = _field("The due date stored with the return; empty when none is stored.", "date")
    agrees: bool = _field("True when the stored date equals the due date of the rule.", "flag")


@dataclasses.dataclass(frozen=True)
class TaxProvisionRow(_Row):
    """One row of `tax_provision`: the recomputed corporate tax of an entity and fiscal year."""

    le_key: str = _field("Key of the legal entity.", "key")
    fiscal_year: int = _field("Fiscal year of the provision.", "label")
    tax_rate: float = _field("Tax rate of the row, a share.", "share")
    profit_before_tax: float = _field("Profit before tax, as stored.", "currency")
    taxable_income_before_losses: float = _field("Profit before tax plus non deductible expenses less exempt income less the temporary difference movement.", "currency")
    tax_loss_utilised: float = _field("Loss carried in that is used against the income of the year.", "currency")
    tax_loss_added: float = _field("Loss of the year that is added to the loss carried forward.", "currency")
    tax_loss_carried_forward: float = _field("Loss carried forward at the end of the year.", "currency")
    taxable_income: float = _field("Taxable income before losses less the loss utilised.", "currency")
    current_tax: float = _field("Rate times taxable income.", "currency")
    deferred_tax_movement: float = _field("Deferred tax movement, as stored.", "currency")
    total_tax_expense: float = _field("Current tax plus the deferred tax movement.", "currency")
    rate_is_the_fact: bool = _field("True when the rate of the row equals the fact of the country of the entity.", "flag")
    agrees: bool = _field("True when every recomputed figure equals the stored one within the tolerance and the rate is the fact.", "flag")


@dataclasses.dataclass(frozen=True)
class EinvoiceShareRow(_Row):
    """One row of `einvoice_format_share`: the structured share of the invoices of one month."""

    period: str = _field("Month of the invoices as YYYY-MM.", "month")
    n_invoices: int = _field("Number of third party invoices counted.", "count")
    n_structured: int = _field("Number of those invoices in a structured format.", "count")
    share: float = _field("n_structured divided by n_invoices, four decimals, between 0 and 1.", "share")


@dataclasses.dataclass(frozen=True)
class EinvoiceGapRow(_Row):
    """One row of `einvoice_gap`: a customer that still receives pdf invoices."""

    cus_key: str = _field("Key of the customer.", "key")
    n_pdf: int = _field("Number of pdf invoices in the window.", "count")
    n_invoices: int = _field("Number of invoices in the window.", "count")
    last_invoice_date: str = _field("Date of the last invoice in the window.", "date")
    last_format: str = _field("Invoice format of the last invoice.", "label")
    days_to_mandatory: int = _field("Days from as_of to the mandatory date of structured invoices; negative after it.", "days")


@dataclasses.dataclass(frozen=True)
class SubledgerReconciliationRow(_Row):
    """One row of `rebuild_subledger_reconciliation`: a subledger against its control account at a month end."""

    le_key: str = _field("Key of the legal entity.", "key")
    period: str = _field("Month end as YYYY-MM.", "month")
    subledger: str = _field("Name of the subledger, for example receivables.", "label")
    detail: str = _field("Part of the subledger, for example an asset class or a bank account; empty for the whole subledger.", "label")
    gl_key: str = _field("Control account in the ledger.", "key")
    subledger_balance: float = _field("Balance rebuilt from the subledger.", "currency")
    ledger_balance: float = _field("Closing balance of the control account in the trial balance.", "currency")
    difference: float = _field("subledger_balance less ledger_balance.", "currency")
    currency: str = _field("Currency of the entity.", "label")
    reconciled: bool = _field("True when the difference is zero to the cent.", "flag")


@dataclasses.dataclass(frozen=True)
class AssetScheduleRow(_Row):
    """One row of `fixed_asset_rollforward`: cost and accumulated depreciation of an asset class and month."""

    le_key: str = _field("Key of the legal entity.", "key")
    asset_class: str = _field("Asset class of the register.", "label")
    period: str = _field("Month as YYYY-MM.", "month")
    cost_opening: float = _field("Cost at the start of the month.", "currency")
    additions: float = _field("Cost of the assets acquired in the month.", "currency")
    disposals_cost: float = _field("Cost of the assets disposed of in the month.", "currency")
    cost_closing: float = _field("Cost at the end of the month.", "currency")
    accumulated_opening: float = _field("Accumulated depreciation at the start of the month.", "currency")
    depreciation: float = _field("Depreciation of the month.", "currency")
    disposals_accumulated: float = _field("Accumulated depreciation of the assets disposed of in the month.", "currency")
    accumulated_closing: float = _field("Accumulated depreciation at the end of the month.", "currency")
    net_book_value: float = _field("cost_closing less accumulated_closing.", "currency")
    currency: str = _field("Currency of the entity.", "label")


@dataclasses.dataclass(frozen=True)
class BankReconRow(_Row):
    """One row of `bank_reconciliation`: the computed balance of a bank account on a date against the stored balance."""

    le_key: str = _field("Key of the legal entity.", "key")
    bank_account: str = _field("Key of the bank account.", "key")
    balance_date: str = _field("Date of the stored balance.", "date")
    computed_balance: float = _field("Opening balance of the ledger account plus the signed payments up to the date.", "currency")
    closing_balance: float = _field("The stored closing balance of the date.", "currency")
    difference: float = _field("computed_balance less closing_balance, to the cent.", "currency")
    currency: str = _field("Currency of the bank account.", "label")


@dataclasses.dataclass(frozen=True)
class OpenItemArRow(_Row):
    """One row of `open_items_ar`: an open receivable, an invoice or an opening item, on a date."""

    item_key: str = _field("Key of the invoice or the opening item.", "key")
    source: str = _field("invoice or opening.", "label")
    le_key: str = _field("Key of the legal entity.", "key")
    cus_key: str = _field("Key of the customer; empty for an opening item without a customer.", "key")
    inv_key: str = _field("Key of the invoice; empty for an opening item.", "key")
    document_date: str = _field("Date of the invoice or the opening item.", "date")
    due_date: str = _field("Due date; empty when none is stored.", "date")
    currency: str = _field("Currency of the entity; all amounts of the row are in it.", "label")
    invoice_amount: float = _field("Amount including retention, a credit note negative.", "currency")
    paid: float = _field("Payments allocated up to and including the date.", "currency")
    written_off: float = _field("Amount written off up to the date.", "currency")
    open_amount: float = _field("invoice_amount less paid less written_off.", "currency")
    retention_held: float = _field("Retention billed and not yet released on the date; part of open_amount.", "currency")
    release_date: str = _field("Release date of the retention: of the invoice, or the due date of an opening item.", "date")


@dataclasses.dataclass(frozen=True)
class OpenItemApRow(_Row):
    """One row of `open_items_ap`: an open payable, a supplier invoice or an opening item, on a date."""

    item_key: str = _field("Key of the supplier invoice or the opening item.", "key")
    source: str = _field("invoice or opening.", "label")
    le_key: str = _field("Key of the legal entity.", "key")
    sup_key: str = _field("Key of the supplier; empty for an opening item without a supplier.", "key")
    sinv_key: str = _field("Key of the supplier invoice; empty for an opening item.", "key")
    document_date: str = _field("Date of the invoice or the opening item.", "date")
    due_date: str = _field("Due date; empty when none is stored.", "date")
    currency: str = _field("Currency of the entity; all amounts of the row are in it.", "label")
    payable_amount_le: float = _field("Amount owed, a credit note negative.", "currency")
    paid: float = _field("Payments allocated up to and including the date.", "currency")
    open_amount: float = _field("payable_amount_le less paid.", "currency")


@dataclasses.dataclass(frozen=True)
class RetentionRow(_Row):
    """One row of `retention_receivable`: a retention held per item, or the total of an entity."""

    item_key: str = _field("Key of the invoice or opening item; empty on a total row.", "key")
    source: str = _field("invoice, opening or total.", "label")
    le_key: str = _field("Key of the legal entity.", "key")
    cus_key: str = _field("Key of the customer; empty on a total row.", "key")
    document_date: str = _field("Date of the invoice or opening item; empty on a total row.", "date")
    release_date: str = _field("Release date of the retention; empty on a total row.", "date")
    currency: str = _field("Currency of the entity.", "label")
    retention_held: float = _field("Retention held on the item, or the sum over the entity on a total row.", "currency")


@dataclasses.dataclass(frozen=True)
class AgeingRow(_Row):
    """One row of `ageing` for customers (party cus_key): the open receivable of a customer in a bucket of days past due."""

    le_key: str = _field("Key of the legal entity.", "key")
    cus_key: str = _field("Key of the customer.", "key")
    bucket: str = _field("Bucket of days past due, for example 31-60, or no_due_date.", "label")
    n_items: int = _field("Number of open items in the bucket.", "count")
    amount: float = _field("Open amount less retention held in the bucket.", "currency")


@dataclasses.dataclass(frozen=True)
class AgeingApRow(_Row):
    """One row of `ageing` for suppliers (party sup_key): the open payable of a supplier in a bucket of days past due."""

    le_key: str = _field("Key of the legal entity.", "key")
    sup_key: str = _field("Key of the supplier.", "key")
    bucket: str = _field("Bucket of days past due, for example 31-60, or no_due_date.", "label")
    n_items: int = _field("Number of open items in the bucket.", "count")
    amount: float = _field("Open amount in the bucket.", "currency")


@dataclasses.dataclass(frozen=True)
class BadDebtRow(OpenItemArRow):
    """One row of `bad_debt_candidates`: an open receivable overdue by at least the write-off days of the fact."""

    receivable_net: float = _field("open_amount less retention_held.", "currency")
    days_past_due: int = _field("Days from the due date to the date asked for.", "days")


@dataclasses.dataclass(frozen=True)
class CustomerExposureRow(_Row):
    """One row of `customer_exposure`: the open receivables of a customer against its credit limit."""

    cus_key: str = _field("Key of the customer.", "key")
    credit_limit: float = _field("Credit limit as stored, in the limit currency; empty when none is set.", "currency")
    limit_currency: str = _field("Currency of the credit limit.", "label")
    limit_dkk: float = _field("Credit limit in DKK at the fixed booking rate; empty without a limit.", "currency")
    open_dkk: float = _field("Open receivables of the customer in DKK at the fixed booking rate.", "currency")
    utilisation: float = _field("open_dkk divided by limit_dkk, a share; empty without a limit.", "share")
    over_limit: bool = _field("True when open_dkk is above limit_dkk; always false without a limit.", "flag")


# Function name to the model of the rows of its result. Used by the documentation quality test and by tools/build_skill.py.
RESULT_MODELS: dict[str, type[_Row]] = {
    "cash_forecast_checks": ViolationRow,
    "liquidity_headroom": HeadroomRow,
    "forecast_accuracy": AccuracyRow,
    "vat_return_from_ledger": VatReturnRow,
    "vat_code_check": ViolationRow,
    "vat_settlement": VatSettlementRow,
    "vat_filing_calendar": FilingDateRow,
    "tax_provision": TaxProvisionRow,
    "einvoice_format_share": EinvoiceShareRow,
    "einvoice_gap": EinvoiceGapRow,
    "rebuild_subledger_reconciliation": SubledgerReconciliationRow,
    "fixed_asset_rollforward": AssetScheduleRow,
    "inventory_valuation_check": ViolationRow,
    "bank_reconciliation": BankReconRow,
    "intercompany_agreement": ViolationRow,
    "open_items_ar": OpenItemArRow,
    "open_items_ap": OpenItemApRow,
    "retention_receivable": RetentionRow,
    "ageing": AgeingRow,
    "bad_debt_candidates": BadDebtRow,
    "customer_exposure": CustomerExposureRow,
}
