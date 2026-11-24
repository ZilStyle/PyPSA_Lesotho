import cdsapi
import xarray as xr
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature

# Step 1: Download ERA5 hourly surface radiation for Lesotho
c = cdsapi.Client()

c.retrieve(
    'reanalysis-era5-single-levels',
    {
        'product_type': 'reanalysis',
        'variable': 'surface_solar_radiation_downwards',
        'year': '2025',
        'month': [f'{m:02d}' for m in range(1, 13)],
        'day': [f'{d:02d}' for d in range(1, 32)],
        'time': [f'{h:02d}:00' for h in range(24)],
        'format': 'netcdf',
        'area': [-28.5, 26.5, -31.0, 29.5],  # [N, W, S, E] - covers Lesotho
        'grid': [0.25, 0.25],
    },
    'lesotho_ssrd_countrywide_2025.nc'
)



