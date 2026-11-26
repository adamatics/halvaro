# The HR API and the libraries in one app

Notebook `notebooks/hr-api-client.ipynb` of halvaro-hr, as text without outputs. Generated from the notebook; run the notebook to see the results.

**Question.** How does an app use the HR API and the libraries together: read the leave records of a person from the API, count the leave days inside one month with the calendar of halvaro-core, and read the holiday balance that the API computed as a typed model of halvaro-hr?

## Functions used

| Function | Use this when | Reference |
|---|---|---|
| `holiday_balance` | you need the holiday balance of one person in one holiday year at the end of a month. | [holiday_balance](../../halvaro-hr-holiday/references/holiday_balance.md) |

## Steps

An app that needs HR data asks the HR API for the rows and uses the libraries for the rules. Two operations are shown: the leave records of a person, and the holiday balance, which the API computes with `holiday_balance` of halvaro-hr. The notebook has no network: the responses are synthetic ones that follow the API contract (the keys are made up; a test of the repository checks them against the OpenAPI document), served by `httpx.MockTransport`. In an app the address and the token come from the environment; the libraries never read them, and the token here is a placeholder.

```python
import datetime as dt

import httpx
import pandas as pd

from halvaro.core import working_days
from halvaro.hr import HolidayBalance, holiday_balance

RECORDED = {
    "/employees/EMP-000007/leave-records": {"items": [
        {"lv_key": "LV-000101", "emp_key": "EMP-000007", "leave_type": "holiday", "start": "2026-10-27", "end": "2026-11-06", "days": 9, "status": "taken"},
        {"lv_key": "LV-000102", "emp_key": "EMP-000007", "leave_type": "holiday", "start": "2026-11-17", "end": "2026-11-20", "days": 4, "status": "taken"},
        {"lv_key": "LV-000103", "emp_key": "EMP-000007", "leave_type": "sick", "start": "2026-11-30", "end": "2026-12-02", "days": 3, "status": "taken"}], "next_cursor": None},
    "/employees/EMP-000007/holiday-balance": {"emp_key": "EMP-000007", "holiday_year": "2026/27", "as_of": "2026-11-30", "entitlement_days": 25.0, "carried_in_days": 3.0,
                                              "carry_over_agreement": False, "accrued_days_ytd": 6.0, "taken_days_ytd": 1.0, "balance_days": 8.0, "has_entitlement_row": True,
                                              "legal_status": "VERIFY"},
}
TOKEN = "placeholder-token-of-the-notebook"


def api(request: httpx.Request) -> httpx.Response:
    assert request.headers["Authorization"] == f"Bearer {TOKEN}"          # every call carries the token, as the real service asks
    return httpx.Response(200, json=RECORDED[request.url.path.removeprefix("/hr/v1")])          # the gateway maps the base path to the service


client = httpx.Client(transport=httpx.MockTransport(api), base_url="https://api.halvaro.example/hr/v1", headers={"Authorization": f"Bearer {TOKEN}"})
client.base_url
```

Step 1. The leave records of the person. The API returns the records that overlap the period; `days` counts the working days of the whole record, never only the part inside the period.

```python
page = client.get("/employees/EMP-000007/leave-records", params={"from": str(dt.date(2026, 11, 1)), "to": str(dt.date(2026, 11, 30))}).json()
leave = pd.DataFrame(page["items"]).assign(start=lambda f: pd.to_datetime(f["start"]).dt.date, end=lambda f: pd.to_datetime(f["end"]).dt.date)
leave[["lv_key", "leave_type", "start", "end", "days"]]
```

Step 2. How many of those days fall inside November? The part of a record inside the month is counted with the working day calendar of halvaro-core, for the region of the person.

```python
first, last = dt.date(2026, 11, 1), dt.date(2026, 11, 30)
leave["days_in_november"] = [working_days(max(s, first), min(e, last), "DK") for s, e in zip(leave["start"], leave["end"])]
leave[["lv_key", "days", "days_in_november"]]
```

Step 3. The holiday balance is computed by the API. Its answer has the fields of the typed result of halvaro-hr, so the app reads it as that model.

```python
reply = client.get("/employees/EMP-000007/holiday-balance", params={"holiday_year": "2026/27"}).json()
balance = HolidayBalance(**reply)
balance
```

Step 4. The operation is the library function. With the tables that sit behind the API, `holiday_balance` gives the same answer, apart from the legal status, which follows the facts of the day.

```python
ent = pd.DataFrame({"emp_key": ["EMP-000007"], "holiday_year": ["2026/27"], "entitlement_days": [25.0], "carried_in_days": [3.0], "carry_over_agreement": [False]})
acc = pd.DataFrame({"emp_key": ["EMP-000007"] * 3, "holiday_year": ["2026/27"] * 3, "period": ["2026-09", "2026-10", "2026-11"], "accrued_days": [2.0, 2.0, 2.0], "taken_days": [0.0, 1.0, 0.0]})
local = holiday_balance(ent, acc, "EMP-000007", "2026/27", dt.date(2026, 11, 30)).to_dict()
{k: (local[k], reply[k]) for k in ("accrued_days_ytd", "taken_days_ytd", "balance_days")}
```

Check. The recorded `days` of every record equal the working days between its dates, the days inside November never exceed the days of the record, the balance equals carried-in plus accrued minus taken, the app model has exactly the fields of the response, and the local call agrees with the response in every field but the status.

```python
assert all(row.days == working_days(row.start, row.end, "DK") for row in leave.itertuples())
assert (leave["days_in_november"] <= leave["days"]).all()
assert balance.balance_days == balance.carried_in_days + balance.accrued_days_ytd - balance.taken_days_ytd
assert set(reply) == set(balance.to_dict())
assert {k: v for k, v in local.items() if k != "legal_status"} == {k: v for k, v in reply.items() if k != "legal_status"}
assert local["legal_status"] in ("ok", "VERIFY", "synthetic", "VERIFY+synthetic")
```
