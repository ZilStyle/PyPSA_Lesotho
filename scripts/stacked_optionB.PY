import pypsa
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
import numpy as np

# ---------------------------------------
# SETTINGS
# ---------------------------------------
YEARS = [2025, 2026, 2027, 2028, 2029, 2030, 2035, 2040, 2045, 2050]
NETWORK_DIR = Path("networks/BAU/B_NOCAP")
OUT_DIR = Path("results/BAU/B_NOCAP")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------
# COLORS
# ---------------------------------------
COLORS = {
    "load":               "#4b4b4b",
    "battery_charge":     "#9e9e9e",
    "export":             "#7b2cbf",
    "unmet":              "#e50910",
    "solar":              "#fae70f",
    "wind":               "#17becf",
    "hydro":              "#440dfa",   # Muela baseload — dark blue
    "oxbow":              "#00bfff",   # Oxbow peaking — sky blue
    "battery_discharge":  "#000000",
    "imports":            "#069832",
}

SUPPLY_STACK = ["solar", "wind", "hydro", "oxbow", "battery_discharge", "imports"]

# ---------------------------------------
# HELPER — centre labels on bars
# ---------------------------------------
def add_center_labels(ax, container, color="black", fmt="{:.0f}", fontsize=8):
    for rect in container:
        h = rect.get_height()
        if h > 1.0:
            ax.text(
                rect.get_x() + rect.get_width() / 2,
                rect.get_y() + h / 2,
                fmt.format(h),
                ha="center", va="center",
                fontsize=fontsize, color=color, clip_on=True,
            )


# ---------------------------------------
# HELPER — split hydro vs oxbow
# ---------------------------------------
def get_hydro_oxbow(n, snap=None):
    """
    Return (hydro_value, oxbow_value) for either a snapshot (MW)
    or the full year (MWh / 1000 = GWh).
    """
    oxbow_gens = n.generators.index[
        n.generators.index.str.contains("Oxbow", case=False)
    ]
    hydro_gens = n.generators.index[
        (n.generators.carrier == "hydro") &
        ~n.generators.index.str.contains("Oxbow", case=False)
    ]

    if snap is not None:
        hydro_val = float(n.generators_t.p.loc[snap, hydro_gens].sum()) if len(hydro_gens) > 0 else 0.0
        oxbow_val = float(n.generators_t.p.loc[snap, oxbow_gens].sum()) if len(oxbow_gens) > 0 else 0.0
    else:
        hydro_val = n.generators_t.p[hydro_gens].sum().sum() / 1000 if len(hydro_gens) > 0 else 0.0
        oxbow_val = n.generators_t.p[oxbow_gens].sum().sum() / 1000 if len(oxbow_gens) > 0 else 0.0

    return hydro_val, oxbow_val


# ================================================================
# SECTION 1 — ANNUAL ENERGY BALANCE
# ================================================================
print("\n" + "="*60)
print("SECTION 1: Annual Energy Balance")
print("="*60)

records = []

for year in YEARS:
    n = pypsa.Network(NETWORK_DIR / f"solved_{year}.nc")

    load_gwh = n.loads_t.p.sum().sum() / 1000

    batt_chg_gwh = (
        n.storage_units_t.p_store.sum().sum() / 1000
        if not n.storage_units.empty else 0.0
    )

    gen_gwh = (
        n.generators_t.p
        .groupby(n.generators.carrier, axis=1)
        .sum()
        .sum() / 1000
    )

    batt_dis_gwh = (
        n.storage_units_t.p_dispatch.sum().sum() / 1000
        if not n.storage_units.empty else 0.0
    )

    export_gens = n.generators.index[n.generators.carrier == "export"]
    export_gwh = (
        -n.generators_t.p[export_gens].sum().sum() / 1000
        if len(export_gens) > 0 else 0.0
    )

    hydro_gwh, oxbow_gwh = get_hydro_oxbow(n)

    print(f"  {year} | Load={load_gwh:.0f} GWh | Solar={gen_gwh.get('solar',0):.0f} | "
          f"Wind={gen_gwh.get('wind',0):.0f} | Hydro={hydro_gwh:.0f} | "
          f"Oxbow={oxbow_gwh:.0f} | Imports={gen_gwh.get('imports',0):.0f} | "
          f"Export={export_gwh:.0f} | Battery={batt_dis_gwh:.0f}")

    records.append({
        "year":               year,
        "load":               load_gwh,
        "battery_charge":     batt_chg_gwh,
        "export":             export_gwh,
        "solar":              gen_gwh.get("solar", 0.0),
        "wind":               gen_gwh.get("wind", 0.0),
        "hydro":              hydro_gwh,
        "oxbow":              oxbow_gwh,
        "battery_discharge":  batt_dis_gwh,
        "imports":            gen_gwh.get("imports", 0.0),
        "unmet":              gen_gwh.get("load_shedding", 0.0),
    })

df = pd.DataFrame(records).set_index("year").fillna(0.0)

labels = df.index.astype(str)
x = np.arange(len(labels))
bar_w = 0.35

fig, ax = plt.subplots(figsize=(15, 7))

# Demand bar
demand_x = x - bar_w / 2
bottom = np.zeros(len(x))

c_load = ax.bar(demand_x, df["load"], bar_w, bottom=bottom, label="Load", color=COLORS["load"])
add_center_labels(ax, c_load, color="white")
bottom += df["load"]

c_bchg = ax.bar(demand_x, df["battery_charge"], bar_w, bottom=bottom, label="Battery charging", color=COLORS["battery_charge"])
add_center_labels(ax, c_bchg)
bottom += df["battery_charge"]

c_export = ax.bar(demand_x, df["export"], bar_w, bottom=bottom, label="Exports/Excess", color=COLORS["export"])
add_center_labels(ax, c_export, color="white")
bottom += df["export"]

c_unmet = ax.bar(demand_x, df["unmet"], bar_w, bottom=bottom, label="Unmet demand", color=COLORS["unmet"])
add_center_labels(ax, c_unmet, color="white")

# Supply bar
supply_x = x + bar_w / 2
bottom = np.zeros(len(x))

SUPPLY_LABELS = {
    "solar":              "Solar",
    "wind":               "Wind",
    "hydro":              "Hydro (Muela)",
    "oxbow":              "Oxbow Peaking",
    "battery_discharge":  "Battery Discharge",
    "imports":            "Imports",
}

for c in SUPPLY_STACK:
    label_color = "white" if c == "battery_discharge" else "black"
    bars = ax.bar(supply_x, df[c], bar_w, bottom=bottom, label=SUPPLY_LABELS[c], color=COLORS[c])
    add_center_labels(ax, bars, color=label_color)
    bottom += df[c]

max_h = max(
    (df["load"] + df["battery_charge"] + df["export"] + df["unmet"]).max(),
    (df[SUPPLY_STACK].sum(axis=1)).max()
)
ax.set_ylim(0, max_h * 1.25)
ax.set_xticks(x)
ax.set_xticklabels(labels)
ax.set_ylabel("Annual Energy (GWh)")
ax.legend(loc="center left", bbox_to_anchor=(1.02, 0.5))
ax.grid(axis="y", alpha=0.25)
plt.tight_layout()
plt.savefig(OUT_DIR / "annual_energy_balance_exports_on_demand.png", dpi=300)
plt.close()
print("\nSaved: annual_energy_balance_exports_on_demand.png")


# ================================================================
# SECTION 2 — MORNING PEAK CAPACITY BALANCE
# ================================================================
print("\n" + "="*60)
print("SECTION 2: Morning Peak Capacity Balance")
print("="*60)

records = []

for year in YEARS:
    n = pypsa.Network(NETWORK_DIR / f"solved_{year}.nc")

    total_load_ts = n.loads_t.p.sum(axis=1)
    peak_snap = total_load_ts.idxmax()

    print(f"\n[Morning Peak] Year {year}")
    print(f"  Timestamp : {peak_snap}  |  Load: {total_load_ts.loc[peak_snap]:.1f} MW")

    gen_peak = n.generators_t.p.loc[peak_snap].groupby(n.generators.carrier).sum()

    batt_dis = n.storage_units_t.p_dispatch.loc[peak_snap].sum() if not n.storage_units.empty else 0.0
    batt_chg = n.storage_units_t.p_store.loc[peak_snap].sum()    if not n.storage_units.empty else 0.0

    export_gens = n.generators.index[n.generators.carrier == "export"]
    export_mw = -n.generators_t.p.loc[peak_snap, export_gens].sum() if len(export_gens) > 0 else 0.0

    hydro_mw, oxbow_mw = get_hydro_oxbow(n, snap=peak_snap)

    records.append({
        "year":               year,
        "load":               float(total_load_ts.loc[peak_snap]),
        "battery_charge":     float(batt_chg),
        "export":             float(export_mw),
        "solar":              float(gen_peak.get("solar", 0.0)),
        "wind":               float(gen_peak.get("wind", 0.0)),
        "hydro":              hydro_mw,
        "oxbow":              oxbow_mw,
        "battery_discharge":  float(batt_dis),
        "imports":            float(gen_peak.get("imports", 0.0)),
        "unmet":              float(gen_peak.get("load_shedding", 0.0)),
    })

pk = pd.DataFrame(records).set_index("year").fillna(0.0)

labels = pk.index.astype(str)
x = np.arange(len(labels))
bar_w = 0.35

fig, ax = plt.subplots(figsize=(15, 7))

demand_x = x - bar_w / 2
bottom = np.zeros(len(x))

c_load = ax.bar(demand_x, pk["load"], bar_w, bottom=bottom, label="Morning load", color=COLORS["load"])
add_center_labels(ax, c_load, color="white")
bottom += pk["load"]

c_bchg = ax.bar(demand_x, pk["battery_charge"], bar_w, bottom=bottom, label="Battery charging", color=COLORS["battery_charge"])
add_center_labels(ax, c_bchg, color="white")
bottom += pk["battery_charge"]

c_export = ax.bar(demand_x, pk["export"], bar_w, bottom=bottom, label="Exports/Excess", color=COLORS["export"])
add_center_labels(ax, c_export, color="white")
bottom += pk["export"]

c_unmet = ax.bar(demand_x, pk["unmet"], bar_w, bottom=bottom, label="Unmet demand", color=COLORS["unmet"])
add_center_labels(ax, c_unmet, color="white")

supply_x = x + bar_w / 2
bottom = np.zeros(len(x))

for c in SUPPLY_STACK:
    label_color = "white" if c == "battery_discharge" else "black"
    bars = ax.bar(supply_x, pk[c], bar_w, bottom=bottom, label=SUPPLY_LABELS[c], color=COLORS[c])
    add_center_labels(ax, bars, color=label_color)
    bottom += pk[c]

max_h = max(
    (pk["load"] + pk["battery_charge"] + pk["export"] + pk["unmet"]).max(),
    (pk[SUPPLY_STACK].sum(axis=1)).max()
)
ax.set_ylim(0, max_h * 1.25)
ax.set_xticks(x)
ax.set_xticklabels(labels)
ax.set_ylabel("Power (MW)")
ax.legend(loc="center left", bbox_to_anchor=(1.02, 0.5))
ax.grid(axis="y", alpha=0.25)
plt.tight_layout()
plt.savefig(OUT_DIR / "peak_power_balance_optionB_with_imports_exports.png", dpi=300)
plt.close()
print("\nSaved: peak_power_balance_optionB_with_imports_exports.png")


# ================================================================
# SECTION 3 — EVENING PEAK CAPACITY BALANCE (18:00–21:00)
# ================================================================
print("\n" + "="*60)
print("SECTION 3: Evening Peak Capacity Balance (18:00–21:00)")
print("="*60)

records = []

for year in YEARS:
    n = pypsa.Network(NETWORK_DIR / f"solved_{year}.nc")

    total_load_ts = n.loads_t.p.sum(axis=1)
    evening_ts = total_load_ts[
        (total_load_ts.index.hour >= 18) &
        (total_load_ts.index.hour <= 21)
    ]

    if evening_ts.empty:
        continue

    evening_snap = evening_ts.idxmax()

    print(f"\n[Evening Peak] Year {year}")
    print(f"  Timestamp : {evening_snap}  |  Load: {total_load_ts.loc[evening_snap]:.1f} MW")

    gen_evening = n.generators_t.p.loc[evening_snap].groupby(n.generators.carrier).sum()

    batt_dis = n.storage_units_t.p_dispatch.loc[evening_snap].sum() if not n.storage_units.empty else 0.0
    batt_chg = n.storage_units_t.p_store.loc[evening_snap].sum()    if not n.storage_units.empty else 0.0

    export_gens = n.generators.index[n.generators.carrier == "export"]
    export_mw = -n.generators_t.p.loc[evening_snap, export_gens].sum() if len(export_gens) > 0 else 0.0

    hydro_mw, oxbow_mw = get_hydro_oxbow(n, snap=evening_snap)

    records.append({
        "year":               year,
        "load":               float(total_load_ts.loc[evening_snap]),
        "battery_charge":     float(batt_chg),
        "export":             float(export_mw),
        "solar":              float(gen_evening.get("solar", 0.0)),
        "wind":               float(gen_evening.get("wind", 0.0)),
        "hydro":              hydro_mw,
        "oxbow":              oxbow_mw,
        "battery_discharge":  float(batt_dis),
        "imports":            float(gen_evening.get("imports", 0.0)),
        "unmet":              float(gen_evening.get("load_shedding", 0.0)),
    })

ev = pd.DataFrame(records).set_index("year").fillna(0.0)

labels = ev.index.astype(str)
x = np.arange(len(labels))
bar_w = 0.35

fig, ax = plt.subplots(figsize=(15, 7))

# LEFT BAR: Demand side (load, battery charging, exports, unmet)
demand_x = x - bar_w / 2
bottom = np.zeros(len(x))

# Plot load as the base (this is the total demand)
c_load = ax.bar(demand_x, ev["load"], bar_w, bottom=bottom, label="Evening load", color=COLORS["load"])
add_center_labels(ax, c_load, color="white")
# Don't add load to bottom - it's the target, not a stack component

# Now stack the "additional" demand components on top of each other
# These represent what's happening with the load
bottom = ev["load"].values  # Start from the load level

c_bchg = ax.bar(demand_x, ev["battery_charge"], bar_w, bottom=bottom, 
                label="Battery charging", color=COLORS["battery_charge"])
add_center_labels(ax, c_bchg, color="white")
bottom += ev["battery_charge"].values

c_export = ax.bar(demand_x, ev["export"], bar_w, bottom=bottom, 
                  label="Exports/Excess", color=COLORS["export"])
add_center_labels(ax, c_export, color="white")
bottom += ev["export"].values

c_unmet = ax.bar(demand_x, ev["unmet"], bar_w, bottom=bottom, 
                 label="Unmet demand", color=COLORS["unmet"])
add_center_labels(ax, c_unmet, color="white")

# RIGHT BAR: Supply side (solar, wind, hydro, oxbow, battery discharge, imports)
supply_x = x + bar_w / 2
bottom = np.zeros(len(x))

# Plot supply stack
for c in SUPPLY_STACK:
    label_color = "white" if c == "battery_discharge" else "black"
    bars = ax.bar(supply_x, ev[c], bar_w, bottom=bottom, 
                  label=SUPPLY_LABELS[c], color=COLORS[c])
    add_center_labels(ax, bars, color=label_color)
    bottom += ev[c].values

# Calculate the maximum value across both bars to set y-axis limit
max_demand = (ev["load"] + ev["battery_charge"] + ev["export"] + ev["unmet"]).max()
max_supply = ev[SUPPLY_STACK].sum(axis=1).max()
y_max = max(max_demand, max_supply) * 1.1  # Add 10% padding

# Round up to nearest 50
y_max = np.ceil(y_max / 50) * 50

ax.set_ylim(0, y_max)
ax.set_yticks(np.arange(0, y_max + 1, 50))
ax.set_xticks(x)
ax.set_xticklabels(labels)
ax.set_ylabel("Power (MW)")
ax.legend(loc="center left", bbox_to_anchor=(1.02, 0.5))
ax.grid(axis="y", alpha=0.25)

# Add a title or subtitle explaining the balance
ax.set_title("Evening Peak Capacity Balance (18:00-21:00)", fontsize=14, fontweight='bold')

plt.tight_layout()
plt.savefig(OUT_DIR / "evening_peak_balance_optionB.png", dpi=300, bbox_inches='tight')
plt.close()
print("\nSaved: evening_peak_balance_optionB.png")

print("\n" + "="*60)
print("All three plots saved successfully.")
print("="*60)