import pypsa
import pandas as pd
import numpy as np
import os

# Snakemake inputs
buses_file = snakemake.input.buses
lines_file = snakemake.input.lines
generators_file = snakemake.input.generators
loads_file = snakemake.input.loads
gen_profiles_file = snakemake.input.gen_profiles

output_file = snakemake.output[0]

# Create network
network = pypsa.Network()

print("Reading Excel files")

buses = pd.read_excel(buses_file)
lines = pd.read_excel(lines_file)
generators = pd.read_excel(generators_file)

print("Adding buses")
for _, row in buses.iterrows():
    network.add("Bus",
                name=row["BusName"],
                x=row["Longitude"],
                y=row["Latitude"],
                v_nom=row["Voltage"],
                bus_status=row["bus_status"])

print("Adding lines")
for _, row in lines.iterrows():
    network.add("Line",
                name=row["Line_id"],
                bus0=row["bus0"],
                bus1=row["bus1"],
                x=row["x"],
                r=row["r"],
                length=row['length'],
                s_nom=row["capacity_MVA"],
                num_parallel=row["num_parallel"],
                v_nom=row["v_nom"],
                line_status=row["line_status"])

print("Adding static generators")
for _, row in generators.iterrows():
    network.add(
        "Generator",
        name=row["generator_id"],
        bus=row["bus"],
        carrier=row["carrier"],
        p_nom=row["capacity_MW"],
        p_nom_extendable=False,
        plant_status=row["plant_status"]
    )


# -------- LOAD TIMESERIES PROCESSING -------- #

print("Processing load timeseries")
load_ts = pd.read_excel(loads_file, sheet_name="Sheet2")

if "Date" not in load_ts.columns:
    raise ValueError(f"Expected timestamp column 'Date' not found. Available: {list(load_ts.columns)}")

load_ts["Date"] = pd.to_datetime(load_ts["Date"], errors="coerce").dt.round("h")
load_ts = load_ts.dropna(subset=["Date"])
load_ts["year"] = load_ts["Date"].dt.year

load_2024 = load_ts[load_ts["year"] == 2024]
if load_2024.empty:
    raise ValueError("No load rows found for 2024.")

print(f"Rows for 2024: {len(load_2024)}")

snapshots = pd.to_datetime(load_2024["Date"])
network.set_snapshots(snapshots)

print("Adding loads")
for col in load_2024.columns:
    if col.endswith("_p"):
        bus = col[:-2].strip()
        if bus in network.buses.index:
            if bus not in network.loads.index:
                network.add("Load", name=bus, bus=bus)
            network.loads_t.p_set[bus] = load_2024[col].values
    elif col.endswith("_q"):
        bus = col[:-2].strip()
        if bus in network.buses.index:
            if bus not in network.loads.index:
                network.add("Load", name=bus, bus=bus)
            network.loads_t.q_set[bus] = load_2024[col].values

# -------- GENERATOR PROFILES CLEAN BLOCK -------- #

print("Assigning generator profiles")

profiles = pd.read_excel(gen_profiles_file, sheet_name="Sheet2")
profiles["Date"] = pd.to_datetime(profiles["Date"], errors="coerce").dt.round("h")
profiles = profiles[profiles["Date"].dt.year == 2024]
profiles = profiles.set_index("Date")
profiles = profiles.reindex(network.snapshots)
profiles = profiles.ffill().fillna(0)

for gen_id in network.generators.index: 
    if gen_id in profiles.columns: 
        print(f"Applying profile for generator {gen_id}") 
        network.generators_t.p_set[gen_id] = profiles[gen_id].values 
    else: 
        print(f"No profile found for generator {gen_id}, setting to zero") 
        network.generators_t.p_set[gen_id] = 0


# -------- SAVE NETWORK -------- #

output_dir = os.path.dirname(output_file)
os.makedirs(output_dir, exist_ok=True)

print("Saving network:", output_file)
network.export_to_netcdf(output_file)
