import pypsa
import sys
from pathlib import Path


# Add project root using Snakemake context (robust on Windows)
PROJECT_ROOT = Path(snakemake.scriptdir).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
import numpy as np
import os


# -----------------------------
# SNAKEMAKE INPUTS
# -----------------------------
buses_file      = snakemake.input.buses
lines_file      = snakemake.input.lines
generators_file = snakemake.input.generators
storage_file    = snakemake.input.storage
loads_file      = snakemake.input.loads

output_file = snakemake.output[0]

# Planning year and scenario
year     = int(snakemake.wildcards.year)
scenario = snakemake.params.get("scenario", "A").upper()

print(f"Building network for year {year} | Scenario Option {scenario}")

# -----------------------------
# CREATE NETWORK
# -----------------------------
n = pypsa.Network()

# -----------------------------
# READ STATIC DATA
# -----------------------------
buses       = pd.read_excel(buses_file)
lines       = pd.read_excel(lines_file)
generators  = pd.read_excel(generators_file)
storage_df  = pd.read_excel(storage_file, sheet_name="Sheet1")

# -----------------------------
# ADD BUSES
# -----------------------------
print("Adding buses")

for _, row in buses.iterrows():
    n.add(
        "Bus",
        name=str(row["BusName"]).strip(),
        x=float(row["Longitude"]),
        y=float(row["Latitude"]),
        v_nom=float(row["Voltage"])
    )

# -----------------------------
# ADD LINES (OPTION A SAFE)
# -----------------------------
print("Adding lines")

for _, row in lines.iterrows():
    n.add(
        "Line",
        name=row["Line_id"],
        bus0=row["bus0"],
        bus1=row["bus1"],
        r=row["r"],
        x=row["x"],
        length=row["length"],
        s_nom=row["capacity_MVA"],
        s_nom_extendable=False,               # Option A default
        s_nom_min=row["capacity_MVA"],        # prevent shrinking
        num_parallel=row["num_parallel"],
        v_nom=row["v_nom"],
        line_status=row["line_status"]
    )

# -----------------------------
# ADD GENERATORS (COMMISSIONING LOGIC)
# -----------------------------
print("Adding generators")

for _, row in generators.iterrows():

    commission = row.get("commissioning_year", 0)
    if pd.isna(commission):
        commission = 0

    if commission != 0 and year < int(commission):
        continue

    n.add(
        "Generator",
        name=row["generator_id"],
        bus=row["bus"],
        carrier=row["carrier"],
        p_nom=row["capacity_MW"],
        p_nom_extendable=False,               # Option A default
        plant_status=row["plant_status"]
    )

# -----------------------------
# ADD STORAGE UNITS (TOPOLOGY ONLY)
# -----------------------------
print("Adding storage units")

for _, row in storage_df.iterrows():

    if row["commissioning_year"] > year:
        continue

    if row["name"] in n.storage_units.index:
        continue

    n.add(
        "StorageUnit",
        name=row["name"],
        bus=row["bus"],
        carrier=row["carrier"],
        p_nom=row["p_nom"],
        max_hours=row["max_hours"],
        efficiency_store=row["efficiency_store"],
        efficiency_dispatch=row["efficiency_dispatch"],
        cyclic_state_of_charge=bool(row["cyclic_state_of_charge"]),
        p_nom_extendable=False                # Option A default
    )

print(f"Storage units added: {len(n.storage_units)}")

# -----------------------------
# PROCESS LOAD TIMESERIES
# -----------------------------
print("Processing load timeseries")

load_ts = pd.read_excel(loads_file, sheet_name="Sheet1")
load_ts["Date"] = pd.to_datetime(load_ts["Date"], errors="coerce").dt.round("h")
load_ts = load_ts.dropna(subset=["Date"])

# enforce same-year snapshots
load_ts = load_ts[load_ts["Date"].dt.year == year]
if load_ts.empty:
    raise ValueError(f"No load data found for year {year}")

n.set_snapshots(load_ts["Date"])

# -----------------------------
# ADD LOADS
# -----------------------------
print("Adding loads")

# case-insensitive, whitespace-tolerant match between load columns and bus names
bus_lookup = {b.strip().lower(): b for b in n.buses.index}

for col in load_ts.columns:

    if not (col.endswith("_p") or col.endswith("_q")):
        continue

    bus = bus_lookup.get(col[:-2].strip().lower())

    if bus is None:
        print(f"WARNING: load column '{col}' has no matching bus, skipped")
        continue

    if bus not in n.loads.index:
        n.add("Load", name=bus, bus=bus)

    if col.endswith("_p"):
        n.loads_t.p_set[bus] = load_ts[col].values
    else:
        n.loads_t.q_set[bus] = load_ts[col].values

print(f"Loads added: {len(n.loads)} | total energy: {n.loads_t.p_set.sum().sum() / 1000:,.1f} GWh")

# -----------------------------
# OPTION B: APPLY COSTS & EXPANSION
# -----------------------------
if scenario == "B":
    print("Applying Option B expansion and cost logic")

    from scripts.assign_costs import (
        assign_generator_costs,
        assign_storage_costs,
        assign_transmission_costs
    )

    assign_generator_costs(n, year)
    assign_storage_costs(n, year)
    assign_transmission_costs(n, year)

# -----------------------------
# FINAL SANITY CHECKS
# -----------------------------
print("Final sanity checks")

assert not n.buses.empty, "No buses in network"
assert not n.lines.empty, "No lines in network"
assert not n.generators.empty, "No generators in network"

if scenario == "B":
    assert n.generators.p_nom_extendable.any(), "No extendable generators in Option B"
    assert n.lines.s_nom_extendable.any(), "No extendable lines in Option B"
    assert n.storage_units.p_nom_extendable.any(), "No extendable storage in Option B"
    assert not n.generators.loc[
        n.generators.carrier == "imports", "p_nom_extendable"
    ].any(), "Imports must not be extendable"

# -----------------------------
# SAVE NETWORK
# -----------------------------
os.makedirs(os.path.dirname(output_file), exist_ok=True)

print(f"Saving network: {output_file}")
n.export_to_netcdf(output_file)