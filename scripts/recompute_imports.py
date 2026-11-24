import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import os

# ----------------------------------------------------------
# USER SETTINGS
# ----------------------------------------------------------
YEARS = [2025, 2026, 2027, 2028, 2029, 2030, 2035, 2040, 2045, 2050]

# ---- STATUS QUO ----
LOAD_DIR_SQ  = "data/Scenario1/loads_status_quo_supply_end"
UNMET_DIR_SQ = "results/unmet_demand_status_quo"

# ---- M300 ----
LOAD_DIR_M300  = "data/Scenario1/loads_m300_supply_end"
UNMET_DIR_M300 = "results/unmet_demand_m300"

# Output
OUT_FILE = "results/unmet_demand_overlay_SQ_vs_M300.png"

# ----------------------------------------------------------
# FUNCTION TO COMPUTE % UNMET DEMAND
# ----------------------------------------------------------
def compute_unmet_percent(load_dir, unmet_dir):
    total_load_mwh = []
    total_unmet_mwh = []

    for year in YEARS:

        # -------- LOAD --------
        load_file = os.path.join(load_dir, f"load_timeseries_{year}_supply_end.xlsx")
        df_load = pd.read_excel(load_file, sheet_name="Sheet1")

        p_cols = [c for c in df_load.columns if c.endswith("_p")]
        annual_load_mwh = df_load[p_cols].to_numpy().sum()
        total_load_mwh.append(annual_load_mwh)

        # -------- UNMET DEMAND --------
        unmet_file = os.path.join(unmet_dir, f"unmet_demand_monthly_{year}.csv")
        df_unmet = pd.read_csv(unmet_file)

        annual_unmet_mwh = df_unmet["unmet"].sum()
        total_unmet_mwh.append(annual_unmet_mwh)

    total_load_mwh = np.array(total_load_mwh)
    total_unmet_mwh = np.array(total_unmet_mwh)

    return (total_unmet_mwh / total_load_mwh) * 100


# ----------------------------------------------------------
# COMPUTE BOTH SERIES
# ----------------------------------------------------------
unmet_sq   = compute_unmet_percent(LOAD_DIR_SQ, UNMET_DIR_SQ)
unmet_m300 = compute_unmet_percent(LOAD_DIR_M300, UNMET_DIR_M300)

# ----------------------------------------------------------
# OVERLAY PLOT
# ----------------------------------------------------------
plt.figure(figsize=(14, 6))

plt.plot(
    YEARS,
    unmet_sq,
    marker="o",
    linewidth=2,
    label="BAU",
    color="#1f77b4"
)

plt.plot(
    YEARS,
    unmet_m300,
    marker="s",
    linewidth=2,
    label="M300",
    color="#d62728"
)

plt.xlabel("Planning Year", fontsize=12)
plt.ylabel("Unmet Demand (%)", fontsize=12)
#plt.title("Unmet Demand Percentage: Status Quo vs M300", fontsize=15)

plt.legend()
plt.grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig(OUT_FILE, dpi=200)
plt.show()

print("Saved overlay unmet demand plot:", OUT_FILE)
