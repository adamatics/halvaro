"""The stage guard every delivery function calls first (library-plans/halvaro-delivery.md section 5)."""
from __future__ import annotations

import functools
import inspect
from collections.abc import Callable, Iterable
from typing import Any, TypeVar, cast

from halvaro.core import Context, FrameError, require_sources
from halvaro.core.registry import function


def _with_context(sig: inspect.Signature) -> inspect.Signature:
    kw = inspect.Parameter("context", inspect.Parameter.KEYWORD_ONLY, annotation=Context)
    params = [p for p in sig.parameters.values() if p.kind is not inspect.Parameter.VAR_KEYWORD]
    tail = [p for p in sig.parameters.values() if p.kind is inspect.Parameter.VAR_KEYWORD]
    return sig.replace(parameters=[*params, kw, *tail])


_R = TypeVar("_R")


def staged(*, sources: Iterable[str], **meta: Any) -> Callable[[Callable[..., _R]], Callable[..., _R]]:
    """Register a function with the core registry and refuse it above the stage of its `context` before it runs.

    The wrapped function takes `context` (a halvaro.core.Context) as a required keyword argument; the function itself does not see it.
    A source above the context stage raises StageRefusal naming the source and the stage where it appears. Unknown meta goes to `registry.function`.
    """
    if isinstance(sources, str) or not sources or not all(isinstance(s, str) and s for s in sources):
        raise TypeError("staged(sources=...) needs a non-empty tuple of source names such as 'projects.project.start'; a function without sources needs no guard")
    sources = tuple(sources)
    names = sorted({s.split(".")[0] for s in sources})

    def deco(fn: Callable[..., _R]) -> Callable[..., _R]:
        code = cast(Any, fn).__code__
        own = tuple(code.co_varnames[:code.co_argcount + code.co_kwonlyargcount])
        if hasattr(fn, "__halvaro__"):
            raise TypeError(f"{fn.__name__} is already registered ({cast(Any, fn).__halvaro__.id}); apply staged() once")
        if "context" in own:
            raise TypeError(f"{fn.__name__} has a parameter called context; staged() adds it as a required keyword argument, rename yours")
        function(sources=sources, **{"parameters": own + ("context",), **meta})(fn)
        fid = cast(Any, fn).__halvaro__.id

        @functools.wraps(fn)
        def wrapper(*args: Any, context: Any, **kwargs: Any) -> _R:
            if not isinstance(context, Context):
                raise FrameError(f"{fid} needs context= a halvaro.core.Context (stage and role of the session), not {type(context).__name__}")
            require_sources(context, names, function=fid)
            return fn(*args, **kwargs)

        cast(Any, wrapper).__signature__ = _with_context(inspect.signature(fn))
        return wrapper

    return deco
