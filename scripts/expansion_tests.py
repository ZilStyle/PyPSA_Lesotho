import pypsa
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

# =================================================
# USER SETTINGS
# =================================================
YEAR = 2050
NETWORK_FILE = f"networks/BAU/B/solved_{YEAR}.nc"
OUTDIR = Path(f"results/B/diagnostics_{YEAR}")
OUTDIR.mkdir(parents=True, exist_ok=True)

# =================================================
# LOAD NETWORK
# =================================================
print("=" * 60)
print(f"OPTION B EXPANSION DIAGNOSTICS | YEAR {YEAR}")
print("=" * 60)

n = pypsa.Network(NETWORK_FILE)

# =================================================
# 1. OBJECTIVE
# =================================================
print("\n[1] Objective value")
print("Objective:", n.objective)

# =================================================
# 2. GENERATOR EXPANSION
# =================================================
print("\n[2] Generator expansion (MW)")

gen = n.generators.copy()
gen["delta_MW"] = gen["p_nom_opt"] - gen["p_nom"]

gen_by_carrier = (
    gen[["carrier", "p_nom", "p_nom_opt", "delta_MW"]]
    .groupby("carrier")
    .sum()
)

print(gen_by_carrier)

# =================================================
# 3. TRANSMISSION EXPANSION
# =================================================
print("\n[3] Transmission expansion")

lines = n.lines.copy()
lines["delta_MVA"] = lines["s_nom_opt"] - lines["s_nom"]

expanded_lines = lines[lines["delta_MVA"] > 1e-3]

print(expanded_lines[[
    "bus0", "bus1", "v_nom", "s_nom", "s_nom_opt", "delta_MVA"
]])

# =================================================
# 4. STORAGE EXPANSION & OPERATION (IMPROVED)
# =================================================
print("\n[4] Storage expansion and operation")

su = n.storage_units.copy()

# Ensure p_nom_opt exists (safety for non-optimised cases)
if "p_nom_opt" not in su.columns:
    su["p_nom_opt"] = su["p_nom"]

# Expansion calculation
su["delta_MW"] = su["p_nom_opt"] - su["p_nom"]

# Flag actual investments
su["expanded"] = su["delta_MW"] > 1e-3

# Clean display
display_cols = [
    "bus", "carrier",
    "p_nom", "p_nom_opt", "delta_MW",
    "expanded",
    "max_hours", "capital_cost",
    "p_nom_extendable"
]

print(su[display_cols].sort_values("p_nom_opt", ascending=False))
print(n.storage_units[["p_nom_max", "p_nom_extendable"]])
solar_buses = set(n.generators.loc[n.generators.carrier == "solar", "bus"])
battery_buses = set(n.storage_units["bus"].values)
print("Solar buses without battery:", solar_buses - battery_buses)
# =================================================
# 5. IMPORTS
# =================================================
print("\n[5] Imports")

imports = n.generators[n.generators.carrier == "imports"]
if not imports.empty:
    imp_energy = n.generators_t.p[imports.index].sum().sum()
    print(imports[["p_nom", "p_nom_opt"]])
    print(f"Imported energy (MWh): {imp_energy:.1f}")

# =================================================
# 6. EXPORTS (GENERATOR WITH NEGATIVE DISPATCH)
# =================================================
print("\n[6] Exports (generator model)")

export_gens = n.generators[n.generators.carrier == "export"]

if export_gens.empty:
    print("❌ No export generators found (carrier == 'export').")
else:
    print(export_gens[["bus", "p_nom", "p_nom_opt", "marginal_cost"]])

    exp_p = n.generators_t.p[export_gens.index].reindex(n.snapshots).fillna(0.0)

    # exporting corresponds to negative dispatch
    exp_MWh = (-exp_p.clip(upper=0.0)).sum().sum()
    exp_peak_MW = (-exp_p.min().min())  # most negative value is max export magnitude

    print(f"Exported energy (MWh): {exp_MWh:.1f}")
    print(f"Peak export (MW):      {exp_peak_MW:.2f}")

    # Export revenue (if marginal_cost is export price, positive)
    exp_price = export_gens["marginal_cost"]
    revenue = (-exp_p.clip(upper=0.0)).sum() * exp_price
    print(f"Export revenue (USD):  {revenue.sum():.2f}")



# =================================================
# 8. PEAK LOAD WINDOWS
# =================================================
load = n.loads_t.p_set.sum(axis=1)
peak_ts = load.idxmax()

month_start = peak_ts.replace(day=1, hour=0, minute=0, second=0)
month_end = (month_start + pd.offsets.MonthEnd(1)).replace(
    hour=23, minute=59, second=59
)

windows = {
    "daily": (
        peak_ts.floor("D"),
        peak_ts.floor("D") + pd.Timedelta(days=1)
    ),
    "weekly": (
        peak_ts - pd.Timedelta(days=3),
        peak_ts + pd.Timedelta(days=3)
    ),
    "monthly": (
        month_start,
        month_end
    )
}

import pandas as pd
import numpy as np

# -------------------------------------------------
# IDENTIFY EXPORT + STORAGE
# -------------------------------------------------
export_gens = n.generators[n.generators.carrier == "export"].index
storage_units = n.storage_units.index

if len(export_gens) == 0:
    raise ValueError("No export generator found (carrier == 'export').")

# -------------------------------------------------
# TIME SERIES
# -------------------------------------------------
export_p = n.generators_t.p[export_gens].sum(axis=1)     # MW (negative = export)
storage_p = n.storage_units_t.p.sum(axis=1)              # MW (negative = charge)

# -------------------------------------------------
# BOOLEAN FLAGS
# -------------------------------------------------
is_exporting = export_p < -1e-3
is_charging  = storage_p < -1e-3

# -------------------------------------------------
# COMBINED TABLE
# -------------------------------------------------
export_charge_df = pd.DataFrame({
    "export_MW": -export_p.clip(upper=0.0),     # positive MW exported
    "storage_charge_MW": -storage_p.clip(upper=0.0),  # positive MW charging
    "exporting": is_exporting,
    "charging": is_charging
})

export_charge_df["export_and_charge"] = (
    export_charge_df["exporting"] & export_charge_df["charging"]
)

total_hours = len(export_charge_df)

hours_export = export_charge_df["exporting"].sum()
hours_charge = export_charge_df["charging"].sum()
hours_both   = export_charge_df["export_and_charge"].sum()

print("Total hours:", total_hours)
print("Hours exporting:", hours_export)
print("Hours charging battery:", hours_charge)
print("Hours exporting AND charging:", hours_both)

print("\nPercentages of year:")
print(f"Exporting: {100*hours_export/total_hours:.1f}%")
print(f"Charging:  {100*hours_charge/total_hours:.1f}%")
print(f"Both:      {100*hours_both/total_hours:.1f}%")

export_energy = export_charge_df["export_MW"].sum()
charge_energy = export_charge_df["storage_charge_MW"].sum()

export_during_charge = export_charge_df.loc[
    export_charge_df["export_and_charge"], "export_MW"
].sum()

print("\nEnergy totals (MWh):")
print(f"Total export energy:        {export_energy:.1f}")
print(f"Total storage charge:       {charge_energy:.1f}")
print(f"Export during charging:     {export_during_charge:.1f}")
print(f"Share of export during charge: "
      f"{100*export_during_charge/export_energy:.1f}%")

events = export_charge_df[
    export_charge_df["exporting"] | export_charge_df["charging"]
].copy()

events["hour"] = events.index.hour
events["month"] = events.index.month

print(events.head(24))

import matplotlib.pyplot as plt

fig, ax = plt.subplots(figsize=(14,5))

export_charge_df["export_MW"].plot(ax=ax, label="Export (MW)")
export_charge_df["storage_charge_MW"].plot(ax=ax, label="Storage charge (MW)")

ax.set_ylabel("MW")
ax.set_title(f"{YEAR}: Export vs Battery Charging")
ax.legend()
plt.tight_layout()
plt.show()

hourly = export_charge_df.groupby(export_charge_df.index.hour).sum()

hourly[["export_MW","storage_charge_MW"]].plot(
    kind="bar", figsize=(14,5)
)
plt.title("Average Export and Battery Charging by Hour of Day")
plt.ylabel("MWh")
plt.xlabel("Hour")
plt.tight_layout()
plt.show()

# -----------------------------
# IDENTIFY EXPORT GENERATOR
# -----------------------------
export_gens = n.generators[n.generators.carrier == "export"].index
assert len(export_gens) == 1, "Expected exactly one export generator"

export_name = export_gens[0]

export_p = n.generators_t.p[export_name]        # MW (negative = export)
export_MW = -export_p.clip(upper=0.0)            # positive MW exported

# -----------------------------
# GENERATION BY CARRIER
# -----------------------------
gen_p = n.generators_t.p.copy()

# remove export itself from generation pool
gen_p = gen_p.drop(columns=[export_name])

gen_by_carrier = (
    gen_p.T
    .groupby(n.generators.loc[gen_p.columns, "carrier"])
    .sum()
    .T
)

# only positive generation can feed exports
gen_by_carrier = gen_by_carrier.clip(lower=0.0)

# -----------------------------
# STORAGE DISCHARGE
# -----------------------------
storage_p = n.storage_units_t.p.copy()

storage_discharge = storage_p.clip(lower=0.0).sum(axis=1)  # MW

# -----------------------------
# TOTAL SUPPLY AVAILABLE TO EXPORT
# -----------------------------
supply_for_export = gen_by_carrier.sum(axis=1) + storage_discharge

# avoid division by zero
valid = (export_MW > 0) & (supply_for_export > 1e-6)

# -----------------------------
# EXPORT CONTRIBUTION BY CARRIER
# -----------------------------
export_contrib = {}

for carrier in gen_by_carrier.columns:
    share = gen_by_carrier.loc[valid, carrier] / supply_for_export.loc[valid]
    export_contrib[carrier] = (share * export_MW.loc[valid]).sum()

# storage as its own "carrier"
storage_share = storage_discharge.loc[valid] / supply_for_export.loc[valid]
export_contrib["storage"] = (storage_share * export_MW.loc[valid]).sum()

export_by_carrier = pd.Series(export_contrib).sort_values(ascending=False)

print("\nEXPORT CONTRIBUTION BY CARRIER (MWh):")
print(export_by_carrier)

print("\nEXPORT CONTRIBUTION SHARE (%):")
print(100 * export_by_carrier / export_by_carrier.sum())

imports = n.generators[n.generators.carrier == "imports"].index
assert len(imports) > 0, "No imports generators found"

imports_p = n.generators_t.p[imports].sum(axis=1)  # MW

# Domestic supply = generation + storage discharge (excluding imports)
domestic_supply = gen_by_carrier.sum(axis=1) + storage_discharge

valid_imp = imports_p > 1e-6

avoided_imports = {}

for carrier in gen_by_carrier.columns:
    share = gen_by_carrier.loc[valid_imp, carrier] / domestic_supply.loc[valid_imp]
    avoided_imports[carrier] = (share * imports_p.loc[valid_imp]).sum()

# storage contribution
storage_share_imp = storage_discharge.loc[valid_imp] / domestic_supply.loc[valid_imp]
avoided_imports["storage"] = (storage_share_imp * imports_p.loc[valid_imp]).sum()

avoided_imports_by_carrier = pd.Series(avoided_imports).sort_values(ascending=False)

print("\nIMPORT DISPLACEMENT BY CARRIER (MWh):")
print(avoided_imports_by_carrier)

print("\nIMPORT DISPLACEMENT SHARE (%):")
print(100 * avoided_imports_by_carrier / avoided_imports_by_carrier.sum())

summary = pd.DataFrame({
    "export_MWh": export_by_carrier,
    "export_share_%": 100 * export_by_carrier / export_by_carrier.sum(),
    "import_displacement_MWh": avoided_imports_by_carrier,
    "import_displacement_share_%": 100 * avoided_imports_by_carrier / avoided_imports_by_carrier.sum()
}).fillna(0.0)

print("\nEXPORT VS IMPORT DISPLACEMENT SUMMARY")
print(summary)

summary.to_csv(f"results/B/export_import_attribution_{YEAR}.csv")





# Technologies to evaluate
TECHS = ["solar", "wind", "hydro", "storage", "imports"]


# FIND SYSTEM PEAK HOUR
# ---------------------------------------
system_load = n.loads_t.p.sum(axis=1)
peak_snapshot = system_load.idxmax()
peak_load_mw = system_load.max()

print(f"Peak snapshot: {peak_snapshot}")
print(f"Peak load: {peak_load_mw:.2f} MW")

# ---------------------------------------
# INSTALLED CAPACITY
# ---------------------------------------
installed = {}

# Generators
for tech in ["solar", "wind", "hydro", "imports"]:
    installed[tech] = (
        n.generators.loc[n.generators.carrier == tech, "p_nom_opt"]
        .sum()
    )

# Storage (discharge capacity)
installed["storage"] = (
    n.storage_units["p_nom_opt"].sum()
    if not n.storage_units.empty else 0.0
)

# ---------------------------------------
# DISPATCH AT PEAK
# ---------------------------------------
dispatch = {}

# Generator dispatch
gen_peak = n.generators_t.p.loc[peak_snapshot]

for tech in ["solar", "wind", "hydro", "imports"]:
    gens = n.generators.index[n.generators.carrier == tech]
    dispatch[tech] = gen_peak[gens].sum() if len(gens) > 0 else 0.0

# Storage discharge at peak
if not n.storage_units.empty:
    dispatch["storage"] = (
        n.storage_units_t.p_dispatch.loc[peak_snapshot].sum()
    )
else:
    dispatch["storage"] = 0.0

# ---------------------------------------
# CAPACITY CREDIT
# ---------------------------------------
records = []

for tech in TECHS:
    cap = installed.get(tech, 0.0)
    disp = dispatch.get(tech, 0.0)

    credit = disp / cap if cap > 1e-6 else 0.0

    records.append({
        "technology": tech,
        "installed_capacity_MW": round(cap, 2),
        "dispatch_at_peak_MW": round(disp, 2),
        "capacity_credit": round(credit, 3)
    })

df = pd.DataFrame(records)

print("\nCAPACITY CREDIT RESULTS")
print(df)


print("\n--- BATTERY STATUS ---")
print(n.storage_units[["p_nom","p_nom_opt" ,"p_nom_extendable", "capital_cost", "max_hours"]])

print("\n--- IMPORTS STATUS ---")
print(n.generators.loc[
    n.generators.carrier == "imports",
    ["p_nom", "p_nom_extendable", "marginal_cost", "capital_cost"]
])