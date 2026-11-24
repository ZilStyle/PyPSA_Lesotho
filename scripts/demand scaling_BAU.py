import pandas as pd
import numpy as np
import os
import calendar

# ===============================
# INPUTS
# ===============================
FILE = "data/load_timeseries_2022_2024.xlsx"
OUTPUT_DIR = "data/Scaled_loads_BAU"
os.makedirs(OUTPUT_DIR, exist_ok=True)

PLANNING_YEARS = [2025, 2026, 2027, 2028, 2029, 2030, 2035, 2040, 2045, 2050]

ANCHOR_YEAR = 2024
TRANSITION_END_YEAR = 2035
TRANSITION_GROWTH = 0.0235   # 2.35% per year, 2025 to 2030 (historical rate)
MATURE_GROWTH = 0.015        # 1.5% per year, 2031 to 2050

# ===============================
# STEP 1: LOAD DATA
# ===============================
df = pd.read_excel(FILE, sheet_name="Sheet1")

df["Date"] = pd.to_datetime(df["Date"], errors="coerce").dt.round("h")
df = df.dropna(subset=["Date"])
df["year"] = df["Date"].dt.year

# ===============================
# STEP 2: IDENTIFY SUBSTATIONS
# ===============================
p_cols = [c for c in df.columns if c.endswith("_p")]
q_cols = [c for c in df.columns if c.endswith("_q")]

substations = [c[:-2] for c in p_cols]   # strip only the "_p" suffix

print("Substations detected:")
print(substations)

# ===============================
# STEP 3: CALCULATE ANNUAL ENERGY
# ===============================
annual_energy = {}

for sub in substations:
    p_col = f"{sub}_p"
    annual_energy[sub] = df.groupby("year")[p_col].sum()

annual_df = pd.DataFrame(annual_energy)

print("\nAnnual energy table (raw sums):")
print(annual_df)

# ===============================
# STEP 4: TARGET ANNUAL ENERGY PER SUBSTATION
# ===============================
def growth_factor(year):
    """Annual energy relative to ANCHOR_YEAR: 2.35% per year to 2030, then 1.5% per year."""
    n_transition = min(year, TRANSITION_END_YEAR) - ANCHOR_YEAR
    n_mature = max(year - TRANSITION_END_YEAR, 0)
    return (1 + TRANSITION_GROWTH) ** n_transition * (1 + MATURE_GROWTH) ** n_mature


e24 = annual_df.loc[ANCHOR_YEAR]                      # 2024 annual energy per substation
target_df = pd.DataFrame({year: e24 * growth_factor(year) for year in PLANNING_YEARS}).T
target_df.index.name = "year"

print("\nTarget annual energy per substation:")
print(target_df)

# ===============================
# STEP 5: GENERATE FUTURE YEARS
# ===============================
summary = []

for year in PLANNING_YEARS:

    is_leap = calendar.isleap(year)
    base_year = 2024 if is_leap else 2023

    print(f"\n=== Building {year} using {base_year} hourly profile ===")

    df_base = df[df["year"] == base_year].drop(columns=["year"])
    # collapse duplicate timestamps from rounding, then force a complete hourly
    # index so missing hours cannot shift the profile against the calendar
    df_base = df_base.groupby("Date").mean(numeric_only=True)
    full_idx = pd.date_range(f"{base_year}-01-01 00:00", f"{base_year}-12-31 23:00", freq="h")
    n_missing = len(full_idx.difference(df_base.index))
    df_base = df_base.reindex(full_idx).interpolate(limit_direction="both")
    if n_missing:
        print(f"  {n_missing} missing hours in {base_year} filled by interpolation")

    # ------------------------------------
    # Create correct hourly time index
    # ------------------------------------
    new_dates = pd.date_range(
        start=f"{year}-01-01 00:00",
        end=f"{year}-12-31 23:00",
        freq="h"
    )

    df_base = df_base.reset_index(drop=True)
    df_base.insert(0, "Date", new_dates)
    e_profile = df_base[p_cols].sum()          # energy of the (filled) profile actually scaled
    # ------------------------------------

    for sub in substations:
        p_col = f"{sub}_p"
        q_col = f"{sub}_q"

        # Scale factor = target annual energy / annual energy of the profile used
        e_target = target_df.loc[year, sub]
        e_base = e_profile[p_col]
        scale = 0.0 if e_base == 0 else e_target / e_base

        if p_col in df_base.columns:
            df_base[p_col] *= scale
        if q_col in df_base.columns:
            df_base[q_col] *= scale          # same factor keeps the power factor unchanged

    df_base.to_csv(os.path.join(OUTPUT_DIR, f"load_timeseries_{year}.csv"), index=False)

    p_total = df_base[p_cols].sum(axis=1)
    summary.append({
        "year": year,
        "growth_factor": growth_factor(year),
        "energy_sum_p": p_total.sum(),
        "peak_p": p_total.max(),
    })

summary_df = pd.DataFrame(summary).set_index("year")
summary_df.to_csv(os.path.join(OUTPUT_DIR, "summary.csv"))

print("\nSystem summary:")
print(summary_df)
print("\nDemand timeseries generation complete.")