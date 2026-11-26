# contracts_for_project

Module `halvaro.delivery.contracts`. Import: `from halvaro.delivery import contracts_for_project`.

```python
contracts_for_project(project: pd.DataFrame, contract: pd.DataFrame, purchase_order: pd.DataFrame, prj_key: str, *, context: halvaro.core.access.Context) -> pd.DataFrame
```

Use this when you need every contract that touches one project: its customer contract, the parent frameworks above it and the supplier frameworks of its purchase orders.

The contracts are: the customer contract of the project (kind customer_contract), the parent contract of a call-off (parent_framework, followed up the chain), and the supplier frameworks of the project's purchase orders (supplier_framework, with the number of orders; an order that points at another type of contract is listed as other_contract). Columns: kind, con_key, type, sup_key, cus_key, orders. Sorted by kind and con_key. An unknown project raises.

Args:
    project: The projects.project frame, one row per prj_key; it needs prj_key and contract_key.
    contract: The contracts.contract frame, one row per con_key; it needs con_key, type, sup_key, cus_key and parent_con_key.
    purchase_order: The procurement.purchase_order frame; it needs prj_key and con_key.
    prj_key: The project key as listed in the project frame, for example PRJ-900001.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A DataFrame with kind, con_key, type, sup_key, cus_key and orders (the number of orders of that contract for the project; 0 for the customer contract and its parents), sorted by kind and con_key, index reset.

Raises:
    FrameError: a frame is not a DataFrame, has duplicate column names, lacks a needed column, or repeats a prj_key or con_key where one row per key is required; the project is not in the project frame exactly once; its contract, a parent contract or the framework of an order is not in contracts.contract; the parent chain loops.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.delivery import contracts_for_project
    >>> ctx = Context(stage="month12", role="analyst")
    >>> prj = pd.DataFrame({"prj_key": ["PRJ-900001"], "contract_key": ["CON-900001"]})
    >>> con = pd.DataFrame({"con_key": ["CON-900001", "CON-900002", "CON-900003"],
    ...                     "type": ["customer_project", "customer_framework", "supplier_framework"],
    ...                     "sup_key": [None, None, "SUP-900001"], "cus_key": ["CUS-900001", "CUS-900001", None],
    ...                     "parent_con_key": ["CON-900002", None, None]})
    >>> po = pd.DataFrame({"prj_key": ["PRJ-900001", "PRJ-900001"], "con_key": ["CON-900003", "CON-900003"]})
    >>> out = contracts_for_project(prj, con, po, "PRJ-900001", context=ctx)
    >>> out[["kind", "con_key", "orders"]].values.tolist()
    [['customer_contract', 'CON-900001', 0], ['parent_framework', 'CON-900002', 0], ['supplier_framework', 'CON-900003', 2]]

## Source columns

- `projects.project.prj_key`
- `projects.project.contract_key`
- `contracts.contract.con_key`
- `contracts.contract.parent_con_key`
- `contracts.contract.type`
- `procurement.purchase_order.prj_key`
- `procurement.purchase_order.con_key`
