import pandas as pd

IN_CSV = r"C:/Users/Mothala/pypsa-lesotho/data/hydrobasins/four_basins_rain_hourly_mm_weighted.csv"
OUT_CSV = r"C:/Users/Mothala/pypsa-lesotho/data/hydrobasins/four_basins_rain_hourly_mm_weighted_clean.csv"

df = pd.read_csv(IN_CSV, parse_dates=["time"], index_col="time")

# Drop ERA5 metadata columns if present
df = df.drop(columns=[c for c in ["number", "expver"] if c in df.columns])

# Standardise column names (important for later scripts)
df.columns = [c.strip().replace(" ", "_").lower() for c in df.columns]

df.to_csv(OUT_CSV)

print("Clean rainfall file saved to:")
print(OUT_CSV)
print(df.head())
