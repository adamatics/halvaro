"""Stage guard of the hr functions that read a source above Day 1 (competence, projects, it-assets).

Plan halvaro-hr.md 8.3: a Day 1 session asking for competence, project or it-asset data gets a refusal that names the missing source. The guard lives in the
function (decision of 2026-11-01, HF-05), not only in the MCP layer. It is `halvaro-delivery`'s `staged`, with one difference: the
`context` keyword is optional, so the many callers that pass frames without a session keep working. When a context is given and a
source is above its stage, StageRefusal is raised before the function runs. Without a context nothing is checked.
"""
from __future__ import annotations

import functools
import inspect
from typing import Any, Callable, Iterable, TypeVar, cast

from halvaro.core import Context, FrameError, require_sources
from halvaro.core.registry import function

_F = TypeVar("_F", bound=Callable[..., Any])


def _with_context(sig: inspect.Signature) -> inspect.Signature:
    kw = inspect.Parameter("context", inspect.Parameter.KEYWORD_ONLY, default=None, annotation="Context | None")
    params = [p for p in sig.parameters.values() if p.kind is not inspect.Parameter.VAR_KEYWORD]
    tail = [p for p in sig.parameters.values() if p.kind is inspect.Parameter.VAR_KEYWORD]
    return sig.replace(parameters=[*params, kw, *tail])


def staged(*, sources: Iterable[str], **meta: Any) -> Callable[[_F], _F]:
    """Register a function with the core registry and refuse it above the stage of its optional `context` before it runs."""
    if isinstance(sources, str) or not sources or not all(isinstance(s, str) and s for s in sources):
        raise TypeError("staged(sources=...) needs a non-empty tuple of source names such as 'competence.requirement.qual_key'")
    sources = tuple(sources)
    names = sorted({s.split(".")[0] for s in sources})

    def deco(fn: _F) -> _F:
        code = fn.__code__
        own = tuple(code.co_varnames[:code.co_argcount])      # as the plain @function registers them: positional parameters only (the index and the pinned tests keep their shape)
        if hasattr(fn, "__halvaro__"):
            raise TypeError(f"{fn.__name__} is already registered; apply staged() once")
        if "context" in code.co_varnames[:code.co_argcount + code.co_kwonlyargcount]:
            raise TypeError(f"{fn.__name__} has a parameter called context; call stage_check(context, ...) inside it instead")
        # The registered parameters stay those of the function: existing tests pin them, and `context` is optional for every caller.
        function(sources=sources, **{"parameters": own, **meta})(fn)
        fid = cast(Any, fn).__halvaro__.id

        @functools.wraps(fn)
        def wrapper(*args: Any, context: Any = None, **kwargs: Any) -> Any:
            if context is not None:
                if not isinstance(context, Context):
                    raise FrameError(f"{fid} needs context= a halvaro.core.Context (stage and role of the session), not {type(context).__name__}")
                require_sources(context, names, function=fid)
            return fn(*args, **kwargs)

        cast(Any, wrapper).__signature__ = _with_context(inspect.signature(fn))
        return cast(_F, wrapper)

    return deco


def stage_check(context: Any, sources: Iterable[str], function_id: str) -> None:
    """For a function that already takes `context`: refuse when a source is above the stage of a given context (None: no check)."""
    if context is not None:
        require_sources(context, sorted({s.split(".")[0] for s in sources}), function=function_id)
