import pandas as pd
import os

# ==========================================================
# USER SETTINGS
# ==========================================================
WIND_2024_CSV = "data/generator_profiles_planned/wind_ready/wind_p_max_pu_2024.csv"
WIND_2025_CSV = "data/generator_profiles_planned/wind_ready/wind_p_max_pu_2025.csv"

OUTPUT_DIR = "data/generator_profiles_planned/wind_ready"

PLANNING_YEARS = [
    2026, 2027, 2028, 2029, 2030,
    2035, 2040, 2045, 2050
]

# ==========================================================
# CREATE OUTPUT DIRECTORY
# ==========================================================
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ==========================================================
# LOAD BASE PROFILES
# ==========================================================
cf_2024 = pd.read_csv(
    WIND_2024_CSV,
    index_col=0,
    parse_dates=True
).squeeze()

cf_2025 = pd.read_csv(
    WIND_2025_CSV,
    index_col=0,
    parse_dates=True
).squeeze()

cf_2024.index = pd.to_datetime(cf_2024.index, dayfirst=True, format="mixed", errors="raise")
cf_2025.index = pd.to_datetime(cf_2025.index, dayfirst=True, format="mixed", errors="raise")

# ==========================================================
# FUNCTION TO ASSIGN PROFILE BY LEAP YEAR
# ==========================================================
def build_profile_for_year(year, cf_leap, cf_normal):
    base = cf_leap.copy() if pd.Timestamp(year=year, month=1, day=1).is_leap_year else cf_normal.copy()
    base.index = base.index.map(lambda t: t.replace(year=year))
    return base



# ==========================================================
# GENERATE AND SAVE PROFILES
# ==========================================================
for year in PLANNING_YEARS:
    cf_year = build_profile_for_year(year, cf_2024, cf_2025)

    out_file = os.path.join(
        OUTPUT_DIR,
        f"wind_p_max_pu_{year}.csv"
    )

    cf_year.to_csv(out_file)

    print(
        f"Saved solar profile for {year} | "
        f"hours = {len(cf_year)} | "
       # f"mean CF = {cf_year.mean():.3f}"
    )

print("==============================================")
print("Solar capacity factor preparation COMPLETE")
print(f"Profiles stored in: {OUTPUT_DIR}")
print("==============================================")
