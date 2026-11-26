# Getting started with halvaro-delivery

Delivery library of the Halvaro Infra estate: projects, comparables, procurement, inventory, contracts and crm (0.1: scaffold)

## First steps

- Import from the package: `from halvaro.delivery import contingency_advice, delay_days, estimate_amount_per_metre`. The names of the export list are the contract.
- The library never reads data, files, credentials or the environment. Your app loads the tables and passes them in.
- An error names the column, the value and what is allowed. Fix the input, do not catch and ignore the error.

## Workflows (one notebook each)

- [From the estimate to the margin and the cost still to come](estimate-to-margin-and-cost-to-completion.md): For running projects, how does the latest forecast estimate become the percent complete, the revenue and the loss provision, the two margins and the cost still to come, and what does the portfolio come to per currency?
- [How late a project was: plan versions, milestones and delay days](plan-versions-and-overrun.md): How far did the plan of a project move over its versions, which milestones were done late or are overdue on a day, how large was the overrun of a finished project, and do the logged delay days add up to the difference between planned and actual end?
- [From the open tenders to the price per metre](tender-pipeline-and-price-per-metre.md): Which tenders are open on a day, how often were decided tenders won, and what does the estimate of a project cost per route metre once the contingency has been advised from the delay record?

## Reference pages of the functions

- `halvaro-delivery/references/contingency_advice.md`
- `halvaro-delivery/references/delay_days.md`
- `halvaro-delivery/references/estimate_amount_per_metre.md`
- `halvaro-delivery/references/estimate_bridge.md`
- `halvaro-delivery/references/milestone_slippage.md`
- `halvaro-delivery/references/open_tenders.md`
- `halvaro-delivery/references/plan_slip.md`
- `halvaro-delivery/references/schedule_overrun.md`
- `halvaro-delivery/references/win_rate.md`
