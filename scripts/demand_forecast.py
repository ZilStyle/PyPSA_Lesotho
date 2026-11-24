import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
import re

# -----------------------------------
# LOAD DIRECTORY
# -----------------------------------
LOAD_DIR = Path(r"C:\Users\USER\pypsa-lesotho\data\demand_forecast\loads_HE_supply_end")

if not LOAD_DIR.exists():
    raise FileNotFoundError(f"Directory not found: {LOAD_DIR}")

# -----------------------------------
# OUTPUT DIRECTORY (same as load dir)
# -----------------------------------
OUT_DIR = LOAD_DIR

# -----------------------------------
# FIND ALL EXCEL FILES
# -----------------------------------
excel_files = sorted(
    f for f in LOAD_DIR.glob("*.xlsx")
    if not f.name.startswith("~$")
)

if not excel_files:
    raise FileNotFoundError("No Excel (.xlsx) files found in loads_status_quo")

summary = []

# -----------------------------------
# PROCESS FILES
# -----------------------------------
for f in excel_files:

    match = re.search(r"(19|20)\d{2}", f.stem)
    if not match:
        print(f"Skipping file without year: {f.name}")
        continue

    year = int(match.group())

    df = pd.read_excel(f)
    df = df.set_index(df.columns[0])

    p_cols = [c for c in df.columns if c.lower().endswith("_p")]
    q_cols = [c for c in df.columns if c.lower().endswith("_q")]

    if not p_cols:
        raise ValueError(f"No active power (_p) columns found in {f.name}")

    system_p = df[p_cols].sum(axis=1)
    system_q = df[q_cols].sum(axis=1)

    summary.append({
        "year": year,
        "active_energy_gwh": system_p.sum() / 1000,
        "reactive_energy_gvarh": system_q.sum() / 1000,
        "peak_active_mw": system_p.max(),
        "peak_reactive_mvar": system_q.max()
    })

# -----------------------------------
# CREATE SUMMARY TABLE
# -----------------------------------
summary_df = (
    pd.DataFrame(summary)
    .set_index("year")
    .sort_index()
)

print("\nDemand summary:")
print(summary_df)

# -----------------------------------
# PLOTS (SAVE + SHOW)
# -----------------------------------

# Annual active energy
plt.figure(figsize=(8, 5))
plt.plot(
    summary_df.index,
    summary_df["active_energy_gwh"],
    marker="o",
    linewidth=2
)
plt.xlabel("Year")
plt.ylabel("Annual Active Energy (GWh)")
plt.title("Status Quo Electricity Demand Projection")
plt.grid(True)
plt.tight_layout()

energy_plot_path = OUT_DIR / "annual_active_energy_gwh.png"
plt.savefig(energy_plot_path, dpi=300)

# Peak active power
plt.figure(figsize=(8, 5))
plt.plot(
    summary_df.index,
    summary_df["peak_active_mw"],
    marker="s",
    linewidth=2
)
plt.xlabel("Year")
plt.ylabel("Peak Active Power (MW)")
plt.title("Status Quo Peak Demand Projection")
plt.grid(True)
plt.tight_layout()

peak_plot_path = OUT_DIR / "peak_active_power_mw.png"
plt.savefig(peak_plot_path, dpi=300)

print("\nPlots saved to:")
print(energy_plot_path)
print(peak_plot_path)





