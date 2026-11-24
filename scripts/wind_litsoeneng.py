import xarray as xr
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# ==========================================================
# USER SETTINGS
# ==========================================================
NETCDF_FILE = "wind_100m_area_-30.1563_27.5111_jan2025.nc"

TARGET_LAT = -30.1563
TARGET_LON = 27.5111

# ==========================================================
# LOAD DATA
# ==========================================================
ds = xr.open_dataset(NETCDF_FILE)

u100 = ds["u100"]
v100 = ds["v100"]

# ==========================================================
# SELECT NEAREST GRID POINT
# ==========================================================
u100_p = u100.sel(latitude=TARGET_LAT, longitude=TARGET_LON, method="nearest")
v100_p = v100.sel(latitude=TARGET_LAT, longitude=TARGET_LON, method="nearest")

sel_lat = float(u100_p.latitude.values)
sel_lon = float(u100_p.longitude.values)

print("==============================================")
print("ERA5 GRID POINT SELECTION")
print(f"Requested location : ({TARGET_LAT:.5f}, {TARGET_LON:.6f})")
print(f"Nearest grid used  : ({sel_lat:.5f}, {sel_lon:.6f})")
print("==============================================")

# ==========================================================
# WIND SPEED CALCULATION (100 m)
# ==========================================================
ws_100m = np.sqrt(u100_p**2 + v100_p**2)

# Convert to pandas Series
ws_100m = ws_100m.to_series()
ws_100m.index = pd.to_datetime(ws_100m.index)

# ==========================================================
# BASIC STATISTICS
# ==========================================================
print("==============================================")
print("JANUARY 2025 WIND SPEED STATISTICS (100 m)")
print(f"Mean wind speed   : {ws_100m.mean():.2f} m/s")
print(f"Median wind speed : {ws_100m.median():.2f} m/s")
print(f"Max wind speed    : {ws_100m.max():.2f} m/s")
print(f"Min wind speed    : {ws_100m.min():.2f} m/s")
print("==============================================")

# ==========================================================
# OPTIONAL: PLOT TIME SERIES
# ==========================================================
plt.figure(figsize=(12, 4))
plt.plot(ws_100m.index, ws_100m.values)
plt.ylabel("Wind speed at 100 m (m/s)")
plt.xlabel("Time")
plt.title("ERA5 Wind Speed at 100 m – January 2025")
plt.tight_layout()
plt.show()
