# region_of

```python
region_of(site_key: str | None = None, *, country: str | None = None) -> str
```

Use this when you need the calendar region (DK, DE-HH or DE-NI) of a site or of a country with one region.

Rule: a site key gives the region of that site. A country gives its region only when it has exactly one (Denmark); Germany has two, so the site key of the person's team is needed.

## Args

site_key: The key of a site, for example "SITE-05". Optional.
country: DK, when no site key is given.

## Returns

str: the region.

## Raises

UnknownRegion: the site key is not a known site, the country is DE (two regions, pass the site key) or the country has no region.

## Example

```python
>>> from halvaro.core import region_of
>>> region_of("SITE-05"), region_of(country="DK")
('DE-HH', 'DK')
>>> region_of(country="DE")
Traceback (most recent call last):
...
halvaro.core.errors.UnknownRegion: country DE has two regions (DE-HH, DE-NI); pass the site key of the person's team
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `hr.site.site_key`, `hr.site.country`.
