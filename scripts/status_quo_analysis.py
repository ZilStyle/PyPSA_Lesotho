import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# --------------------------------------
# SETTINGS
# --------------------------------------
PLANNING_YEARS = [2025, 2026, 2027, 2028, 2029, 2030, 2035, 2040, 2045, 2050]

LOAD_DIR = "data/Scenario1/load_BAU_supply_end"
GEN_DIR = "data/generator_profiles_scenario1"
OUT_DIR = "results/unmet_demand_BAU"
os.makedirs(OUT_DIR, exist_ok=True)

# --------------------------------------
# HELPERS
# --------------------------------------

def sum_load(df_load):
    """Sum all *_p columns to get system load."""
    p_cols = [c for c in df_load.columns if c.endswith("_p")]
    return df_load[p_cols].sum(axis=1)


def extract_gen(df_gen, names):
    """Sum selected generator columns if they exist."""
    cols = [c for c in names if c in df_gen.columns]
    if not cols:
        return pd.Series(0.0, index=df_gen.index)
    return df_gen[cols].sum(axis=1)


# --------------------------------------
# MAIN LOOP
# --------------------------------------

for year in PLANNING_YEARS:
    print(f"\n=== Processing {year} ===")

    # ------------------------
    # Load scaled load
    # ------------------------
    load_file = f"{LOAD_DIR}/load_timeseries_{year}_supply_end.xlsx"
    if not os.path.exists(load_file):
        raise FileNotFoundError(load_file)

    df_load = pd.read_excel(load_file, sheet_name="Sheet1") #sheet2 to for isolated networks
    df_load["Date"] = pd.to_datetime(df_load["Date"])
    df_load = df_load.set_index("Date").sort_index()

    load_ts = sum_load(df_load)

    # ------------------------
    # Load generator profiles
    # ------------------------
    gen_file = f"{GEN_DIR}/generator_profiles_scenario1_{year}.xlsx"
    if not os.path.exists(gen_file):
        raise FileNotFoundError(gen_file)

    df_gen = pd.read_excel(gen_file, sheet_name="Sheet2") #sheet 3 for isolated networks
    df_gen["Date"] = pd.to_datetime(df_gen["Date"])
    df_gen = df_gen.set_index("Date").sort_index()

    # Detect generator names automatically
    solar_gens = [c for c in df_gen.columns if "Ramarothole" in c]
    hydro_gens = [c for c in df_gen.columns if "Muela" in c]
    import_gens = [c for c in df_gen.columns if "Maseru bulk" in c]

    solar_ts = extract_gen(df_gen, solar_gens)
    hydro_ts = extract_gen(df_gen, hydro_gens)
    import_ts = extract_gen(df_gen, import_gens)

    # ------------------------
    # Compute unmet demand
    # ------------------------
    unmet = load_ts - solar_ts - hydro_ts - import_ts
    unmet = unmet.clip(lower=0)

    df_out = pd.DataFrame({
        "load": load_ts,
        "solar": solar_ts,
        "hydro": hydro_ts,
        "imports": import_ts,
        "unmet": unmet
    })

    # Save hourly results
    hourly_csv = f"{OUT_DIR}/unmet_demand_hourly_{year}.csv"
    df_out.to_csv(hourly_csv)
    print("Saved:", hourly_csv)

    # ------------------------
    # Monthly totals (MWh)
    # ------------------------
    df_month = df_out.resample("M").sum()
    monthly_csv = f"{OUT_DIR}/unmet_demand_monthly_{year}.csv"
    df_month.to_csv(monthly_csv)
    print("Saved:", monthly_csv)

    # ------------------------
    # Plot monthly stack
    # ------------------------
    plt.figure(figsize=(12,6))
    plt.stackplot(
        df_month.index,
        df_month["solar"],
        df_month["hydro"],
        df_month["imports"],
        df_month["unmet"],
        labels=["Solar", "Hydro", "Imports", "Unmet demand"]
    )
    plt.title(f"Monthly Energy Supply Mix and Unmet Demand, {year}")
    plt.ylabel("MWh")
    plt.legend(loc="upper left")
    plt.grid(True, alpha=0.3)

    plot_file = f"{OUT_DIR}/monthly_stack_{year}.png"
    plt.savefig(plot_file, dpi=200)
    plt.close()
    print("Saved:", plot_file)

print("\nAll years processed.")
