# footer

```python
footer(envelope: Envelope) -> str
```

Use this when you need the caption line of a result envelope: basis and as-of, 'synthetic data' when the envelope says so and 'provisional legal parameter, VERIFY' when its status carries VERIFY.

Rule: the caption of the envelope's basis and as_of, then 'synthetic data' when envelope.synthetic is true (a missing attribute counts as true), then the VERIFY label when the text VERIFY occurs
in envelope.status (so VERIFY and VERIFY+synthetic both qualify, and so does a proposed fact whose status carries it); the parts are joined with "; ".

## Args

envelope: The result envelope (any object with the attributes basis, as_of, synthetic and status; a missing attribute is read as empty, and synthetic as true).

## Returns

str: the footer text.

## Raises

FrameError: the as_of of the envelope is not empty, a date, a timestamp or an ISO date text (YYYY-MM-DD).

## Example

```python
>>> import datetime as dt
>>> from halvaro.core import Envelope, footer
>>> footer(Envelope(value=1, basis="actual cost", as_of=dt.date(2026, 11, 30), status="VERIFY", synthetic=True))
'actual cost, as of 2026-11-30; synthetic data; provisional legal parameter, VERIFY'
>>> footer(Envelope(value=1, basis="actual cost", as_of=dt.date(2026, 11, 30), synthetic=False))
'actual cost, as of 2026-11-30'
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: none (inputs are passed in).
