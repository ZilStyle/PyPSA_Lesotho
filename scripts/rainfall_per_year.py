import pandas as pd

csv = r"C:/Users/Mothala/pypsa-lesotho/data/hydrobasins/four_basins_rain_hourly_mm_weighted_clean.csv"

df = pd.read_csv(csv)

# Explicit and robust datetime parsing
df["time"] = pd.to_datetime(df["time"], dayfirst=True, format="mixed")
df = df.set_index("time")

rain = df[["jordan", "katse_dam", "muela", "oxbow"]]

# Annual rainfall totals (mm/year)
annual_mm = rain.resample("YE").sum()
annual_mm.index = annual_mm.index.year

print("Annual rainfall totals (mm/year):")
print(annual_mm)
print("\nSummary statistics:")
print(annual_mm.describe())
