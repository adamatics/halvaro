"""Function registry: metadata of every public function, the code index and its checks."""
from __future__ import annotations

import dataclasses
import importlib
import re
import sys
from importlib import metadata, resources
import os
from pathlib import Path
from typing import Any, Callable, Collection, TypeVar, cast

from . import snapshot
from .errors import HalvaroError

TAG_RE = re.compile(r"^[A-Z]\d+b?$")
KEY_COLUMN_RE = re.compile(r"^[a-z0-9-]+\.[a-z0-9_]+\.[a-z0-9_]+$")


@dataclasses.dataclass(frozen=True)
class FunctionMeta:
    id: str
    summary: str
    since: str = "0.1.0"
    deprecated: str | None = None
    kb: tuple[str, ...] = ()
    kb_versions: tuple[str, ...] = ()
    facts: tuple[str, ...] = ()
    sources: tuple[str, ...] = ()                 # source.table.column
    stage: str | None = None            # derived: the highest stage of the sources
    oracle: str | None = None
    tags: tuple[str, ...] = ()
    restricted: tuple[str, ...] = ()
    parameters: tuple[str, ...] = ()


_REGISTRY: dict[str, FunctionMeta] = {}
F = TypeVar("F", bound=Callable[..., Any])


def _stage_of(sources: tuple[str, ...]) -> str | None:
    snap = snapshot.load()
    order = snap["stage_order"]
    held = [order.index(snap["stages"][s.split(".")[0]]) for s in sources if s.split(".")[0] in snap["stages"]]
    return order[max(held)] if held else None


_TAGS: dict[Path, dict[str, tuple[str, ...]]] = {}
_ORACLE_POINTERS: dict[Path, dict[str, str]] = {}


def _library_root(module: str) -> Path | None:
    """The folder of the library (the one with pyproject.toml and src) that holds `module`, when the module is a source file under that `src`; else None.

    An installed library (site-packages) has no such folder, and a checkout above an installed library is never taken for it, so the repository files of a library (tags.yaml, oracle-pointers.yaml)
    are read in a checkout only (rule R9: they never ship)."""
    mod = sys.modules.get(module)
    name = getattr(mod, "__file__", None) if mod is not None else None
    if not name:
        return None
    here = Path(name).resolve()
    if any(part in ("site-packages", "dist-packages") for part in here.parts):
        return None
    for parent in here.parents:
        if (parent / "pyproject.toml").exists() and (parent / "src").is_dir():
            return parent if here.is_relative_to(parent / "src") else None
    return None


def _tags_of(module: str) -> dict[str, tuple[str, ...]]:
    """The tag ids per function id from tags.yaml of the library that holds `module`, when that file is there.

    The file sits next to pyproject.toml of the library in the repository and is not part of the wheel (rule R9). It is read once per library (a file that changes while the process runs is not read again).
    A file that is not a mapping from a function id to a list of ids raises ValueError naming the file."""
    root = _library_root(module)
    if root is None:
        return {}
    path = root / "tags.yaml"
    if path not in _TAGS:
        _TAGS[path] = _read_tags(path)
    return _TAGS[path]


def _oracle_pointers_of(module: str) -> dict[str, str]:
    """The oracle pointers per function id from oracle-pointers.yaml of the library that holds `module`: the pointers that name a test or function of the closed repository
    (rule R9, lane L5.5). Same rules as the tag file: a repository file, not in the wheel, read in a checkout only; a file that is not a mapping from a function id to a text raises ValueError."""
    root = _library_root(module)
    if root is None:
        return {}
    path = root / "oracle-pointers.yaml"
    if path not in _ORACLE_POINTERS:
        _ORACLE_POINTERS[path] = _read_oracle_pointers(path)
    return _ORACLE_POINTERS[path]


def _read_oracle_pointers(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    data = _load_mapping(path)
    if data is None:
        return {}
    if not isinstance(data, dict) or any(not isinstance(v, str) or not v.startswith("py:") for v in data.values()):
        raise ValueError(f"{path}: oracle-pointers.yaml maps a function id to an oracle pointer text that starts with py:")
    return {str(k): v for k, v in data.items()}


def _load_mapping(path: Path) -> Any:
    """yaml.safe_load of a repository file, with a ValueError that names the file for a syntax error and for a key that is written twice (the second would win silently)."""
    import yaml

    class _Strict(yaml.SafeLoader):
        pass

    def _mapping(loader: Any, node: Any, deep: bool = False) -> dict[Any, Any]:
        keys = [loader.construct_object(k, deep=True) for k, _ in node.value]
        twice = sorted({str(k) for k in keys if keys.count(k) > 1})
        if twice:
            raise ValueError(f"{path}: the key {twice[0]} is written twice")
        return {k: loader.construct_object(v, deep=True) for k, (_, v) in zip(keys, node.value)}

    _Strict.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapping)
    try:
        return yaml.load(path.read_text(encoding="utf-8"), Loader=_Strict)  # noqa: S506 (a SafeLoader subclass)
    except yaml.YAMLError as exc:
        raise ValueError(f"{path}: not valid YAML ({exc.__class__.__name__})") from None


def _read_tags(path: Path) -> dict[str, tuple[str, ...]]:
    if not path.exists():
        return {}
    data = _load_mapping(path)
    if data is None:
        return {}
    if not isinstance(data, dict) or any(not isinstance(v, list) or any(not isinstance(h, str) or not TAG_RE.match(h) for h in v) for v in data.values()):
        raise ValueError(f"{path}: tags.yaml maps a function id to a list of tag ids that the registry accepts")
    return {str(k): tuple(v) for k, v in data.items()}


def function(*, summary: str | None = None, id: str | None = None, since: str = "0.1.0", deprecated: str | None = None, kb: Collection[str] = (), kb_versions: Collection[str] = (),
             facts: Collection[str] = (), sources: Collection[str] = (), oracle: str | None = None, tags: Collection[str] = (), restricted: Collection[str] = (), parameters: Collection[str] = ()) -> Callable[[F], F]:
    """Register a function. The id defaults to halvaro.core.<module>.<name>; the stage is derived from the sources when the index is exported."""
    def deco(fn: F) -> F:
        fid = id or f"{fn.__module__}.{fn.__name__}"
        doc = (fn.__doc__ or "").strip().splitlines()
        meta = FunctionMeta(id=fid, summary=summary or (doc[0].strip() if doc else ""), since=since, deprecated=deprecated, kb=tuple(kb),
                            kb_versions=tuple(kb_versions), facts=tuple(facts), sources=tuple(sources), oracle=oracle if oracle is not None else _oracle_pointers_of(fn.__module__).get(fid), tags=tuple(tags) or _tags_of(fn.__module__).get(fid, ()),
                            restricted=tuple(restricted), parameters=tuple(parameters or fn.__code__.co_varnames[: fn.__code__.co_argcount]))
        if fid in _REGISTRY:
            raise ValueError(f"function id {fid} is registered twice")
        _REGISTRY[fid] = meta
        fn.__halvaro__ = meta  # type: ignore[attr-defined]
        return fn
    return deco


def repository_file_problems(library_dir: Path, prefix: str) -> list[str]:
    """Problems of tags.yaml and oracle-pointers.yaml of one library: a function id that is not registered (a typo), and a function whose registered tags or pointer differ from the file (a keyword of
    the decorator that says something else). The index tools raise on a problem, so the files and the registry cannot drift apart."""
    out: list[str] = []
    mine = {fid: m for fid, m in _REGISTRY.items() if fid.startswith(prefix)}
    for name, read, get in (("tags.yaml", _read_tags, lambda m: m.tags), ("oracle-pointers.yaml", _read_oracle_pointers, lambda m: m.oracle)):
        data = read(library_dir / name)
        out += [f"{name} names {fid}, which is not registered" for fid in sorted(set(data) - set(mine))]
        out += [f"{name}: {fid} is registered with {get(mine[fid])!r}, the file says {data[fid]!r}" for fid in sorted(set(data) & set(mine)) if get(mine[fid]) != data[fid]]
    return out


def registered() -> dict[str, FunctionMeta]:
    """All registered functions by id (sorted)."""
    return dict(sorted(_REGISTRY.items()))


def library_prefix(library: str) -> str:
    """Id prefix of a distribution: halvaro-hr gives halvaro.hr."""
    return library.replace("-", ".") + "."


def library_of(function_id: str) -> str:
    """Distribution of a function id: halvaro.hr.org.terms_on belongs to halvaro-hr."""
    parts = function_id.split(".")
    if len(parts) < 4 or parts[0] != "halvaro":
        raise HalvaroError(f"{function_id!r} is not a function id (halvaro.<domain>.<module>.<function>)")
    return f"{parts[0]}-{parts[1]}"


def library_version(distribution: str = "halvaro-core") -> str:
    """Version of an installed distribution, or of its source tree (the `_version` module of the package) when running from a checkout."""
    try:
        return metadata.version(distribution)
    except metadata.PackageNotFoundError:
        try:
            return cast(str, importlib.import_module(library_prefix(distribution) + "_version").__version__)
        except (ImportError, AttributeError) as e:
            raise HalvaroError(f"no version for {distribution}: it is not installed and has no {library_prefix(distribution)}_version module") from e


def export_index(path: str | os.PathLike[str] | None = None, library: str = "halvaro-core") -> list[dict[str, Any]]:
    """Sorted records of the code index of one distribution (the ids with its package prefix, stamped with its name and version in memory); written as code-index.yaml, without the version (committed_form), when a path is given."""
    if not re.fullmatch(r"halvaro-[a-z][a-z_]*", library):
        raise HalvaroError(f"{library!r} is not a distribution name (halvaro-<domain>, lower case letters and underscores)")
    records, prefix, version = [], library_prefix(library), library_version(library)
    for fid, m in registered().items():
        if not fid.startswith(prefix):
            continue
        r = {k: (list(v) if isinstance(v, tuple) else v) for k, v in dataclasses.asdict(m).items()}
        r["stage"] = _stage_of(m.sources)
        r["library"], r["version"] = library, version
        records.append(r)
    if not records:
        raise HalvaroError(f"no registered function has the prefix {prefix}: import the package of {library} before exporting its index, and check the name")
    if path is not None:
        import yaml
        with open(path, "w", encoding="utf-8") as f:
            yaml.safe_dump({"snapshot": snapshot.snapshot_hash(), "functions": committed_form(records)}, f, sort_keys=True, allow_unicode=True)
    return records


def committed_form(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The records as they are committed in a code-index.yaml: without `version` (issue #241). The version of a package comes from the package at install time (a tag or its
    `_version` module), so a committed index that stamped it would change with every tag. `since` stays. `export_index` still returns the version in memory."""
    return [{k: v for k, v in r.items() if k != "version"} for r in records]


def index_schema() -> dict[str, Any]:
    """JSON Schema of one code index record."""
    import json
    return cast("dict[str, Any]", json.loads(resources.files("halvaro.core").joinpath("_data/code-index.schema.json").read_text(encoding="utf-8")))


def check(*, known_kb: Collection[str] | None = None, oracle_exists: Callable[[str], bool] | None = None) -> list[str]:
    """Problems of the registered functions: unknown facts, columns or stage, bad tag ids, unregistered replacement, KB or oracle ids that do not exist."""
    snap, problems = snapshot.load(), []
    columns, reg = set(snap["columns"]), registered()
    for fid, m in reg.items():
        for f in m.facts:
            if f not in snap["facts"]:
                problems.append(f"{fid}: fact {f} is not in the snapshot")
        for c in (*m.sources, *m.restricted):
            if c not in columns:
                problems.append(f"{fid}: column {c} is not in the dictionary")
        if any(not TAG_RE.match(h) for h in m.tags):
            problems.append(f"{fid}: tag ids {m.tags} are not a capital letter and a number")
        if m.deprecated and m.deprecated not in reg:
            problems.append(f"{fid}: deprecated names {m.deprecated}, which is not registered")
        if known_kb is not None:
            for k in (*m.kb, *(v.split("@")[0] for v in m.kb_versions)):
                if k not in known_kb:
                    problems.append(f"{fid}: KB document {k} does not exist")
        if oracle_exists and m.oracle and not oracle_exists(m.oracle):
            problems.append(f"{fid}: oracle {m.oracle} does not exist")
    return problems
