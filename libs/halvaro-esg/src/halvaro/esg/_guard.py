"""The stage guard every esg function calls first (library-plans/halvaro-esg.md section 5)."""
from __future__ import annotations

import functools
import inspect
from typing import Any, Callable, Iterable, TypeVar, cast

from halvaro.core import Context, FrameError, require_sources
from halvaro.core.registry import function

R = TypeVar("R")


def _with_context(sig: inspect.Signature) -> inspect.Signature:
    kw = inspect.Parameter("context", inspect.Parameter.KEYWORD_ONLY, annotation=Context)
    params = [p for p in sig.parameters.values() if p.kind is not inspect.Parameter.VAR_KEYWORD]
    tail = [p for p in sig.parameters.values() if p.kind is inspect.Parameter.VAR_KEYWORD]
    return sig.replace(parameters=[*params, kw, *tail])


def staged(*, sources: Iterable[str], **meta: Any) -> Callable[[Callable[..., R]], Callable[..., R]]:
    """Register a function with the core registry and refuse it above the stage of its `context` before it runs.

    The wrapped function takes `context` (a halvaro.core.Context) as a required keyword argument; the function itself does not see it.
    A source above the context stage raises StageRefusal naming the source and the stage where it appears. Unknown meta goes to `registry.function`.
    """
    if isinstance(sources, str) or not sources or not all(isinstance(s, str) and s for s in sources):
        raise TypeError("staged(sources=...) needs a non-empty tuple of source names such as 'energy-esg.emission_factor.value'; a function without sources needs no guard")
    sources = tuple(sources)
    names = sorted({s.split(".")[0] for s in sources})

    def deco(fn: Callable[..., R]) -> Callable[..., R]:
        code = cast(Any, fn).__code__
        own = tuple(code.co_varnames[:code.co_argcount + code.co_kwonlyargcount])
        if hasattr(fn, "__halvaro__"):
            raise TypeError(f"{fn.__name__} is already registered ({cast(Any, fn).__halvaro__.id}); apply staged() once")
        if "context" in own:
            raise TypeError(f"{fn.__name__} has a parameter called context; staged() adds it as a required keyword argument, rename yours")
        function(sources=sources, **{"parameters": own + ("context",), **meta})(fn)
        registered: Any = fn
        fid = registered.__halvaro__.id

        @functools.wraps(fn)
        def wrapper(*args: Any, context: Any, **kwargs: Any) -> R:
            if not isinstance(context, Context):
                raise FrameError(f"{fid} needs context= a halvaro.core.Context (stage and role of the session), not {type(context).__name__}")
            require_sources(context, names, function=fid)
            return fn(*args, **kwargs)

        wrapped: Any = wrapper
        wrapped.__signature__ = _with_context(inspect.signature(fn))
        return wrapper

    return deco


def unwrapped(fn: Callable[..., R]) -> Callable[..., R]:
    """The function as it was before staged() wrapped it (functools.wraps keeps it as __wrapped__); typed like the function."""
    return cast(Callable[..., R], getattr(fn, "__wrapped__"))
