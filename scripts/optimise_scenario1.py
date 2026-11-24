import pypsa
import pandas as pd
import numpy as np

# =====================================================
# CONFIG
# =====================================================
NETWORK_FILE = "results/scenario1/network_2025.nc"
GEN_PROFILES_FILE = "data/generator_profiles_scenario1/generator_profiles_scenario1_2025.xlsx"
GEN_PROFILES_SHEET = "Sheet2"   # change to your sheet name if needed
OUTPUT_CSV = "results/scenario1/balance_2025_unmet_demand.csv"

# Names in the generator profiles file
SOLAR_GEN = "Ramarothole"
HYDRO_GEN = "Muela"
IMPORT_GEN = "Maseru bulk"

# =====================================================
# 1. Load network to get loads
# =====================================================
print(f"Loading network from {NETWORK_FILE}")
n = pypsa.Network(NETWORK_FILE)
print(f"Snapshots in network: {len(n.snapshots)}")

# Total load per hour [MW]
# Assumes n.loads_t.p_set is in MW for each bus
load_series = n.loads_t.p_set.sum(axis=1)
load_series.name = "load_MW"

print("\nLoad series sample:")
print(load_series.head())

# =====================================================
# 2. Load generator profiles for 2025
# =====================================================
print(f"\nLoading generator profiles from {GEN_PROFILES_FILE}")
df_gen = pd.read_excel(GEN_PROFILES_FILE, sheet_name=GEN_PROFILES_SHEET)

if "Date" not in df_gen.columns:
    raise ValueError(f"'Date' column not found in {GEN_PROFILES_FILE}")

df_gen["Date"] = pd.to_datetime(df_gen["Date"], errors="coerce")
df_gen = df_gen.dropna(subset=["Date"])

# If file has more than one year, restrict to 2025
df_gen["year"] = df_gen["Date"].dt.year
df_gen = df_gen[df_gen["year"] == 2025].copy()
df_gen = df_gen.set_index("Date")
df_gen = df_gen.sort_index()

print("\nGenerator profiles columns:")
print(df_gen.columns.tolist())

# Align to network snapshots
df_gen = df_gen.reindex(n.snapshots)
if df_gen.isna().any().any():
    print("Warning: NaNs found after reindexing generator profiles, filling forward then zero.")
    df_gen = df_gen.ffill().fillna(0.0)

# Extract series for each generator
def get_gen_series(name):
    if name not in df_gen.columns:
        raise ValueError(f"Generator '{name}' not found in profile file columns.")
    s = df_gen[name].astype(float)
    s.name = name
    return s

solar_series = get_gen_series(SOLAR_GEN)
hydro_series = get_gen_series(HYDRO_GEN)
imports_series = get_gen_series(IMPORT_GEN)

print("\nSample of generator profiles:")
print(pd.concat([solar_series, hydro_series, imports_series], axis=1).head())

# Sanity check for imports cap
max_import = imports_series.max()
print(f"\nMaximum imports value in profiles: {max_import:.2f} MW")
if max_import > 180.0 + 1e-6:
    print("Warning: imports profile exceeds 180 MW. You said it should be capped.")

# =====================================================
# 3. Compute unmet demand
# =====================================================
supply_total = solar_series + hydro_series + imports_series
supply_total.name = "total_supply_MW"

unmet = load_series - supply_total
unmet = unmet.clip(lower=0.0)
unmet.name = "unmet_demand_MW"

balance_df = pd.concat(
    [
        load_series,
        solar_series.rename("solar_MW"),
        hydro_series.rename("hydro_MW"),
        imports_series.rename("imports_MW"),
        unmet,
    ],
    axis=1,
)

print("\nBalance sample:")
print(balance_df.head())

print("\nTotal annual values [MWh if hourly time step]:")
print(balance_df.sum())

# =====================================================
# 4. Save to CSV
# =====================================================
balance_df.to_csv(OUTPUT_CSV, index_label="snapshot")
print(f"\nSaved hourly balance and unmet demand to {OUTPUT_CSV}")
