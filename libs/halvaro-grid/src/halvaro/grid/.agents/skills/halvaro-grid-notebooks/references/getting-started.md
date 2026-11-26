# Getting started with halvaro-grid

Network, load and service library of the Halvaro Infra estate: telemetry quality and series, capacity, alarms, geometry and topology (0.1: quality, series, capacity, alarms, geometry, topology)

## First steps

- Import from the package: `from halvaro.grid import alarm_summary, alarm_ticket_link, critical_spares_issued`. The names of the export list are the contract.
- The library never reads data, files, credentials or the environment. Your app loads the tables and passes them in.
- An error names the column, the value and what is allowed. Fix the input, do not catch and ignore the error.

## Workflows (one notebook each)

- [From samples to alarms, incidents and tickets](samples-to-alarms-and-incidents.md): How do the ok samples of a load sensor become alarms under the limits of the sensor, how do alarms that follow each other close become one incident, how many alarms are there per zone and month, and which of them have a service ticket?
- [Strained zones and the spares for a winter plan](strained-zones-and-spares-for-a-winter-plan.md): Which zones carry strained elements, how many critical spares did the last winter use, and does the stock on the planning day, with the lead time of the supplier, carry the spares through a similar winter?
- [From load samples to a ranking of zones](zone-peak-load-ranking.md): How do hourly load samples of a heat zone become a peak per zone, and which zones rank highest once a zone with too many suspect samples is left out?

## Reference pages of the functions

- `halvaro-grid/references/alarm_summary.md`
- `halvaro-grid/references/alarm_ticket_link.md`
- `halvaro-grid/references/critical_spares_issued.md`
- `halvaro-grid/references/element_peak_load.md`
- `halvaro-grid/references/incident_groups.md`
- `halvaro-grid/references/peak_load.md`
- `halvaro-grid/references/rank_zones.md`
- `halvaro-grid/references/recompute_alarms.md`
- `halvaro-grid/references/strained_elements.md`
- `halvaro-grid/references/zone_load_percent.md`
- `halvaro-grid/references/zone_strain_summary.md`
