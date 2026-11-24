import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import os

# ----------------------------------------------------------
# USER SETTINGS
# ----------------------------------------------------------
LOAD_DIR = "data/Scenario1/load_BAU_supply_end"
UNMET_DIR = "results/unmet_demand_BAU"

YEARS = [2025, 2026, 2027, 2028, 2029, 2030, 2035, 2040, 2045, 2050]

# ----------------------------------------------------------
# CALCULATE ANNUAL LOAD AND UNMET ENERGY (MWh)
# ----------------------------------------------------------
total_load_mwh = []
total_unmet_mwh = []

for year in YEARS:

    # -------- LOAD --------
    load_file = os.path.join(LOAD_DIR, f"load_timeseries_{year}_supply_end.xlsx")
    df_load = pd.read_excel(load_file, sheet_name="Sheet1")

    p_cols = [c for c in df_load.columns if c.endswith("_p")]
    annual_load_mwh = df_load[p_cols].to_numpy().sum()
    total_load_mwh.append(annual_load_mwh)

    # -------- UNMET DEMAND --------
    unmet_file = os.path.join(UNMET_DIR, f"unmet_demand_monthly_{year}.csv")
    df_unmet = pd.read_csv(unmet_file)

    annual_unmet_mwh = df_unmet["unmet"].sum()
    total_unmet_mwh.append(annual_unmet_mwh)

# ----------------------------------------------------------
# % UNMET DEMAND
# ----------------------------------------------------------
total_load_mwh = np.array(total_load_mwh)
total_unmet_mwh = np.array(total_unmet_mwh)

unmet_percent = (total_unmet_mwh / total_load_mwh) * 100

# ----------------------------------------------------------
# LINE PLOT: % UNMET DEMAND PER YEAR
# ----------------------------------------------------------
plt.figure(figsize=(14, 6))

plt.plot(
    YEARS,
    unmet_percent,
    marker="o",
    linewidth=2
)

plt.xlabel("Planning Year", fontsize=12)
plt.ylabel("Unmet Demand (%)", fontsize=12)
#plt.title("Percentage of Unmet Demand per Planning Year", fontsize=15)
plt.grid(True, alpha=0.3)



plt.tight_layout()

out_file = os.path.join(UNMET_DIR, "percentage_unmet_demand_line.png")
plt.savefig(out_file, dpi=200)
plt.show()

print("Saved unmet demand percentage line plot:", out_file)
