import pandas as pd
from pathlib import Path

# =========================================================
# PATHS
# =========================================================
# Folder written by the BAU script (load_timeseries_<year>.csv)
BASE_DIR = Path(r"C:\Users\USER\pypsa-lesotho\data\Scaled_loads_BAU")
OUT_DIR  = Path(r"C:\Users\USER\pypsa-lesotho\data\Scaled_loads_M300")

OUT_DIR.mkdir(parents=True, exist_ok=True)

# =========================================================
# YEARS
# =========================================================
ANCHOR_YEAR   = 2025
RAMP_END_YEAR = 2030                     # 5.35% growth runs up to and including 2030

RAMP_YEARS   = [2026, 2027, 2028, 2029, 2030]
MATURE_YEARS = [2035, 2040, 2045, 2050]

# =========================================================
# GROWTH ASSUMPTIONS
# =========================================================
BASELINE_CAGR = 0.0235
UPLIFT        = 0.03
M300_GROWTH   = BASELINE_CAGR + UPLIFT   # 5.35%
MATURE_GROWTH = 0.015                    # 1.5%

# =========================================================
# HELPER FUNCTIONS
# =========================================================
def load_file(year):
    """Read the BAU file for a year: CSV first, xlsx as fallback."""
    csv = BASE_DIR / f"load_timeseries_{year}.csv"
    xlsx = BASE_DIR / f"load_timeseries_{year}.xlsx"

    if csv.exists():
        df = pd.read_csv(csv, parse_dates=["Date"])
    elif xlsx.exists():
        df = pd.read_excel(xlsx, sheet_name="Sheet1")
    else:
        print(f"{year}: not found in {BASE_DIR}")
        return None

    df.columns = (
        df.columns.astype(str)
        .str.strip()
        .str.replace(r"\s+", " ", regex=True)
    )
    return df


def get_pq_columns(df):
    p_cols = [c for c in df.columns if c.lower().endswith("_p")]
    q_cols = [c for c in df.columns if c.lower().endswith("_q")]

    if not p_cols:
        raise ValueError("No _p columns detected")

    return p_cols, q_cols


def annual_energy_gwh(df, p_cols):
    system_p = df[p_cols].sum(axis=1, skipna=True)
    return float(system_p.sum() / 1000)


def scale_and_save(df, year, scale_factor):
    """Scale P and Q by the same factor (keeps power factor) and save."""
    p_cols, q_cols = get_pq_columns(df)

    df = df.copy()
    df[p_cols] *= scale_factor
    if q_cols:
        df[q_cols] *= scale_factor

    out = OUT_DIR / f"load_timeseries_{year}.xlsx"
    df.to_excel(out, sheet_name="Sheet1", index=False)
    return annual_energy_gwh(df, p_cols)


summary = []

# =========================================================
# STEP 1: ANCHOR AT 2025 (M300 = BAU in 2025)
# =========================================================
df_2025 = load_file(ANCHOR_YEAR)
if df_2025 is None:
    raise FileNotFoundError(f"2025 anchor file missing in {BASE_DIR}")

p_cols_2025, _ = get_pq_columns(df_2025)
E_2025 = annual_energy_gwh(df_2025, p_cols_2025)

scale_and_save(df_2025, ANCHOR_YEAR, 1.0)
summary.append({"year": ANCHOR_YEAR, "target_gwh": E_2025, "scale": 1.0})
print(f"Anchor energy E_2025 = {E_2025:.3f} GWh (saved unchanged)\n")

# =========================================================
# STEP 2: M300 RAMP-UP (2026-2030), 5.35% per year
# =========================================================
for year in RAMP_YEARS:
    df = load_file(year)
    if df is None:
        continue

    target = E_2025 * (1 + M300_GROWTH) ** (year - ANCHOR_YEAR)

    p_cols, _ = get_pq_columns(df)
    current = annual_energy_gwh(df, p_cols)

    scale = target / current
    scale_and_save(df, year, scale)
    summary.append({"year": year, "target_gwh": target, "scale": scale})

    print(f"{year}: target={target:.3f} GWh, scale={scale:.4f}")

# M300 energy at the end of the ramp (2030), the starting point for mature growth
E_RAMP_END = E_2025 * (1 + M300_GROWTH) ** (RAMP_END_YEAR - ANCHOR_YEAR)

# =========================================================
# STEP 3: MATURE M300 GROWTH (2031-2050), 1.5% per year
# =========================================================
for year in MATURE_YEARS:
    df = load_file(year)
    if df is None:
        continue

    target = E_RAMP_END * (1 + MATURE_GROWTH) ** (year - RAMP_END_YEAR)

    p_cols, _ = get_pq_columns(df)
    current = annual_energy_gwh(df, p_cols)

    scale = target / current
    scale_and_save(df, year, scale)
    summary.append({"year": year, "target_gwh": target, "scale": scale})

    print(f"{year}: target={target:.3f} GWh, scale={scale:.4f}")

summary_df = pd.DataFrame(summary).set_index("year")
summary_df.to_csv(OUT_DIR / "summary_m300.csv")

print("\nMission 300 demand scaling complete.")
print(summary_df.round(4))
print(f"Output folder: {OUT_DIR}")