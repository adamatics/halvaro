# master_of

```python
master_of(prefix: str) -> MasterInfo
```

Use this when you have a key prefix and need the entity it names and the table that is its master.

Rule: the prefix is looked up in the master list of the design (master-of.yaml): the entity, the source, the table, the key column and the stage at which the master becomes visible.

## Args

prefix: A key prefix such as EMP.

## Returns

MasterInfo: prefix, entity, source, table, column and stage.

## Raises

KeyFormatError: the prefix has no master.

## Example

```python
>>> from halvaro.core import master_of
>>> info = master_of("EMP")
>>> info.source, info.table, info.stage
('hr', 'employee', 'day1')
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: none (inputs are passed in).
