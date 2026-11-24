import pypsa
import pandas as pd
import matplotlib.pyplot as plt

# -----------------------------
# LOAD SOLVED NETWORK
# -----------------------------
n = pypsa.Network("networks/planned/solved_2050.nc")

# -----------------------------
# GENERATION ENERGY (MWh)
# -----------------------------
gen_p = n.generators_t.p.copy()          # MW
gen_energy_mwh = gen_p.sum()             # MWh (hourly snapshots)

gen_energy = (
    gen_energy_mwh
    .to_frame(name="MWh")
    .assign(carrier=n.generators.carrier)
    .groupby("carrier")["MWh"]
    .sum()
)

gen_energy_gwh = gen_energy / 1000

# -----------------------------
# LOAD ENERGY (MWh)
# -----------------------------
load_p = n.loads_t.p_set.copy()          # MW
load_energy_mwh = load_p.sum().sum()     # total MWh
load_energy_gwh = load_energy_mwh / 1000

print("=== 2030 ANNUAL ENERGY (GWh) ===")
print(gen_energy_gwh.sort_values(ascending=False))
print("\nTotal load (GWh):", load_energy_gwh)

# -----------------------------
# PREPARE DATA FOR PLOT
# -----------------------------
plot_data = gen_energy_gwh.copy()
plot_data["load"] = load_energy_gwh   # add load as its own bar

# Optional: order bars
order = [
    "solar",
    "wind",
    "hydro",
    "imports",
    "storage",        # if present
    "load_shedding",
    "load"
]

plot_data = plot_data.reindex([c for c in order if c in plot_data.index])

# -----------------------------
# PLOT
# -----------------------------
plt.figure(figsize=(10, 6))

plot_data.plot(
    kind="bar",
    color=[
        "gold",        # solar
        "skyblue",     # wind
        "royalblue",   # hydro
        "firebrick",   # imports
        "purple",      # storage
        "black",       # load shedding
        "grey"         # load
    ][:len(plot_data)],
    edgecolor="black"
)

plt.ylabel("Energy (GWh)")
plt.title("2030 Electricity Supply Mix and Load")
plt.grid(axis="y", alpha=0.3)
plt.xticks(rotation=45, ha="right")

plt.tight_layout()
plt.show()

hydro_gens = n.generators.index[n.generators.carrier == "hydro"]

# dispatched MW
p = n.generators_t.p[hydro_gens]

# available MW = p_nom * p_max_pu
p_nom = n.generators.loc[hydro_gens, "p_nom"]
pmax = n.generators_t.p_max_pu[hydro_gens]
available = pmax.multiply(p_nom, axis=1)

dispatched_gwh = p.sum().sum()/1000
available_gwh = available.sum().sum()/1000
curtailed_gwh = (available - p).clip(lower=0).sum().sum()/1000

print("Hydro dispatched (GWh):", dispatched_gwh)
print("Hydro available (GWh):", available_gwh)
print("Hydro curtailed (GWh):", curtailed_gwh)


import pypsa
import pandas as pd

n = pypsa.Network("networks/planned/solved_2050.nc")

results = []

for carrier in ["solar", "wind", "hydro"]:
    gens = n.generators.index[n.generators.carrier == carrier]
    if gens.empty:
        continue

    p = n.generators_t.p[gens]
    pmax = n.generators_t.p_max_pu[gens]
    p_nom = n.generators.loc[gens, "p_nom"]

    available = pmax.multiply(p_nom, axis=1)
    curtailed = (available - p).clip(lower=0)

    results.append({
        "carrier": carrier,
        "available_GWh": available.sum().sum() / 1000,
        "dispatched_GWh": p.sum().sum() / 1000,
        "curtailed_GWh": curtailed.sum().sum() / 1000,
        "curtailment_%": 100 * curtailed.sum().sum() / available.sum().sum()
    })

curtailment_summary = pd.DataFrame(results).set_index("carrier")
print(curtailment_summary)

curtailment_ts = {}

for carrier in ["solar", "wind", "hydro"]:
    gens = n.generators.index[n.generators.carrier == carrier]
    if gens.empty:
        continue

    p = n.generators_t.p[gens]
    pmax = n.generators_t.p_max_pu[gens]
    p_nom = n.generators.loc[gens, "p_nom"]

    available = pmax.multiply(p_nom, axis=1)
    curtailed = (available - p).clip(lower=0).sum(axis=1)

    curtailment_ts[carrier] = curtailed

curtailment_ts = pd.DataFrame(curtailment_ts)

print(curtailment_ts.describe())

# hours where any curtailment occurs
curtail_hours = curtailment_ts.sum(axis=1)
curtail_hours = curtail_hours[curtail_hours > 1e-3].index

# line loading during those hours
loading = n.lines_t.p0.abs().loc[curtail_hours].divide(
    n.lines.s_nom, axis=1
)

# identify most binding lines
binding_lines = loading.quantile(0.99).sort_values(ascending=False)

print("Top binding lines during curtailment:")
print(binding_lines.head(10))

import pypsa
import pandas as pd

n = pypsa.Network("networks/planned/solved_2050.nc")

# Identify import generators
import_gens = n.generators.index[n.generators.carrier == "imports"]

rows = []

for gen in import_gens:
    bus = n.generators.at[gen, "bus"]
    p_nom = n.generators.at[gen, "p_nom"]

    # Hourly dispatch
    p_ts = n.generators_t.p[gen]

    rows.append({
        "generator": gen,
        "bus": bus,
        "p_nom_MW": p_nom,
        "max_dispatch_MW": p_ts.max(),
        "mean_dispatch_MW": p_ts.mean()
    })

imports_dispatch = pd.DataFrame(rows).set_index("generator")

print("\nIMPORT GENERATOR DISPATCH CHECK (2030)")
print(imports_dispatch)

line_rows = []

for gen in import_gens:
    bus = n.generators.at[gen, "bus"]

    # lines connected to this bus
    lines = n.lines[(n.lines.bus0 == bus) | (n.lines.bus1 == bus)]

    for line, row in lines.iterrows():
        flow = n.lines_t.p0[line].abs().max()

        line_rows.append({
            "import_bus": bus,
            "generator": gen,
            "line": line,
            "line_s_nom_MW": row.s_nom,
            "max_line_flow_MW": flow
        })

line_check = pd.DataFrame(line_rows)

print("\nIMPORT LINES THERMAL CHECK")
print(line_check)


print("Storage units:")
print(n.storage_units[["bus","p_nom","max_hours","marginal_cost","capital_cost","efficiency_store","efficiency_dispatch","cyclic_state_of_charge"]])

su = n.storage_units.index

# Dispatch (+) and store (-) in PyPSA storage_units_t.p
p = n.storage_units_t.p[su]

print("\nMax discharge (MW):", p.max().max())
print("Max charge (MW):", (-p).max().max())
print("Total throughput (MWh):", p.abs().sum().sum())

import pypsa
import pandas as pd
import matplotlib.pyplot as plt

n = pypsa.Network("networks/planned/solved_2050.nc")

gen = n.generators_t.p.groupby(n.generators.carrier, axis=1).sum()

# Storage
p_su = n.storage_units_t.p.sum(axis=1)
storage_discharge = p_su.clip(lower=0)
storage_charge = (-p_su).clip(lower=0)

# Plot one week example
t0 = "2050-01-01"
t1 = "2050-01-08"

ax = gen.loc[t0:t1].plot.area(linewidth=0)
storage_discharge.loc[t0:t1].plot(ax=ax, linewidth=1, label="storage_discharge")
plt.legend()
plt.title("Dispatch including storage discharge")
plt.show()

plt.figure()
storage_charge.loc[t0:t1].plot(linewidth=1, label="storage_charge")
plt.legend()
plt.title("Storage charging (positive = charging MW)")
plt.show()

print(n.storage_units[["bus", "carrier", "p_nom"]])

rule build_base_network:
    input:
        buses="data/Scenario1/buses.xlsx",
        lines="data/Scenario1/lines.xlsx",
        generators="data/Scenario1/generators.xlsx",
        loads="data/load_timeseries_2022_2024.xlsx",
        gen_profiles="data/generator_profiles.xlsx"
    output:
        "results/base/network_2024_status_quo.nc"

    script:
        "scripts/build_base_network.py"