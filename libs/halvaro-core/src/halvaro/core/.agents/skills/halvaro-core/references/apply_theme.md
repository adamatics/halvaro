# apply_theme

```python
apply_theme(figure: Any, mode: str = 'light') -> Any
```

Use this when you need a chart to carry the colours and font of the light or dark theme.

Rule: the theme tokens of the mode (proposed, they wait for a design review) are set on the figure. A plotly figure (one with update_layout) gets the paper and plot background, the text colour and font, the categorical colours as colorway and the grid colour on both axes. A matplotlib figure (one with axes and set_facecolor) gets the background on the figure and every axes, the text colour on ticks, axis labels and title, and the grid colour. The same figure object is returned.

## Args

figure: A plotly figure or a matplotlib figure.
mode: "light" or "dark". Default "light" (proposed).

## Returns

Any: the figure that was passed in, changed in place.

## Raises

FrameError: the mode is neither light nor dark (checked first), or the figure is neither a plotly nor a matplotlib figure.

## Example

```python
>>> from halvaro.core import apply_theme
>>> class Fig:
...     def update_layout(self, **settings):
...         self.layout = settings
...     def update_xaxes(self, **settings):
...         pass
...     def update_yaxes(self, **settings):
...         pass
>>> fig = Fig()
>>> apply_theme(fig, "dark") is fig
True
>>> fig.layout["paper_bgcolor"], len(fig.layout["colorway"])
('#14181D', 6)
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: none (inputs are passed in).
