from pathlib import Path
import xarray as xr

ERA5_DIR = Path(r"C:/Users/Mothala/pypsa-lesotho/data/era5_hourly/fixed")
OUTFILE = ERA5_DIR / "ERA5_Lesotho_hourly_2010_2024.nc"

files = sorted(ERA5_DIR.glob("era5_Lesotho_hourly_*.nc"))
if not files:
    raise FileNotFoundError(f"No NetCDF files found in {ERA5_DIR}")

ds = xr.open_mfdataset(
    [str(f) for f in files],
    combine="by_coords",
    parallel=False,      # safer on Windows
    engine="netcdf4"
)

# Keep only precipitation
if "tp" not in ds.data_vars:
    raise KeyError(f"'tp' not found. Variables present: {list(ds.data_vars)}")

ds = ds[["tp"]]

# 🔑 ERA5 FIX: rename valid_time → time
if "valid_time" in ds.coords:
    ds = ds.rename({"valid_time": "time"})

# Sort by time now that it exists
ds = ds.sortby("time")

# Optional compression
encoding = {"tp": {"zlib": True, "complevel": 4}}

ds.to_netcdf(OUTFILE, encoding=encoding)

print(f"Successfully merged ERA5 data to:\n{OUTFILE}")
print(ds)
