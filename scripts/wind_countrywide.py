import cdsapi
import xarray as xr
import numpy as np

# ==========================================================
# TARGET LOCATION
# ==========================================================
TARGET_LAT = -30.1563
TARGET_LON = 27.5111

# Small spatial buffer (~25–30 km)
DELTA = 0.25

# ERA5 area format: [North, West, South, East]
AREA = [
    TARGET_LAT + DELTA,   # North
    TARGET_LON - DELTA,   # West
    TARGET_LAT - DELTA,   # South
    TARGET_LON + DELTA    # East
]

# ==========================================================
# DOWNLOAD ERA5 HOURLY WIND DATA (100 m) – JANUARY 2025
# ==========================================================
c = cdsapi.Client()

c.retrieve(
    "reanalysis-era5-single-levels",
    {
        "product_type": "reanalysis",
        "variable": [
            "100m_u_component_of_wind",
            "100m_v_component_of_wind"
        ],
        "year": "2025",
        "month": "08",
        "day": [f"{d:02d}" for d in range(1, 32)],
        "time": [f"{h:02d}:00" for h in range(24)],
        "format": "netcdf",
        "area": AREA,
        "grid": [0.25, 0.25],
    },
    "wind_100m_area_-30.1563_27.5111_jan2025.nc"
)

print("ERA5 100 m wind data download complete for January 2025")
print(f"Area used [N, W, S, E]: {AREA}")
