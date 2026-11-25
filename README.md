# PyPSA-Lesotho

Generation, storage and transmission expansion planning model for Lesotho's electricity system, built with [PyPSA](https://pypsa.org) and [Snakemake](https://snakemake.readthedocs.io). The model was developed at the Energy Research Centre, National University of Lesotho (NUL-ERC), to support analysis for Lesotho's Integrated Resource Plan (IRP).

This repository contains the **code only**. Input data from the Lesotho Electricity Company (LEC) and the Lesotho Highlands Development Authority (LHDA) are restricted and are not included (see [Data](#data)).

---

## What the model does

- Represents the national transmission network (buses, lines, substations) with hourly demand at each substation.
- Solves a linear optimal power flow for each planning year at hourly resolution (8,760 or 8,784 hours).
- Compares supply options under two demand scenarios:

| Supply option | Folder | Description |
|---|---|---|
| Option A (Mission 300 supply) | `A` | Dispatch only. Committed plant at fixed capacity, load shedding at the value of lost load. |
| Option B (Planned generation expansion) | `B` | Co-optimises solar, wind, battery storage and transmission reinforcement, with a reserve margin. Solar and wind may expand up to 1.5 times committed capacity (50% ceiling). |
| Option B, 25% ceiling | `B_RE25` | As Option B, with solar and wind limited to 1.25 times committed capacity (BAU only). |
| Option B, no ceiling | `B_NOCAP` | As Option B, with no upper limit on solar and wind expansion (BAU only). |

| Demand scenario | Growth assumption |
|---|---|
| BAU | 2.35% per year to 2035, then 1.5% per year |
| M300 | 5.35% per year from 2026 to 2030 (universal access by 2030), then 1.5% per year |

Planning years: 2025 to 2030 annually, then 2035, 2040, 2045 and 2050 (set in `config.yaml`).

### Model design notes

- **Independent planning years.** Each planning year is solved as a separate single-year optimisation. The committed fleet in year *t* is existing plant plus pipeline projects with a commissioning year on or before *t*. Capacity built by the model in one year is not carried into the next, so results are a sequence of least-cost snapshot years, not a cumulative build schedule.
- **Expansion rules (Option B).** Solar and wind expand only at sites with committed capacity. Candidate battery storage is sized from zero at candidate buses. Existing lines may be reinforced above their rating. Hydropower and imports are fixed. Nothing expands before 2027.
- **Operational constraints (Option B).** Planning reserve margin (15% above peak load), import limit (220 MW in all hours, lower cap in the 18:00 to 21:59 window), Oxbow daily energy limit, an export option at Mabote from 2027, and rule-based battery operation in the evening peak window.
- **Linearised power flow.** Only active-power constraints are modelled. Reactive power, voltage stability and N-1 security are not.

---

## Workflow

![Workflow](PyPSA_Lesotho_workflow.svg)

| Rule | Script | Output |
|---|---|---|
| `build_network` | `scripts/build_network.py` | `networks/{demand}/{option}/network_{year}.nc` |
| `add_profiles` | `scripts/add_profiles.py` | `networks/{demand}/{option}/profiled_{year}.nc` |
| `assign_costs_B` | `scripts/assign_costs.py` | `networks/{demand}/B/costed_{year}.nc` |
| `solve_option_A` | `scripts/solve_option_A.py` | `networks/{demand}/A/solved_{year}.nc`, `results/{demand}/A/summary_{year}.csv` |
| `solve_option_B` | `scripts/solve_option_B.py` | `networks/{demand}/B/solved_{year}.nc`, `results/{demand}/B/summary_{year}*.csv` |
| `apply_re_ceiling` | `scripts/apply_re_ceiling.py` | `networks/BAU/B_{RE25,NOCAP}/costed_{year}.nc` |
| `solve_option_B_re` | `scripts/solve_option_B.py` | `results/BAU/B_{RE25,NOCAP}/summary_{year}*.csv` |

---

## Requirements

- Python 3.10
- PyPSA, linopy, pandas, numpy, openpyxl
- Snakemake
- A linear programming solver. The scripts are configured for [Gurobi](https://www.gurobi.com) (academic licences are free). HiGHS can be used by changing `solver_name` in the solve scripts.
- For the network map: geopandas, holoviews, geoviews, cartopy, bokeh
- For the workflow diagram: Graphviz

Create the environment:

```bash
conda env create -f environment.yml
conda activate pypsa-LSO
```

---

## Data

The following inputs are required but not included. Paths are relative to the project root.

| File | Contents |
|---|---|
| `data/planned/m300/buses.xlsx` | `BusName`, `Longitude`, `Latitude`, `Voltage` |
| `data/planned/m300/lines.xlsx` | `Line_id`, `bus0`, `bus1`, `r`, `x`, `length`, `capacity_MVA`, `num_parallel`, `v_nom`, `line_status` |
| `data/planned/m300/generators.xlsx` | `generator_id`, `bus`, `capacity_MW`, `carrier`, `plant_status`, `commissioning_year` (0 = existing) |
| `data/planned/m300/storage_units.xlsx` | `name`, `bus`, `carrier`, `p_nom`, `max_hours`, `efficiency_store`, `efficiency_dispatch`, `cyclic_state_of_charge`, `commissioning_year` |
| `data/planned/m300/profiles/{solar,wind,hydro}_ready/*_p_max_pu_{year}.csv` | Hourly availability (per unit) by generator |
| `data/article/load_{BAU,M300}_supply_end/load_timeseries_{year}_supply_end.xlsx` | `Date`, then `<bus>_p` and `<bus>_q` columns (MW, MVAr) |
| `data/planned/m300/costs.xlsx` | Option A: `year`, `carrier`, `marginal_cost` (includes `load_shedding`) |
| `data/planned/processed_costs/generators_costs.csv` | `year`, `Carrier`, `capital_cost` (annualised), `marginal_cost`, `Efficiency` |
| `data/planned/processed_costs/storage_costs.csv` | `year`, `Carrier`, `capital_cost` (annualised), `max_hours`, `efficiency_store`, `efficiency_dispatch` |
| `data/planned/processed_costs/transmission_costs.csv` | `year`, `Investment_usd_per_MW_km`, `FOM_percent_per_year`, `annuity_factor` |

Network, demand, and hydropower data were provided by LEC and LHDA under restricted access. Requests for these data should be directed to the data owners. Cost assumptions are documented in the accompanying paper.

---

## Running the model

From the project root:

```bash
# check what will run
snakemake -j 8 all -n

# all demand scenarios and options
snakemake -j 8 all

# one option for both demands
snakemake -j 8 all_A
snakemake -j 8 all_B

# one demand for both options
snakemake -j 8 all_BAU
snakemake -j 8 all_M300

# renewable ceiling sensitivities (BAU)
snakemake -j 8 all_RE
```

Results are written to `results/{demand}/{option}/` and solved networks to `networks/{demand}/{option}/`.

To regenerate the workflow diagram:

```bash
snakemake all all_RE --forceall --rulegraph > rulegraph.dot
dot -Tsvg rulegraph.dot -o PyPSA_Lesotho_workflow.svg
```

---

## Analysis scripts

Run from the project root after the model has solved.

| Script | Purpose |
|---|---|
| `status_quo_balance.py` | Hourly supply balance for the Central network under the Status Quo (existing solar and hydro, 180 MW import cap) |
| `cost_summary_plots.py` | Annual CAPEX, OPEX, export revenue, net cost and cost per kWh, with BAU and M300 comparison plots |
| `technology_cost_tracker.py` | Excel workbook of capacity and cost by asset and year |
| `cross_scenario_summary.py` | Cross-scenario summary table for 2050 |
| `plot_dispatch_week.py` | Hourly dispatch stack for the peak July week |
| `network_map_line_loading.py` | Interactive network map and line loading-duration table |

Demand scenario preparation:

| Script | Purpose |
|---|---|
| `scale_loads_m300_from_bau.py`, `scale_loads_he_from_bau.py`, `scale_loads_le_from_bau.py` | Scale BAU substation loads to the M300, High Economy and Low Economy scenarios |
| `scale_to_supply_end.py` | Convert demand-side loads to supply-side loads (losses uplift) |
| `compare_scenarios.py` | Annual energy and peak demand comparison across scenarios |

---

## Limitations

- Planning years are solved independently; capacity is not carried forward between years.
- Battery dispatch follows prescribed operating rules rather than price signals.
- Linearised (DC) power flow; no reactive power, voltage or N-1 constraints.
- Line loading is reported as active-power flow relative to the line rating.
- Export revenue depends on an assumed export price and the ability to export the full surplus.

---

## Citation


---

## Licence

[Add licence, e.g. MIT or GPL-3.0]

## Contact

Reabetsoe Sehobai, Energy Research Centre, National University of Lesotho
