# reporting_basis

Module `halvaro.esg.basis`. Import: `from halvaro.esg import reporting_basis`.

```python
reporting_basis(decision: str, *, context: halvaro.core.access.Context) -> BasisStatement
```

Use this when you need the statement of the reporting basis, with its VERIFY flags, from the policy decision text.

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

## Source columns

- `energy-esg.esg_data_request.standard`
