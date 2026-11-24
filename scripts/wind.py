import atlite
import numpy as np
import pandas as pd

cutout_path = "./cutouts/litsoeneng_wind_2025_jan.nc"

cutout = atlite.Cutout(cutout_path)

print("Cutout loaded")
print("Grid size:", dict(cutout.data.sizes))
print("Time range:", cutout.data.time.values[0], "to", cutout.data.time.values[-1])

# Use 100 m wind speed
ws = cutout.data["wnd100m"]

records = []

for x in ws.x.values:
    for y in ws.y.values:
        series = ws.sel(x=x, y=y).values.astype(float)

        records.append({
            "x": float(x),
            "y": float(y),
            "mean_ws": series.mean(),
            "p90_ws": np.percentile(series, 90),
            "max_ws": series.max(),
            "hours_above_6": int(np.sum(series > 6)),
            "hours_above_8": int(np.sum(series > 8)),
        })

df_ws = pd.DataFrame(records).sort_values("mean_ws", ascending=False)

df_ws

best = df_ws.iloc[0]

best_x = best["x"]
best_y = best["y"]

print("Selected ridge-proxy grid point:")
print(best)
