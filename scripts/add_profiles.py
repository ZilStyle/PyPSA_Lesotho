import pypsa
import pandas as pd
import os

# -----------------------------
# INPUTS FROM SNAKEMAKE
# -----------------------------
network_file = snakemake.input.network
solar_file   = snakemake.input.solar
wind_file    = snakemake.input.wind
hydro_file   = snakemake.input.hydro

output_file  = snakemake.output[0]

# -----------------------------
# LOAD NETWORK
# -----------------------------
n = pypsa.Network(network_file)

print("Loading generator profiles")

# -----------------------------
# PROFILE LOADERS
# -----------------------------
def load_profile(path, dayfirst=False):
    df = pd.read_csv(path) if path.endswith(".csv") else pd.read_excel(path)

    df["Date"] = pd.to_datetime(
        df["Date"],
        dayfirst=dayfirst,
        errors="coerce"
    ).dt.round("h")

    df = df.dropna(subset=["Date"])
    df = df.drop_duplicates(subset=["Date"])
    df = df.set_index("Date")

    # Strict alignment to network snapshots
    df = df.reindex(n.snapshots)

    return df.ffill().fillna(0.0)

# -----------------------------
# LOAD PROFILES
# -----------------------------
solar = load_profile(solar_file, dayfirst=True)
hydro = load_profile(hydro_file, dayfirst=True)
wind  = load_profile(wind_file,  dayfirst=False)

# -----------------------------
# INITIALISE p_max_pu
# -----------------------------
# Default = fully available unless constrained by profile
n.generators_t.p_max_pu = pd.DataFrame(
    1.0,
    index=n.snapshots,
    columns=n.generators.index
)

# =================================================
# SOLAR (CF broadcast)
# =================================================
solar_cf = solar.iloc[:, 0].astype(float).clip(0.0, 1.0)
solar_gens = n.generators.index[n.generators.carrier == "solar"]

for gen in solar_gens:
    n.generators_t.p_max_pu.loc[:, gen] = solar_cf.values

# =================================================
# WIND (CF broadcast)
# =================================================
wind_cf = wind.iloc[:, 0].astype(float).clip(0.0, 1.0)
wind_gens = n.generators.index[n.generators.carrier == "wind"]

for gen in wind_gens:
    n.generators_t.p_max_pu.loc[:, gen] = wind_cf.values


print("CSV rows:", len(wind))
print("Network snapshots:", len(n.snapshots))

print("Mean CF from CSV:", wind.iloc[:,0].mean())
print("Mean CF after alignment:", wind.reindex(n.snapshots).iloc[:,0].mean())

# =================================================
# HYDRO (WATER-LIMITED, EXCLUDING OXBOW)
# =================================================
hydro_cf = hydro.iloc[:, 0].astype(float).clip(0.0, 1.0)

# IMPORTANT: exclude Oxbow here
hydro_gens = n.generators.index[
    (n.generators.carrier == "hydro") &
    (n.generators.index != "Oxbow")
]

for gen in hydro_gens:
    n.generators_t.p_max_pu.loc[:, gen] = hydro_cf.values

# =================================================
# OXBOW PEAKING HYDRO (TIME-RESTRICTED ONLY)
# =================================================
if "Oxbow" in n.generators.index:

    hours = n.snapshots.hour

    oxbow_mask = (
        ((hours >= 7) & (hours <= 10)) |   # 07:00–10:00 (4 hrs)
        ((hours >= 18) & (hours < 21))   # 18:00–21:00 (3 hrs)
    ).astype(float)

    n.generators_t.p_max_pu.loc[:, "Oxbow"] = oxbow_mask

# -----------------------------
# SUMMARY
# -----------------------------
print("Profiles assigned:")
print(f"  Solar generators : {len(solar_gens)} (day-first dates)")
print(f"  Wind generators  : {len(wind_gens)} (day-first dates)")
print(f"  Hydro generators : {len(hydro_gens)} (water-limited)")
print(f"  Oxbow peaking    : {'enabled' if 'Oxbow' in n.generators.index else 'not present'}")


print("Assigned wind CF:", n.generators_t.p_max_pu[wind_gens].mean().mean())

# -----------------------------
# SAVE NETWORK
# -----------------------------
os.makedirs(os.path.dirname(output_file), exist_ok=True)
print("Saving profiled network:", output_file)
n.export_to_netcdf(output_file)
