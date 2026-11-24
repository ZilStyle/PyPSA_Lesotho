import pypsa
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
import numpy as np

# ---------------------------------------
# SETTINGS
# ---------------------------------------
YEARS = [2025, 2026, 2027, 2028, 2029, 2030, 2035, 2040, 2045, 2050]
NETWORK_DIR = Path("networks/A")
OUT_DIR = Path("results/A")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------
# COLORS
# ---------------------------------------
COLORS = {
    "load":              "#4b4b4b",
    "battery_charge":    "#9e9e9e",
    "unmet":             "#e50910",
    "solar":             "#fae70f",
    "wind":              "#17becf",
    "hydro":             "#440dfa",   # Muela baseload — dark blue
    "oxbow":             "#00bfff",   # Oxbow peaking  — sky blue
    "battery_discharge": "#000000",
    "imports":           "#069832",
}

SUPPLY_STACK = ["solar", "wind", "hydro", "oxbow", "battery_discharge", "imports"]

SUPPLY_LABELS = {
    "solar":              "Solar",
    "wind":               "Wind",
    "hydro":              "Hydro (Muela)",
    "oxbow":              "Oxbow Peaking",
    "battery_discharge":  "Battery Discharge",
    "imports":            "Imports",
}

# ============================================================
# HELPER — centre labels on bars
# ============================================================
def add_center_labels(ax, containers, fmt="{:.0f}", min_val=1.0, fontsize=8):
    for cont in containers:
        for rect in cont.patches:
            h = rect.get_height()
            if h > min_val:
                ax.text(
                    rect.get_x() + rect.get_width() / 2,
                    rect.get_y() + h / 2,
                    fmt.format(h),
                    ha="center", va="center",
                    color="white", fontsize=fontsize, clip_on=True
                )


# ============================================================
# HELPER — top-of-segment labels (for small segments like battery charge)
# ============================================================
def add_top_of_segment_labels(ax, container, fmt="{:.0f}", min_val=0.5, fontsize=8, color="black"):
    for rect in container.patches:
        h = rect.get_height()
        if h > min_val:
            ax.text(
                rect.get_x() + rect.get_width() / 2,
                rect.get_y() + h + 0.5,   # just above the top of the segment
                fmt.format(h),
                ha="center", va="bottom",
                color=color, fontsize=fontsize,
                clip_on=True
            )

# ============================================================
# HELPER — split Muela hydro vs Oxbow
# ============================================================
def get_hydro_oxbow(n, snap=None):
    """
    Returns (muela_hydro, oxbow) either as GWh (snap=None)
    or as MW at a specific snapshot.
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


# ============================================================
# PART A — ANNUAL ENERGY BALANCE
# ============================================================
print("\n" + "="*60)
print("SECTION 1: Annual Energy Balance")
print("="*60)

records = []

for year in YEARS:
    n = pypsa.Network(NETWORK_DIR / f"solved_{year}.nc")

    load_gwh = n.loads_t.p.sum().sum() / 1000

    gen_gwh = (
        n.generators_t.p
        .groupby(n.generators.carrier, axis=1)
        .sum()
        .sum() / 1000
    )

    if not n.storage_units.empty:
        batt_dis_gwh = n.storage_units_t.p_dispatch.sum().sum() / 1000
        batt_chg_gwh = n.storage_units_t.p_store.sum().sum()    / 1000
    else:
        batt_dis_gwh = batt_chg_gwh = 0.0

    hydro_gwh, oxbow_gwh = get_hydro_oxbow(n)

    print(f"  {year} | Load={load_gwh:.0f} GWh | Solar={gen_gwh.get('solar',0):.0f} | "
          f"Wind={gen_gwh.get('wind',0):.0f} | Hydro={hydro_gwh:.0f} | "
          f"Oxbow={oxbow_gwh:.0f} | Imports={gen_gwh.get('imports',0):.0f} | "
          f"Unmet={gen_gwh.get('load_shedding',0):.1f}")

    records.append({
        "year":              year,
        "load":              load_gwh,
        "battery_charge":    batt_chg_gwh,
        "solar":             gen_gwh.get("solar", 0.0),
        "wind":              gen_gwh.get("wind",  0.0),
        "hydro":             hydro_gwh,
        "oxbow":             oxbow_gwh,
        "battery_discharge": batt_dis_gwh,
        "imports":           gen_gwh.get("imports", 0.0),
        "unmet":             gen_gwh.get("load_shedding", 0.0),
    })

df = pd.DataFrame(records).set_index("year").fillna(0.0)
labels = df.index.astype(str)
x = np.arange(len(labels))
bar_w = 0.35

fig, ax = plt.subplots(figsize=(14, 6))

demand_x = x - bar_w / 2
supply_x = x + bar_w / 2

# Demand bar
demand_bottom = np.zeros(len(x))

c_load = ax.bar(demand_x, df["load"], bar_w, bottom=demand_bottom, label="Load", color=COLORS["load"])
demand_bottom += df["load"].values

c_bchg = ax.bar(demand_x, df["battery_charge"], bar_w, bottom=demand_bottom, label="Battery charging", color=COLORS["battery_charge"], alpha=0.7)
demand_bottom += df["battery_charge"].values

c_unmet = ax.bar(demand_x, df["unmet"], bar_w, bottom=demand_bottom, label="Unmet demand", color=COLORS["unmet"])

# Supply bar
supply_bottom = np.zeros(len(x))
supply_containers = []

for c in SUPPLY_STACK:
    bars = ax.bar(supply_x, df[c], bar_w, bottom=supply_bottom, label=SUPPLY_LABELS[c], color=COLORS[c])
    supply_containers.append(bars)
    supply_bottom += df[c].values

add_center_labels(ax, [c_load, c_unmet] + supply_containers)
add_top_of_segment_labels(ax, c_bchg, color="dimgray")

max_y = max(
    (df["load"] + df["battery_charge"] + df["unmet"]).max(),
    df[SUPPLY_STACK].sum(axis=1).max()
)
ax.set_ylim(0, max_y * 1.15)
ax.set_xticks(x)
ax.set_xticklabels(labels)
ax.set_ylabel("Annual Energy (GWh)")
ax.legend(loc="center left", bbox_to_anchor=(1.02, 0.5))
ax.grid(axis="y", alpha=0.25)
plt.tight_layout()
plt.savefig(OUT_DIR / "m300_annual_energy_balance_2bars.png", dpi=300)
plt.close()
print("Saved: m300_annual_energy_balance_2bars.png")


# ============================================================
# PART B — SYSTEM PEAK CAPACITY BALANCE
# ============================================================
print("\n" + "="*60)
print("SECTION 2: System Peak Capacity Balance")
print("="*60)

records = []

for year in YEARS:
    n = pypsa.Network(NETWORK_DIR / f"solved_{year}.nc")
    ts = n.loads_t.p.sum(axis=1)
    snap = ts.idxmax()

    print(f"\n[System Peak] Year {year} | {snap} | Load: {ts.loc[snap]:.1f} MW")

    gen_peak = n.generators_t.p.loc[snap].groupby(n.generators.carrier).sum()
    batt_dis = n.storage_units_t.p_dispatch.loc[snap].sum() if not n.storage_units.empty else 0.0
    batt_chg = n.storage_units_t.p_store.loc[snap].sum()    if not n.storage_units.empty else 0.0
    hydro_mw, oxbow_mw = get_hydro_oxbow(n, snap=snap)

    records.append({
        "year":              year,
        "load":              float(ts.loc[snap]),
        "battery_charge":    float(batt_chg),
        "solar":             float(gen_peak.get("solar",  0.0)),
        "wind":              float(gen_peak.get("wind",   0.0)),
        "hydro":             hydro_mw,
        "oxbow":             oxbow_mw,
        "battery_discharge": float(batt_dis),
        "imports":           float(gen_peak.get("imports", 0.0)),
        "unmet":             float(gen_peak.get("load_shedding", 0.0)),
    })

pk = pd.DataFrame(records).set_index("year").fillna(0.0)
labels = pk.index.astype(str)
x = np.arange(len(labels))

fig, ax = plt.subplots(figsize=(15, 7))

demand_x = x - bar_w / 2
supply_x = x + bar_w / 2

demand_bottom = np.zeros(len(x))

c_load = ax.bar(demand_x, pk["load"], bar_w, bottom=demand_bottom, label="Peak load", color=COLORS["load"])
demand_bottom += pk["load"].values

c_bchg = ax.bar(demand_x, pk["battery_charge"], bar_w, bottom=demand_bottom, label="Battery charging", color=COLORS["battery_charge"], alpha=0.7)
demand_bottom += pk["battery_charge"].values

c_unmet = ax.bar(demand_x, pk["unmet"], bar_w, bottom=demand_bottom, label="Unmet demand", color=COLORS["unmet"])

supply_bottom = np.zeros(len(x))
supply_containers = []

for c in SUPPLY_STACK:
    bars = ax.bar(supply_x, pk[c], bar_w, bottom=supply_bottom, label=SUPPLY_LABELS[c], color=COLORS[c])
    supply_containers.append(bars)
    supply_bottom += pk[c].values

add_center_labels(ax, [c_load, c_unmet] + supply_containers)
add_top_of_segment_labels(ax, c_bchg, color="dimgray")

max_y = max(
    (pk["load"] + pk["battery_charge"] + pk["unmet"]).max(),
    pk[SUPPLY_STACK].sum(axis=1).max()
)
ax.set_ylim(0, max_y * 1.15)
ax.set_xticks(x)
ax.set_xticklabels(labels)
ax.set_ylabel("Power (MW)")
ax.legend(loc="center left", bbox_to_anchor=(1.02, 0.5))
ax.grid(axis="y", alpha=0.25)
plt.tight_layout()
plt.savefig(OUT_DIR / "m300_peak_capacity_balance_2bars.png", dpi=300)
plt.close()
print("Saved: m300_peak_capacity_balance_2bars.png")


# ============================================================
# PART C — EVENING PEAK CAPACITY BALANCE (18:00–21:00)
# ============================================================
print("\n" + "="*60)
print("SECTION 3: Evening Peak Capacity Balance (18:00–21:00)")
print("="*60)

records = []

for year in YEARS:
    n = pypsa.Network(NETWORK_DIR / f"solved_{year}.nc")
    ts = n.loads_t.p.sum(axis=1)

    evening_ts = ts[(ts.index.hour >= 18) & (ts.index.hour <= 21)]
    if evening_ts.empty:
        print(f"  {year}: no evening snapshots — skipping")
        continue

    esnap = evening_ts.idxmax()
    print(f"\n[Evening Peak] Year {year} | {esnap} | Load: {ts.loc[esnap]:.1f} MW")

    gen_ev   = n.generators_t.p.loc[esnap].groupby(n.generators.carrier).sum()
    batt_dis = n.storage_units_t.p_dispatch.loc[esnap].sum() if not n.storage_units.empty else 0.0
    batt_chg = n.storage_units_t.p_store.loc[esnap].sum()    if not n.storage_units.empty else 0.0
    hydro_mw, oxbow_mw = get_hydro_oxbow(n, snap=esnap)

    records.append({
        "year":              year,
        "load":              float(ts.loc[esnap]),
        "battery_charge":    float(batt_chg),
        "solar":             float(gen_ev.get("solar",  0.0)),
        "wind":              float(gen_ev.get("wind",   0.0)),
        "hydro":             hydro_mw,
        "oxbow":             oxbow_mw,
        "battery_discharge": float(batt_dis),
        "imports":           float(gen_ev.get("imports", 0.0)),
        "unmet":             float(gen_ev.get("load_shedding", 0.0)),
    })

ev = pd.DataFrame(records).set_index("year").fillna(0.0)
labels = ev.index.astype(str)
x = np.arange(len(labels))

fig, ax = plt.subplots(figsize=(14, 6))

demand_x = x - bar_w / 2
supply_x = x + bar_w / 2

demand_bottom = np.zeros(len(x))

c_load = ax.bar(demand_x, ev["load"], bar_w, bottom=demand_bottom, label="Evening load", color=COLORS["load"])
demand_bottom += ev["load"].values

c_bchg = ax.bar(demand_x, ev["battery_charge"], bar_w, bottom=demand_bottom, label="Battery charging", color=COLORS["battery_charge"], alpha=0.7)
demand_bottom += ev["battery_charge"].values

c_unmet = ax.bar(demand_x, ev["unmet"], bar_w, bottom=demand_bottom, label="Unmet demand", color=COLORS["unmet"])

supply_bottom = np.zeros(len(x))
supply_containers = []

for c in SUPPLY_STACK:
    bars = ax.bar(supply_x, ev[c], bar_w, bottom=supply_bottom, label=SUPPLY_LABELS[c], color=COLORS[c])
    supply_containers.append(bars)
    supply_bottom += ev[c].values

add_center_labels(ax, [c_load, c_unmet] + supply_containers)
add_top_of_segment_labels(ax, c_bchg, color="dimgray")

ax.set_ylim(0, 400)
ax.set_yticks(np.arange(0, 401, 50))
ax.set_xticks(x)
ax.set_xticklabels(labels)
ax.set_ylabel("Power (MW)")
ax.legend(loc="center left", bbox_to_anchor=(1.02, 0.5))
ax.grid(axis="y", alpha=0.25)
plt.tight_layout()
plt.savefig(OUT_DIR / "evening_peak_balance.png", dpi=300)
plt.close()
print("Saved: evening_peak_balance.png")

print("\n" + "="*60)
print("All Option A plots generated successfully.")
print("="*60)