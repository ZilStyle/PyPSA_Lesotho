import pandas as pd
import matplotlib.pyplot as plt
import os
import numpy as np
import calendar

# ----------------------------------------------------------
# USER SETTINGS
# ----------------------------------------------------------

GEN_PROF_DIR = "data/generator_profiles_scenario1"
LOAD_DIR = "data/Scenario1/load_BAU_supply_end"
UNMET_DIR = "results/unmet_demand_BAU"

YEARS = [2025, 2026, 2027, 2028, 2029, 2030, 2035, 2040, 2045, 2050]

solar_name = "Ramarothole"
hydro_name = "Muela"
imports_name = "Maseru bulk"

# ----------------------------------------------------------
# ACCUMULATE ANNUAL VALUES
# ----------------------------------------------------------

solar_total = []
hydro_total = []
imports_total = []
unmet_total = []
load_total = []
hours_year = []

for year in YEARS:

    # Hours per year (leap year handling)
    is_leap = calendar.isleap(year)
    hours = 8784 if is_leap else 8760
    hours_year.append(hours)

    # -------- LOAD --------
    load_file = os.path.join(LOAD_DIR, f"load_timeseries_{year}_supply_end.xlsx")
    df_load = pd.read_excel(load_file, sheet_name="Sheet1")

    p_cols = [c for c in df_load.columns if c.endswith("_p")]
    total_load = df_load[p_cols].sum(axis=1).sum()
    load_total.append(total_load)

    # -------- GENERATION PROFILES --------
    gen_file = os.path.join(GEN_PROF_DIR, f"generator_profiles_scenario1_{year}.xlsx")
    df_gen = pd.read_excel(gen_file, sheet_name="Sheet2")

    total_solar = df_gen[solar_name].sum()
    total_hydro = df_gen[hydro_name].sum()
    total_imports = df_gen[imports_name].sum()

    solar_total.append(total_solar)
    hydro_total.append(total_hydro)
    imports_total.append(total_imports)

    # -------- UNMET DEMAND --------
    unmet_file = os.path.join(UNMET_DIR, f"unmet_demand_hourly_{year}.csv")
    df_unmet = pd.read_csv(unmet_file)
    total_unmet = df_unmet["unmet"].sum()
    unmet_total.append(total_unmet)

# ----------------------------------------------------------
# CONVERT TO GWh
# ----------------------------------------------------------
load_gwh = np.array(load_total) /1000
solar_gwh = np.array(solar_total) /1000
hydro_gwh = np.array(hydro_total) /1000
imports_gwh = np.array(imports_total) /1000
unmet_gwh = np.array(unmet_total) /1000

# ----------------------------------------------------------
# CONVERT TO MW (average)
# ----------------------------------------------------------

load_gw = np.array(load_total) / hours_year
solar_gw = np.array(solar_total) / hours_year
hydro_gw = np.array(hydro_total) / hours_year
imports_gw = np.array(imports_total) / hours_year
unmet_gw = np.array(unmet_total) / hours_year

# ----------------------------------------------------------
# HELPER: CENTER LABELS FOR STACKED BARS
# ----------------------------------------------------------

def label_center(values, bottoms, x_pos):
    for i in range(len(values)):
        if values[i] > 0:
            plt.text(
                x_pos[i],
                bottoms[i] + values[i] / 2,
                f"{values[i]:.1f}",
                ha="center",
                va="center",
                color="black",
                fontsize=9,
                
            )

def label_top(values, bottoms, x_pos):
    for i in range(len(values)):
        if values[i] > 0.5:
            plt.text(
                x_pos[i],
                bottoms[i] + values[i],
                f"{values[i]:.1f}",
                ha="center",
                va="bottom",
                color="black",
                fontsize=9,
                
            )

# ----------------------------------------------------------
# PLOT: STACKED GENERATION vs DEMAND (GWh)
# ----------------------------------------------------------

labels = [str(y) for y in YEARS]
x = np.arange(len(YEARS))
width = 0.35

plt.figure(figsize=(18, 8))

# Demand (standalone bar)
bars_load = plt.bar(
    x - width/2,
    load_gwh,
    width,
    label="Demand (Load)",
    color="#4b4b4b"
)

# Stacked generation
bars_solar = plt.bar(
    x + width/2,
    solar_gwh,
    width,
    label="Solar",
    color="#fae70f"
)

bars_hydro = plt.bar(
    x + width/2,
    hydro_gwh,
    width,
    bottom=solar_gwh,
    label="Hydro",
    color="#440dfa"
)

bars_imports = plt.bar(
    x + width/2,
    imports_gwh,
    width,
    bottom=solar_gwh + hydro_gwh,
    label="Imports",
    color="#069832"
)

bars_unmet = plt.bar(
    x + width/2,
    unmet_gwh,
    width,
    bottom=solar_gwh + hydro_gwh + imports_gwh,
    label="Unmet",
    color="#e50910"
)

# ----------------------------------------------------------
# ADD CENTERED LABELS
# ----------------------------------------------------------

# Demand labels
label_center(load_gwh, np.zeros_like(load_gwh), x - width/2)

# Stacked labels
label_center(solar_gwh, np.zeros_like(solar_gwh), x + width/2)
label_center(hydro_gwh, solar_gwh, x + width/2)
label_center(imports_gwh, solar_gwh + hydro_gwh, x + width/2)

# Unmet (TOP of stack)
label_top(unmet_gwh, solar_gwh + hydro_gwh + imports_gwh, x + width/2)

# ----------------------------------------------------------
# FORMATTING
# ----------------------------------------------------------

plt.xticks(x, labels, fontsize=12)
plt.ylabel("Annual Energy (GWh)")
#plt.title("Annual Energy Comparison per Planning Year (GWh)")
plt.legend()
plt.grid(axis="y", alpha=0.25)

plt.tight_layout()
gwh_plot = os.path.join(UNMET_DIR, "stacked_annual_energy_GWh.png")
plt.savefig(gwh_plot, dpi=200)
plt.show()

print("Saved GWh plot:", gwh_plot)