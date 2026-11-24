import pypsa
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# ---------------------------------------
# SETTINGS
# ---------------------------------------
YEARS = [2025, 2026, 2027, 2028, 2029, 2030, 2035, 2040, 2045, 2050]
RESERVE_MARGIN = 0.15
PEAK_HOURS = 100
STORAGE_PEAK_DURATION = 4.0
IMPORT_CREDIT = 1.0

firm_capacity = []
peak_loads = []

# ---------------------------------------
# LOOP THROUGH YEARS
# ---------------------------------------
for year in YEARS:

    n = pypsa.Network(f"networks/m300/B/solved_{year}.nc")

    # Peak load
    total_load = n.loads_t.p_set.sum(axis=1)
    peak = total_load.max()
    peak_loads.append(peak)

    peak_hours = total_load.nlargest(PEAK_HOURS).index

    row = {"year": year}

    # -----------------------------------
    # HYDRO (100% firm)
    # -----------------------------------
    hydro = n.generators[n.generators.carrier == "hydro"]
    row["Hydro"] = hydro.p_nom_opt.sum()

    # -----------------------------------
    # SOLAR (ELCC-style)
    # -----------------------------------
    solar = n.generators[n.generators.carrier == "solar"]
    if not solar.empty:
        cf = n.generators_t.p_max_pu.loc[peak_hours, solar.index].mean()
        row["Solar"] = (solar.p_nom_opt * cf).sum()
    else:
        row["Solar"] = 0.0

    # -----------------------------------
    # WIND (ELCC-style)
    # -----------------------------------
    wind = n.generators[n.generators.carrier == "wind"]
    if not wind.empty:
        cf = n.generators_t.p_max_pu.loc[peak_hours, wind.index].mean()
        row["Wind"] = (wind.p_nom_opt * cf).sum()
    else:
        row["Wind"] = 0.0

    # -----------------------------------
    # STORAGE (power credit)
    # -----------------------------------
    storage = n.storage_units
    if not storage.empty:
        credit = (storage.max_hours / STORAGE_PEAK_DURATION).clip(0, 1)
        row["Storage"] = (storage.p_nom_opt * credit).sum()
    else:
        row["Storage"] = 0.0

    # -----------------------------------
    # IMPORTS (capacity credit)
    # -----------------------------------
    imports = n.generators[n.generators.carrier == "imports"]
    row["Imports"] = IMPORT_CREDIT * imports.p_nom.sum()

    firm_capacity.append(row)

# ---------------------------------------
# DATAFRAMES
# ---------------------------------------
fc = pd.DataFrame(firm_capacity).set_index("year")
peak_loads = pd.Series(peak_loads, index=YEARS)
reserve_req = peak_loads * (1 + RESERVE_MARGIN)

# ---------------------------------------
# PLOT
# ---------------------------------------
fig, ax = plt.subplots(figsize=(12, 6))

bottom = np.zeros(len(fc))

colors = {
    "Hydro": "#3b4cc0",
    "Solar": "#f9e721",
    "Wind": "#27c4c2",
    "Storage": "#000000",
    "Imports": "#1a9850"
}

for tech in ["Solar", "Wind", "Hydro", "Storage", "Imports"]:
    ax.bar(
        fc.index,
        fc[tech],
        bottom=bottom,
        label=tech,
        color=colors[tech]
    )
    bottom += fc[tech].values

# Overlay peak load and reserve
ax.plot(fc.index, peak_loads, "ko-", label="Peak load")
ax.plot(fc.index, reserve_req, "r--o", label="Peak load + 15% reserve")

ax.set_ylabel("Firm capacity (MW)")
ax.set_xlabel("Year")
ax.set_title("Firm Capacity Composition vs Peak Load (M300)")
ax.legend(ncol=3)
ax.grid(axis="y", alpha=0.3)

plt.tight_layout()
plt.show()
