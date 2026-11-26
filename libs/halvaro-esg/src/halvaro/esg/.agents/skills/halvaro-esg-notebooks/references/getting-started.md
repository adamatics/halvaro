# Getting started with halvaro-esg

ESG and carbon library of the Halvaro Infra estate: emission factors, activity, recomputation, restated lines, GHG and footprint (0.1: factors, activity, recompute, lines, ghg, footprint)

## First steps

- Import from the package: `from halvaro.esg import assert_no_double_count, current_basis, intensity`. The names of the export list are the contract.
- The library never reads data, files, credentials or the environment. Your app loads the tables and passes them in.
- An error names the column, the value and what is allowed. Fix the input, do not catch and ignore the error.

## Workflows (one notebook each)

- [A restated year, counted once](restated-emission-lines.md): When emission lines of a year were restated with a new factor, how do the lines pass the rule checks, why does a plain total count a restated line together with its original, what is the total on the current basis, and how much did the restatement move it?
- [From emission lines to scope totals and intensity](scope-totals-and-intensity.md): How do emission lines of a year become totals per scope, tonnes per employee and per revenue, and a list of the scope 3 categories that have no lines?

## Reference pages of the functions

- `halvaro-esg/references/assert_no_double_count.md`
- `halvaro-esg/references/current_basis.md`
- `halvaro-esg/references/intensity.md`
- `halvaro-esg/references/restatement_bridge.md`
- `halvaro-esg/references/restatement_pairs.md`
- `halvaro-esg/references/scope3_coverage.md`
- `halvaro-esg/references/scope_totals.md`
- `halvaro-esg/references/validate_lines.md`
