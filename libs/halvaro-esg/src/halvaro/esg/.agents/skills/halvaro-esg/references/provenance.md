# provenance

Module `halvaro.esg.basis`. Import: `from halvaro.esg import provenance`.

```python
provenance(*results: Envelope) -> Provenance
```

Use this when you need the provenance of a result computed from other results: their factor sets, VERIFY notes, facts and status joined.

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
