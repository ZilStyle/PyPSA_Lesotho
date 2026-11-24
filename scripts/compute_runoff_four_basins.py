import pandas as pd

RAIN_CSV = r"C:/Users/Mothala/pypsa-lesotho/data/hydrobasins/four_basins_rain_hourly_mm_clean.csv"
OUT_CSV  = r"C:/Users/Mothala/pypsa-lesotho/data/hydrobasins/four_basins_runoff_m3s.csv"

# Basin parameters (replace areas with your exact UP_AREA values)
basins = {
    "katse_dam": {"area_km2": 3375.7, "C": 0.45},
    "muela":     {"area_km2": 5794.4, "C": 0.50},
    "oxbow":     {"area_km2": 4441.3, "C": 0.40},
    "jordan":    {"area_km2": 3487.8,  "C": 0.35},
}

df = pd.read_csv(RAIN_CSV, parse_dates=["time"], index_col="time")

Q = pd.DataFrame(index=df.index)

for basin, params in basins.items():
    A_m2 = params["area_km2"] * 1e6
    C = params["C"]

    # Rainfall in mm/h → m/h
    rain_m = df[basin] / 1000.0

    # Runoff in m3/s
    Q[basin] = C * rain_m * A_m2 / 3600.0

Q.to_csv(OUT_CSV)

print("Runoff Q(t) computed and saved to:")
print(OUT_CSV)
print(Q.head())
