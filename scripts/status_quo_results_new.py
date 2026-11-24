import pandas as pd
import matplotlib.pyplot as plt
import os
import numpy as np

# ----------------------------------------------------------
# USER SETTINGS
# ----------------------------------------------------------

GEN_PROF_DIR = "data/generator_profiles_scenario1_m300"
LOAD_DIR = "data/Scenario1/loads_m300_supply_end"
UNMET_DIR = "results/unmet_demand_m300"


YEARS = [2025, 2026, 2027, 2028, 2029, 2030, 2035, 2040, 2045, 2050]

solar_name = "Ramarothole"
hydro_name = "Muela"
imports_name = "Maseru bulk"

# ----------------------------------------------------------
# STORAGE ARRAYS
# ----------------------------------------------------------

load_total = []
solar_total = []
hydro_total = []
imports_total = []
unmet_total = []

load_peak = []
solar_peak = []
hydro_peak = []
imports_peak = []
unmet_peak_calc = []

evening_load = []
evening_solar = []
evening_hydro = []
evening_imports = []
evening_unmet = []
# ----------------------------------------------------------
# LOOP THROUGH YEARS
# ----------------------------------------------------------

for year in YEARS:

    # -------- LOAD --------
    load_file = os.path.join(LOAD_DIR, f"load_timeseries_{year}_supply_end.xlsx")
    df_load = pd.read_excel(load_file, sheet_name="Sheet1")

    p_cols = [c for c in df_load.columns if c.endswith("_p")]

    # Hourly total load (MW)
    load_ts = df_load[p_cols].sum(axis=1)

    # Annual energy (MWh)
    load_total.append(load_ts.sum())

    # Identify peak load hour
    peak_load_idx = load_ts.idxmax()
    peak_load = load_ts.loc[peak_load_idx]
    load_peak.append(peak_load)

    # -------- GENERATION --------
    gen_file = os.path.join(GEN_PROF_DIR, f"generator_profiles_scenario1_{year}.xlsx")
    df_gen = pd.read_excel(gen_file, sheet_name="Sheet2")

    solar_ts = df_gen[solar_name]
    hydro_ts = df_gen[hydro_name]
    imports_ts = df_gen[imports_name]

    # Annual energy (MWh)
    solar_total.append(solar_ts.sum())
    hydro_total.append(hydro_ts.sum())
    imports_total.append(imports_ts.sum())

    # Values at peak load hour
    peak_solar = solar_ts.loc[peak_load_idx]
    peak_hydro = hydro_ts.loc[peak_load_idx]
    peak_imports = imports_ts.loc[peak_load_idx]

    solar_peak.append(peak_solar)
    hydro_peak.append(peak_hydro)
    imports_peak.append(peak_imports)

    # -------- PEAK UNMET LOAD (LOAD-REFERENCED) --------
    peak_unmet = max(
        0,
        peak_load - (peak_hydro + peak_imports + peak_solar)
    )
    unmet_peak_calc.append(peak_unmet)

    # -------- UNMET ENERGY (FROM MODEL OUTPUT) --------
    unmet_file = os.path.join(UNMET_DIR, f"unmet_demand_hourly_{year}.csv")
    df_unmet = pd.read_csv(unmet_file)
    unmet_total.append(df_unmet["unmet"].sum())


        # -------- EVENING PEAK (18:00–21:00) --------
    # assume index is datetime
    df_load.index = pd.to_datetime(df_load.iloc[:,0], errors="coerce")

    evening_mask = (df_load.index.hour >= 18) & (df_load.index.hour <= 21)
    evening_ts = load_ts[evening_mask]

    if not evening_ts.empty:
        evening_idx = evening_ts.idxmax()
        e_load = load_ts.loc[evening_idx]

        e_solar = solar_ts.loc[evening_idx]
        e_hydro = hydro_ts.loc[evening_idx]
        e_imports = imports_ts.loc[evening_idx]

        e_unmet = max(
            0,
            e_load - (e_solar + e_hydro + e_imports)
        )

    else:
        e_load, e_solar, e_hydro, e_imports, e_unmet = 0,0,0,0,0

    evening_load.append(e_load)
    evening_solar.append(e_solar)
    evening_hydro.append(e_hydro)
    evening_imports.append(e_imports)
    evening_unmet.append(e_unmet)

# ----------------------------------------------------------
# CONVERT ENERGY TO GWh
# ----------------------------------------------------------

load_gwh = np.array(load_total) / 1000
solar_gwh = np.array(solar_total) / 1000
hydro_gwh = np.array(hydro_total) / 1000
imports_gwh = np.array(imports_total) / 1000
unmet_gwh = np.array(unmet_total) / 1000

# ----------------------------------------------------------
# PEAK POWER ARRAYS (MW)
# ----------------------------------------------------------

load_mw = np.array(load_peak)
solar_mw = np.array(solar_peak)
hydro_mw = np.array(hydro_peak)
imports_mw = np.array(imports_peak)
unmet_mw = np.array(unmet_peak_calc)

evening_load_mw = np.array(evening_load)
evening_solar_mw = np.array(evening_solar)
evening_hydro_mw = np.array(evening_hydro)
evening_imports_mw = np.array(evening_imports)
evening_unmet_mw = np.array(evening_unmet)

# ----------------------------------------------------------
# COMMON PLOT SETTINGS
# ----------------------------------------------------------

labels = [str(y) for y in YEARS]
x = np.arange(len(YEARS))
width = 0.18

def label_bars(bars):
    for bar in bars:
        h = bar.get_height()
        plt.text(
            bar.get_x() + bar.get_width() / 2,
            h,
            f"{h:.1f}",
            ha="center",
            va="bottom",
            fontsize=9
        )


# ----------------------------------------------------------
# HELPER: CENTER LABELS FOR STACKED BARS
# ----------------------------------------------------------

def label_center(values, bottoms, x_pos):
    for i in range(len(values)):
        if values[i] > 0.1:
            plt.text(
                x_pos[i],
                bottoms[i] + values[i] / 2,
                f"{values[i]:.1f}",
                ha="center",
                va="center",
                color="Black",
                fontsize=9,
                
            )

# ----------------------------------------------------------
# PLOT: STACKED GENERATION vs DEMAND (PEAK MW)
# ----------------------------------------------------------
labels = [str(y) for y in YEARS]
x = np.arange(len(YEARS))
width = 0.35

plt.figure(figsize=(18, 8))

# Demand bar
bars_load = plt.bar(
    x - width/2,
    load_mw,
    width,
    label="Morning load",
    color="#4b4b4b"
)

# Stacked generation
bars_solar = plt.bar(
    x + width/2,
    solar_mw,
    width,
    label="Solar",
    color="#fae70f"
)

bars_hydro = plt.bar(
    x + width/2,
    hydro_mw,
    width,
    bottom=solar_mw,
    label="Hydro",
    color="#440dfa"
)

bars_imports = plt.bar(
    x + width/2,
    imports_mw,
    width,
    bottom=solar_mw + hydro_mw,
    label="Imports",
    color="#069832"
)

bars_unmet = plt.bar(
    x + width/2,
    unmet_mw,
    width,
    bottom=solar_mw + hydro_mw + imports_mw,
    label="Unmet",
    color="#e50910"
)

# ----------------------------------------------------------
# ADD CENTERED LABELS
# ----------------------------------------------------------

# Demand labels
label_center(load_mw, np.zeros_like(load_mw), x - width/2)

# Stacked labels
label_center(solar_mw, np.zeros_like(solar_mw), x + width/2)
label_center(hydro_mw, solar_mw, x + width/2)
label_center(imports_mw, solar_mw + hydro_mw, x + width/2)
label_center(unmet_mw, solar_mw + hydro_mw + imports_mw, x + width/2)

# ----------------------------------------------------------
# FORMATTING
# ----------------------------------------------------------

plt.xticks(x, labels)
plt.ylabel("Power (MW)")
#plt.title("Peak Power Balance as System Peak")
plt.legend()
plt.grid(axis="y", alpha=0.25)

plt.tight_layout()
plt.savefig(os.path.join(UNMET_DIR, "stacked_peak_vs_demand.png"), dpi=200)
plt.show()

# ----------------------------------------------------------
# PLOT: EVENING PEAK STACKED (MW)
# ----------------------------------------------------------

plt.figure(figsize=(18, 8))

# Demand
plt.bar(
    x - width/2,
    evening_load_mw,
    width,
    label="Evening Load",
    color="#4b4b4b"
)

# Supply stack
b1 = evening_solar_mw
b2 = b1 + evening_hydro_mw
b3 = b2 + evening_imports_mw

plt.bar(x + width/2, evening_solar_mw, width, label="Solar", color="#fae70f")
plt.bar(x + width/2, evening_hydro_mw, width, bottom=b1, label="Hydro", color="#440dfa")
plt.bar(x + width/2, evening_imports_mw, width, bottom=b2, label="Imports", color="#069832")
plt.bar(x + width/2, evening_unmet_mw, width, bottom=b3, label="Unmet", color="#e50910")

# Labels
label_center(evening_load_mw, np.zeros_like(evening_load_mw), x - width/2)
label_center(evening_solar_mw, np.zeros_like(evening_solar_mw), x + width/2)
label_center(evening_hydro_mw, b1, x + width/2)
label_center(evening_imports_mw, b2, x + width/2)

# Unmet at top
for i in range(len(evening_unmet_mw)):
    if evening_unmet_mw[i] > 0.1:
        plt.text(
            x[i] + width/2,
            b3[i] + evening_unmet_mw[i],
            f"{evening_unmet_mw[i]:.1f}",
            ha="center",
            va="bottom",
            color="black",
            fontsize=9
        )

plt.xticks(x, labels)
plt.ylabel("Power (MW)")
plt.title("Evening Peak Capacity Balance (18:00–21:00)")
plt.legend()
plt.grid(axis="y", alpha=0.25)

plt.tight_layout()
plt.savefig(os.path.join(UNMET_DIR, "evening_peak_vs_demand.png"), dpi=200)
plt.show()