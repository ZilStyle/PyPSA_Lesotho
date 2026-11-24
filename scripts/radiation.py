import xarray as xr
import pandas as pd
import pvlib
import os

# ==========================================================
# USER SETTINGS
# ==========================================================
NETCDF_FILE = "lesotho_ssrd_countrywide_2025.nc"

TARGET_LAT = -29.80765
TARGET_LON = 27.335203

TILT_DEG = 30
AZIMUTH_DEG = 0          # north-facing (southern hemisphere)
G_REF = 1000.0           # W/m² reference irradiance

SOLAR_CAPACITY_MW = 30.0 # set plant size here

BASE_DATA_DIR = "data"
SOLAR_DIR = os.path.join(BASE_DATA_DIR, "solar_profile")

OUT_PMAXPU = os.path.join(SOLAR_DIR, "solar_p_max_pu_tilt30_30_2025.csv")
OUT_MW     = os.path.join(SOLAR_DIR, "solar_generation_mw_tilt30_30_2025.csv")

# ==========================================================
# CREATE OUTPUT DIRECTORY IF NEEDED
# ==========================================================
os.makedirs(SOLAR_DIR, exist_ok=True)

# ==========================================================
# LOAD ERA5 SSRD DATA
# ==========================================================
ds = xr.open_dataset(NETCDF_FILE)
ssrd = ds["ssrd"]

# ==========================================================
# SELECT NEAREST GRID POINT
# ==========================================================
ssrd_point = ssrd.sel(latitude=TARGET_LAT, longitude=TARGET_LON, method="nearest")
sel_lat = float(ssrd_point.latitude.values)
sel_lon = float(ssrd_point.longitude.values)

print("==============================================")
print("ERA5 GRID POINT SELECTION")
print(f"Requested location : ({TARGET_LAT:.5f}, {TARGET_LON:.6f})")
print(f"Nearest grid used  : ({sel_lat:.5f}, {sel_lon:.6f})")
print("==============================================")

# ==========================================================
# SSRD → GHI (W/m²)
# ==========================================================
ghi = (ssrd_point / 3600.0).to_series()
ghi.index = pd.to_datetime(ghi.index)
ghi = ghi.clip(lower=0)

# ==========================================================
# SOLAR POSITION
# ==========================================================
sp = pvlib.solarposition.get_solarposition(
    time=ghi.index,
    latitude=sel_lat,
    longitude=sel_lon
)

# ==========================================================
# DECOMPOSE (ERBS)
# ==========================================================
dni_dhi = pvlib.irradiance.erbs(
    ghi=ghi,
    zenith=sp["zenith"],
    datetime_or_doy=ghi.index
)

dni = dni_dhi["dni"].clip(lower=0)
dhi = dni_dhi["dhi"].clip(lower=0)

# ==========================================================
# TRANSPOSE TO 30° TILT
# ==========================================================
poa = pvlib.irradiance.get_total_irradiance(
    surface_tilt=TILT_DEG,
    surface_azimuth=AZIMUTH_DEG,
    solar_zenith=sp["zenith"],
    solar_azimuth=sp["azimuth"],
    dni=dni,
    ghi=ghi,
    dhi=dhi
)

poa_global = poa["poa_global"].clip(lower=0)

# ==========================================================
# CAPACITY FACTOR AND MW PROFILE
# ==========================================================
PR = 0.80
p_max_pu = (poa_global / 1000.0) * PR
p_max_pu = p_max_pu.clip(0, 1)


p_mw = p_max_pu * SOLAR_CAPACITY_MW
p_mw.name = "p_mw"

# ==========================================================
# EXPORT
# ==========================================================
p_max_pu.to_csv(OUT_PMAXPU)
p_mw.to_csv(OUT_MW)

print("==============================================")
print("EXPORT COMPLETE")
print(f"Saved p_max_pu → {OUT_PMAXPU}")
print(f"Saved MW profile → {OUT_MW}")
print(f"Installed capacity : {SOLAR_CAPACITY_MW} MW")
print(f"Mean CF             : {p_max_pu.mean():.3f}")
print(f"Annual energy (MWh) : {p_mw.sum():.2f}")
print("==============================================")
