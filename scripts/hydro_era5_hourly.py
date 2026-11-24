import cdsapi
import os

c = cdsapi.Client()

# Your chosen download folder
download_dir = r"C:/Users/Mothala/pypsa-lesotho/data/era5_hourly"

# Create folder if it does not exist
os.makedirs(download_dir, exist_ok=True)

years = list(range(2010, 2025))  # 2010 to 2024
months = [f"{m:02d}" for m in range(1, 13)]

for y in years:
    for m in months:
        print(f"\nDownloading ERA5-Land hourly precipitation for {y}-{m}...")

        outfile = os.path.join(download_dir, f"era5_Lesotho_hourly_{y}_{m}.nc")

        # Avoid downloading twice
        if os.path.exists(outfile):
            print(f"File {outfile} already exists, skipping.")
            continue

        c.retrieve(
            'reanalysis-era5-land',
            {
                'variable': ['total_precipitation'],
                'year': str(y),
                'month': m,
                'day': [f"{d:02d}" for d in range(1, 32)],   # always 1–28 to avoid invalid dates
                'time': [f"{h:02d}:00" for h in range(24)],  # 24 hours
                'area': [-28.5, 27.2, -31.0, 29.6],          # tight Lesotho bounding box
                'format': 'netcdf'
            },
            outfile
        )

        print(f"Finished {y}-{m} → saved to {outfile}")