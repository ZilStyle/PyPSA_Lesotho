import pypsa
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

# =================================================
# USER SETTINGS
# =================================================
YEAR = 2040
NETWORK_FILE = f"networks/B/solved_{YEAR}.nc"

OUTDIR = Path(f"results/B/diagnostics_{YEAR}")
OUTDIR.mkdir(parents=True, exist_ok=True)

# =================================================
# HELPER: LEAP YEAR CHECK
# =================================================
def is_leap(year):
    return (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0)

# =================================================
# LOAD NETWORK
# =================================================
print("=" * 60)
print(f"DAILY OPERATION + ATTRIBUTION | YEAR {YEAR}")
print("=" * 60)

n = pypsa.Network(NETWORK_FILE)

# =================================================
# SELECT REPRESENTATIVE DAY
# =================================================
if is_leap(YEAR):
    target_day = f"{YEAR}-07-08"
else:
    target_day = f"{YEAR}-07-10"

print(f"\nSelected analysis day: {target_day}")

# ==================================================
# EXPORT + STORAGE TIMESERIES
# =====================================================
export_gens = n.generators[n.generators.carrier == "export"].index
if len(export_gens) == 0:
    raise ValueError("No export generator found")

export_p = n.generators_t.p[export_gens].sum(axis=1)
export_MW = -export_p.clip(upper=0.0)

if not n.storage_units.empty:
    storage_p = n.storage_units_t.p.sum(axis=1)
else:
    storage_p = pd.Series(0.0, index=n.snapshots)

storage_charge = -storage_p.clip(upper=0.0)
storage_discharge = storage_p.clip(lower=0.0)

# =======================================================
# FILTER DAY
# =======================================================
mask = export_MW.index.strftime("%Y-%m-%d") == target_day

export_day = export_MW[mask]
charge_day = storage_charge[mask]
discharge_day = storage_discharge[mask]

if export_day.empty:
    raise ValueError(f"No data for {target_day}")

hours = export_day.index.hour

# ======================================================
# PRINT SUMMARY
# ======================================================
print("\n--- DAILY SUMMARY ---")
print(f"Max export (MW):       {export_day.max():.2f}")
print(f"Max charge (MW):       {charge_day.max():.2f}")
print(f"Max discharge (MW):    {discharge_day.max():.2f}")

print(f"Total export (MWh):    {export_day.sum():.1f}")
print(f"Total charge (MWh):    {charge_day.sum():.1f}")
print(f"Total discharge (MWh): {discharge_day.sum():.1f}")

# =================================================
# PLOT DAILY PROFILE
# =================================================
plt.figure(figsize=(14,6))

plt.plot(hours, export_day, label="Exports", linewidth=2)
plt.plot(hours, charge_day, label="Battery Charging", linewidth=2)
plt.plot(hours, discharge_day, label="Battery Discharging", linewidth=2)

plt.axvspan(18, 21, alpha=0.2, color="grey", label="Evening Peak")

plt.xlabel("Hour of Day")
plt.ylabel("Power (MW)")
plt.title(f"{YEAR} Daily Operation Profile ({target_day})")

plt.xticks(range(0,24))
plt.grid(alpha=0.3)
plt.legend()

plt.tight_layout()
plt.savefig(OUTDIR / f"daily_operation_{YEAR}.png", dpi=300)
plt.show()

# =================================================
# GENERATION BY TECHNOLOGY
# =================================================
gen_p = n.generators_t.p.copy()
gen_carrier = n.generators.carrier

gen_by_tech = gen_p.groupby(gen_carrier, axis=1).sum()
gen_day = gen_by_tech[mask]

# =================================================
# EXPORT CONTRIBUTIONS
# =================================================
export_contrib = {}

for tech in gen_day.columns:
    contrib = []

    for t in gen_day.index:
        total_gen = gen_day.loc[t].sum()

        if total_gen <= 0:
            contrib.append(0.0)
            continue

        share = gen_day.loc[t, tech] / total_gen
        contrib.append(share * export_day.loc[t])

    export_contrib[tech] = np.sum(contrib)

export_contrib = pd.Series(export_contrib).sort_values(ascending=False)

print("\n--- EXPORT CONTRIBUTION BY TECHNOLOGY (MWh) ---")
print(export_contrib.round(2))

# =================================================
# TRUE CHARGING CONTRIBUTION (MODEL-CONSISTENT)
# =================================================
solar_idx = n.generators[n.generators.carrier == "solar"].index
wind_idx  = n.generators[n.generators.carrier == "wind"].index

solar_gen = n.generators_t.p[solar_idx].sum(axis=1)
wind_gen  = n.generators_t.p[wind_idx].sum(axis=1) if len(wind_idx) > 0 else pd.Series(0.0, index=n.snapshots)

solar_day = solar_gen[mask]
wind_day  = wind_gen[mask] if isinstance(wind_gen, pd.Series) else 0

charge_contrib = {"solar": 0.0, "wind": 0.0}

for t in solar_day.index:

    total_ren = solar_day.loc[t] + (wind_day.loc[t] if isinstance(wind_day, pd.Series) else 0)

    if total_ren <= 0:
        continue

    # proportional split ONLY among renewables
    solar_share = solar_day.loc[t] / total_ren
    wind_share  = (wind_day.loc[t] / total_ren) if isinstance(wind_day, pd.Series) else 0

    charge_contrib["solar"] += solar_share * charge_day.loc[t]
    charge_contrib["wind"]  += wind_share * charge_day.loc[t]

charge_contrib = pd.Series(charge_contrib)

print("\n--- BATTERY CHARGING CONTRIBUTION (MODEL CONSISTENT) ---")
print(charge_contrib.round(2))

# =================================================
# CONTRIBUTION PLOT
# =================================================
df_plot = pd.DataFrame({
    "Exports": export_contrib,
    "Charging": charge_contrib
}).fillna(0)

df_plot = df_plot[df_plot.sum(axis=1) > 0]

df_plot.plot(kind="bar", stacked=True, figsize=(10,6))

plt.ylabel("Energy (MWh)")
plt.title(f"{YEAR} Technology Contribution ({target_day})")
plt.xticks(rotation=45)
plt.grid(axis="y", alpha=0.3)

plt.tight_layout()
plt.savefig(OUTDIR / f"tech_contributions_{YEAR}.png", dpi=300)
plt.show()

print(f"\nAll outputs saved in: {OUTDIR}")

import pypsa
import pandas as pd
import matplotlib.pyplot as plt

YEAR = 2040
n = pypsa.Network(f"networks/B/solved_{YEAR}.nc")

# -----------------------------
# FIND SYSTEM PEAK DAY
# -----------------------------
load_ts = n.loads_t.p_set.sum(axis=1)
peak_day = load_ts.idxmax().strftime("%Y-%m-%d")

print(f"\nPeak day: {peak_day}")

# -----------------------------
# EXTRACT OXBOW PROFILE
# -----------------------------
oxbow = n.generators_t.p["Oxbow"]

mask = oxbow.index.strftime("%Y-%m-%d") == peak_day
oxbow_day = oxbow[mask]

hours = oxbow_day.index.hour

# -----------------------------
# PLOT
# -----------------------------
plt.figure(figsize=(12,5))

plt.plot(hours, oxbow_day, marker="o")

plt.title(f"Oxbow Contribution on Peak Day ({peak_day})")
plt.xlabel("Hour of Day")
plt.ylabel("Power (MW)")

plt.xticks(range(0,24))
plt.grid(alpha=0.3)

plt.tight_layout()
plt.show()