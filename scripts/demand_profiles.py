import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

# ---------------------------------------
# FILES (do not change paths)
# ---------------------------------------
FILES = {
    2022: "data/historic_load/load_2022.csv",
    2023: "data/historic_load/load_2023.csv",
    2024: "data/historic_load/load_2024.csv",
}

profiles = {}

# ---------------------------------------
# LOAD + PROCESS
# ---------------------------------------
for year, file in FILES.items():
    df = pd.read_csv(file)

    # assume first column is datetime
    time_col = df.columns[0]
    load_col = df.columns[1]

    df[time_col] = pd.to_datetime(
        df[time_col],
        format="mixed",
        dayfirst=True,
        errors="raise"
    )

    df = df.set_index(time_col)
    df = df.sort_index()

    # find peak day
    daily_peak = df[load_col].resample("D").max()
    peak_day = daily_peak.idxmax().date()

    peak_profile = df.loc[str(peak_day), load_col]

    profiles[year] = peak_profile

    print(f"{year} peak day: {peak_day} | Peak load: {peak_profile.max():.2f} MW")

# ---------------------------------------
# PLOT
# ---------------------------------------
plt.figure(figsize=(12, 6))

for year, series in profiles.items():
    plt.plot(
        series.index.hour,
        series.values,
        label=str(year),
        linewidth=2
    )

plt.xlabel("Hour of day")
plt.ylabel("Load (MW)")
plt.title("Peak Day Daily Demand Profiles (2022–2024)")
plt.legend(title="Year")
plt.grid(alpha=0.3)

plt.tight_layout()
plt.savefig("results/peak_day_daily_profiles_2022_2024.png", dpi=300)
plt.show()

import pandas as pd
import matplotlib.pyplot as plt

# ---------------------------------------
# FILES (do not change paths)
# ---------------------------------------
FILES = {
    2022: "data/historic_load/load_2022.csv",
    2023: "data/historic_load/load_2023.csv",
    2024: "data/historic_load/load_2024.csv",
}

plt.figure(figsize=(16, 6))

# ---------------------------------------
# LOAD + WEEKLY AGGREGATE + PLOT
# ---------------------------------------
for year, file in FILES.items():
    df = pd.read_csv(file)

    # assume: first column = time, second column = load
    time_col = df.columns[0]
    load_col = df.columns[1]

    df[time_col] = pd.to_datetime(
        df[time_col],
        format="mixed",
        dayfirst=True,
        errors="raise"
    )

    df = df.set_index(time_col)
    df = df.sort_index()

    # weekly average load
    weekly_load = df[load_col].resample("W").mean()

    plt.plot(
        range(1, len(weekly_load) + 1),
        weekly_load.values,
        label=str(year),
        linewidth=1.8
    )

    print(
        f"{year}: weeks={len(weekly_load)}, "
        f"peak weekly avg={weekly_load.max():.2f} MW, "
        f"mean weekly avg={weekly_load.mean():.2f} MW"
    )

# ---------------------------------------
# FORMAT
# ---------------------------------------
plt.xlabel("Week of year")
plt.ylabel("Average Load (MW)")
plt.title("Annual Weekly Average Load Profiles Overlay (2022–2024)")
plt.legend(title="Year")
plt.grid(alpha=0.3)

plt.tight_layout()
plt.savefig("results/annual_weekly_load_profiles_2022_2024.png", dpi=300)
plt.show()