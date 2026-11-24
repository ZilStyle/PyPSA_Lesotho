import pandas as pd
from pathlib import Path

# =========================================================
# PATHS
# =========================================================
# Folder written by the BAU script (load_timeseries_<year>.csv or .xlsx)
BASE_DIR = Path(r"C:\Users\USER\pypsa-lesotho\data\Scaled_loads_BAU")
OUT_DIR  = Path(r"C:\Users\USER\pypsa-lesotho\data\Scaled_loads_LE")

OUT_DIR.mkdir(parents=True, exist_ok=True)

# =========================================================
# YEARS
# =========================================================
ANCHOR_YEAR = 2025                       # LE = BAU in 2025

LE_YEARS = [2026, 2027, 2028, 2029, 2030, 2035, 2040, 2045, 2050]

# =========================================================
# GROWTH ASSUMPTION (Low Economy)
# =========================================================
LE_GROWTH = 0.01                         # 1% per year, 2026 to 2050

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


def rescale_year(year, target):
    """Load the BAU file for a year, scale it to the target energy and save it."""
    df = load_file(year)
    if df is None:
        return

    p_cols, _ = get_pq_columns(df)
    current = annual_energy_gwh(df, p_cols)

    scale = target / current
    scale_and_save(df, year, scale)
    summary.append({"year": year, "target_gwh": target, "scale": scale})

    print(f"{year}: target={target:.3f} GWh, scale={scale:.4f}")


summary = []

# =========================================================
# STEP 1: ANCHOR AT 2025 (LE = BAU in 2025)
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
# STEP 2: LOW ECONOMY GROWTH (2026-2050), 1% per year
# =========================================================
for year in LE_YEARS:
    rescale_year(year, E_2025 * (1 + LE_GROWTH) ** (year - ANCHOR_YEAR))

summary_df = pd.DataFrame(summary).set_index("year")
summary_df.to_csv(OUT_DIR / "summary_le.csv")

print("\nLow Economy demand scaling complete.")
print(summary_df.round(4))
print(f"Output folder: {OUT_DIR}")