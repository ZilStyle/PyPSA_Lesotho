import logging
import warnings

warnings.filterwarnings("ignore", message=".*were not assigned to the network.*")
logging.getLogger("pypsa.optimization.optimize").setLevel(logging.ERROR)
import pypsa
import pandas as pd
import numpy as np
import os

# -----------------------------
# INPUTS
# -----------------------------
network_file = snakemake.input.network
costs_file = snakemake.input.costs

output_network = snakemake.output.network
output_summary = snakemake.output.summary

year = int(snakemake.wildcards.year)

# -----------------------------
# LOAD NETWORK
# -----------------------------
n = pypsa.Network(network_file)

print(f"Solving Planned scenario for year {year}")

# -----------------------------
# READ COSTS
# -----------------------------
costs = pd.read_excel(costs_file)

# sanity
required_cols = {"year", "carrier", "marginal_cost"}
missing = required_cols - set(costs.columns)
if missing:
    raise ValueError(f"Missing columns in costs.xlsx: {missing}")

costs_year = costs[costs["year"] == year]

if costs_year.empty:
    raise ValueError(f"No cost data found for year {year}")

# -----------------------------
# APPLY MARGINAL COSTS
# -----------------------------
for _, row in costs_year.iterrows():
    carrier = row["carrier"]
    mc = row["marginal_cost"]

    if carrier in n.generators.carrier.values:
        n.generators.loc[
            n.generators.carrier == carrier, "marginal_cost"
        ] = mc

# -----------------------------
# ENSURE OPTION A (NO EXPANSION)
# -----------------------------
n.generators["p_nom_extendable"] = False
if not n.storage_units.empty:
    n.storage_units["p_nom_extendable"] = False

# -----------------------------
# ADD LOAD SHEDDING
# -----------------------------
voll = float(
    costs_year.loc[costs_year.carrier == "load_shedding", "marginal_cost"].iloc[0]
)

for bus in n.buses.index:
    ls = f"LoadShedding_{bus}"
    if ls not in n.generators.index:
        n.add(
            "Generator",
            name=ls,
            bus=bus,
            carrier="load_shedding",
            p_nom_extendable=True,
            marginal_cost=voll
        )


# -------------------------------------------------
# DEFINE CARRIERS (LINES, GENERATORS, BUSES)
# -------------------------------------------------

all_carriers = set()

if "carrier" in n.lines.columns:
    all_carriers |= set(n.lines.carrier.dropna().unique())

if "carrier" in n.generators.columns:
    all_carriers |= set(n.generators.carrier.dropna().unique())

if "carrier" in n.buses.columns:
    all_carriers |= set(n.buses.carrier.dropna().unique())

if not n.storage_units.empty and "carrier" in n.storage_units.columns:
    all_carriers |= set(n.storage_units.carrier.dropna().unique())

if "hydro_peaking" not in n.carriers.index:
    n.add("Carrier", "hydro_peaking")


for c in all_carriers:
    if c not in n.carriers.index:
        n.add("Carrier", name=c)


def add_oxbow_daily_energy_limit(n, sns):
    model = n.model

    if "Oxbow" not in n.generators.index:
        return

    ox = "Oxbow"
    snapshots = pd.Index(sns)

    # Group snapshots by day
    days = snapshots.normalize().unique()

    for day in days:
        idx = snapshots[snapshots.normalize() == day]

        model.add_constraints(
            model.variables["Generator-p"].loc[idx, ox].sum()
            <= 90 * 7,
            name=f"oxbow_daily_energy_{day.date()}"
        )


# -----------------------------
# SOLVE
# -----------------------------
n.optimize(
    solver_name="gurobi",
    solver_options={"Threads":8,
                    "Method":2,
                    "Crossover":0,
                    "Seed":42},
    extra_functionality=add_oxbow_daily_energy_limit
)
# ---------------------------------------
# SAVE OBJECTIVE VALUE
# ---------------------------------------
objective_value = n.objective

objective_df = pd.DataFrame({
    "year": [year],
    "objective_cost": [objective_value]
})

objective_file = output_summary.replace(".csv", "_objective.csv")
objective_df.to_csv(objective_file, index=False)

print(f"Objective cost saved: {objective_value}")



# -----------------------------
# COST BREAKDOWN
# -----------------------------
print("Extracting cost breakdown")

dispatch = n.generators_t.p
mc = n.generators.marginal_cost

energy_MWh = dispatch.sum()
costs_by_gen = energy_MWh * mc

costs_by_carrier = (
    costs_by_gen
    .groupby(n.generators.carrier)
    .sum()
)

energy_by_carrier = (
    energy_MWh
    .groupby(n.generators.carrier)
    .sum() / 1e3
)

summary = pd.DataFrame({
    "year": year,
    "energy_GWh": energy_by_carrier,
    "operating_cost": costs_by_carrier
}).reset_index().rename(columns={"index": "carrier"})

summary.to_csv(output_summary, index=False)

# -----------------------------
# SAVE NETWORK
# -----------------------------
os.makedirs(os.path.dirname(output_network), exist_ok=True)
n.export_to_netcdf(output_network)

print("Planned scenario solved successfully")
