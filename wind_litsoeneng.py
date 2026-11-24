import atlite
import xarray as xr
import pandas as pd
import matplotlib.pyplot as plt
import os

# -----------------------------------------------------
# 1️⃣ Define parameters
# -----------------------------------------------------
cutout_name = "litsoeneng_wind_2025_jan"          # NEW cutout name
cutout_dir = "./cutouts"

# Coordinates for Litšoeneng
lon, lat = 27.5111, -30.1563


# Ensure cutout directory exists
os.makedirs(cutout_dir, exist_ok=True)

cutout_path = os.path.join(cutout_dir, cutout_name + ".nc")

# -----------------------------------------------------
# 2️⃣ Always create a new cutout
# -----------------------------------------------------
print("🆕 Creating new ERA5 cutout (forcing regeneration)...")

cutout = atlite.Cutout(
    path=cutout_path,
    module="era5",
    x=slice(27, 28),
    y=slice(-30.5, -29.5),
    time=slice("2025-01-01", "2025-01-31"),
)

cutout.prepare()

print("✅ New cutout prepared successfully")
print("Cutout dimensions:", dict(cutout.data.sizes))
print(
    "Time range:",
    cutout.data.time.values[0],
    "to",
    cutout.data.time.values[-1],
)
