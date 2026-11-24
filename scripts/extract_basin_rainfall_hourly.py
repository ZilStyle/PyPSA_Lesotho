import geopandas as gpd
import xarray as xr
import numpy as np
from rasterio.features import geometry_mask
from affine import Affine
from pathlib import Path
import pandas as pd

# =================================================
# PATHS
# =================================================
ERA5_FILE = Path(
    "C:/Users/Mothala/pypsa-lesotho/data/era5_hourly/fixed/ERA5_Lesotho_hourly_2010_2024.nc"
)

BASINS_ROOT = Path(
    "C:/Users/Mothala/pypsa-lesotho/data/hydrobasins/four_basins"
)

OUT_CSV = Path(
    "C:/Users/Mothala/pypsa-lesotho/data/hydrobasins/four_basins_rain_hourly_mm_correct.csv"
)

# =================================================
# LOAD ERA5
# =================================================
ds = xr.open_dataset(ERA5_FILE)

# ERA5-Land total precipitation
# units: metres accumulated over the hour
tp = ds["tp"] * 1000.0  # convert to mm
tp = tp.sortby("time")

lats = ds["latitude"].values
lons = ds["longitude"].values

# build affine transform for raster masking
res_lon = abs(lons[1] - lons[0])
res_lat = abs(lats[1] - lats[0])

transform = Affine(
    res_lon, 0, lons.min(),
    0, -res_lat, lats.max()
)

results = {}

# =================================================
# LOOP THROUGH BASINS
# =================================================
for basin_dir in BASINS_ROOT.iterdir():

    if not basin_dir.is_dir():
        continue

    basin_name = basin_dir.name.lower().replace(" ", "_")
    shp_files = list(basin_dir.glob("*.shp"))

    if len(shp_files) != 1:
        raise RuntimeError(
            f"Expected exactly one shapefile in {basin_dir}, found {len(shp_files)}"
        )

    print(f"Processing basin: {basin_name}")

    basin = gpd.read_file(shp_files[0]).to_crs("EPSG:4326")
    geom = basin.geometry.values

    # raster mask: True inside basin
    mask = geometry_mask(
        geom,
        out_shape=(len(lats), len(lons)),
        transform=transform,
        invert=True
    )

    # -------------------------------------------------
    # CRITICAL FIX: TRUE BASIN AVERAGE
    # -------------------------------------------------
    masked_tp = tp.where(mask)

    # number of grid cells in basin (constant)
    cell_count = mask.sum()

    # basin-average rainfall (mm/h)
    basin_mean = masked_tp.sum(dim=("latitude", "longitude")) / cell_count

    results[basin_name] = basin_mean

# =================================================
# SAVE OUTPUT
# =================================================
df = xr.Dataset(results).to_dataframe()
df.index.name = "time"
df = df.sort_index()

df.to_csv(OUT_CSV)

print("\nBasin-average rainfall extraction COMPLETE")
print(f"Saved to:\n{OUT_CSV}")
print(df.head())
