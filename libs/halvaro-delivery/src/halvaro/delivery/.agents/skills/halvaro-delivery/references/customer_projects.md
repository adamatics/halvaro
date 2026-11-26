# customer_projects

Module `halvaro.delivery.commercial`. Import: `from halvaro.delivery import customer_projects`.

```python
customer_projects(customer: pd.DataFrame, project: pd.DataFrame, contract: pd.DataFrame, opportunity: pd.DataFrame | None = None, *, by: str = 'customer', contract_types: Sequence[str] = ('customer_project', 'customer_framework', 'customer_service'), context: halvaro.core.access.Context) -> pd.DataFrame
```

Use this when you need the projects and contracts per customer, or the totals and shares per customer tier.

Customer rows (by='customer'): cus_key, name, tier, n_projects, n_active, n_contracts (contracts of `contract_types`, PROPOSED the three customer types) and, with `opportunity`, won_value_dkk (expected_value_dkk of the won opportunities of the customer, not converted here). Tier rows (by='tier'): tier, n_customers, n_projects, n_contracts, won_value_dkk (with opportunity), share_of_projects and share_of_won_value (with opportunity; of all customers). Customers without a project are listed with zero.

Args:
    customer: The crm.customer frame, one row per cus_key; it needs cus_key, name and tier (no nulls).
    project: The projects.project frame, one row per prj_key; it needs prj_key, customer_key (no nulls) and status.
    contract: The contracts.contract frame, one row per con_key; it needs con_key, cus_key and type.
    opportunity: Optional crm.opportunity frame, one row per opp_key (opp_key, cus_key, stage, expected_value_dkk); it adds the won value.
    by: customer for one row per customer (default) or tier for one row per tier.
    contract_types: The contract types that count as customer contracts, a tuple or list, not a text (default customer_project, customer_framework, customer_service; PROPOSED).
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A DataFrame sorted by cus_key (by customer) or in the tier order anchor, key, standard, occasional, then other tiers (by tier); the columns are those named above.

Raises:
    FrameError: a frame is not a DataFrame, lacks a needed column or repeats a key (customer by cus_key, project by prj_key, contract by con_key, opportunity by opp_key); by is not customer or tier; contract_types is a text instead of a list; a project has no customer_key or a customer has no tier; a project or a won opportunity belongs to a customer that crm.customer does not hold.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.delivery import customer_projects
    >>> ctx = Context(stage="month12", role="analyst")
    >>> cust = pd.DataFrame({"cus_key": ["CUS-900001", "CUS-900002"], "name": ["Customer A", "Customer B"], "tier": ["key", "standard"]})
    >>> prj = pd.DataFrame({"prj_key": ["PRJ-900001"], "customer_key": ["CUS-900001"], "status": ["active"]})
    >>> con = pd.DataFrame({"con_key": ["CON-900001"], "cus_key": ["CUS-900001"], "type": ["customer_project"]})
    >>> customer_projects(cust, prj, con, context=ctx)[["cus_key", "n_projects", "n_active", "n_contracts"]].to_dict("records")
    [{'cus_key': 'CUS-900001', 'n_projects': 1, 'n_active': 1, 'n_contracts': 1}, {'cus_key': 'CUS-900002', 'n_projects': 0, 'n_active': 0, 'n_contracts': 0}]

## Source columns

- `crm.customer.cus_key`
- `crm.customer.name`
- `crm.customer.tier`
- `projects.project.prj_key`
- `projects.project.customer_key`
- `projects.project.status`
- `projects.project.opp_key`
- `contracts.contract.con_key`
- `contracts.contract.cus_key`
- `contracts.contract.type`
- `crm.opportunity.opp_key`
- `crm.opportunity.expected_value_dkk`
- `crm.opportunity.stage`
