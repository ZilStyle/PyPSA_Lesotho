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

OUT_DIR = Path("results/A/option_A")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ============================================================
# PART A: ANNUAL ENERGY CONTRIBUTION (GWh)
# ============================================================

records = []

for year in YEARS:
    n = pypsa.Network(NETWORK_DIR / f"solved_{year}.nc")

    # -------------------------------
    # LOAD
    # -------------------------------
    load_gwh = n.loads_t.p.sum().sum() / 1000

    # -------------------------------
    # GENERATORS
    # -------------------------------
    gen_gwh = (
        n.generators_t.p
        .groupby(n.generators.carrier, axis=1)
        .sum()
        .sum()
        / 1000
    )

    # -------------------------------
    # STORAGE (SEPARATE!)
    # -------------------------------
    if not n.storage_units.empty:
        batt_discharge_gwh = (
            n.storage_units_t.p_dispatch.sum().sum() / 1000
        )
        batt_charge_gwh = (
            n.storage_units_t.p_store.sum().sum() / 1000
        )
    else:
        batt_discharge_gwh = 0.0
        batt_charge_gwh = 0.0

    row = {
        "year": year,
        "load": load_gwh,
        "battery_discharge": batt_discharge_gwh,
        "battery_charge": batt_charge_gwh,
    }

    for carrier, val in gen_gwh.items():
        row[carrier] = val

    records.append(row)

df = pd.DataFrame(records).set_index("year").fillna(0.0)

# ---------------------------------------
# SERIES
# ---------------------------------------
labels = df.index.astype(str)
x = np.arange(len(labels))
width = 0.13

load_gwh     = df["load"].values
solar_gwh    = df.get("solar", 0).values
wind_gwh     = df.get("wind", 0).values
hydro_gwh    = df.get("hydro", 0).values
imports_gwh  = df.get("imports", 0).values
unmet_gwh    = df.get("load_shedding", 0).values

batt_dis_gwh = df["battery_discharge"].values
batt_chg_gwh = -df["battery_charge"].values   # NEGATIVE ON PURPOSE

# ---------------------------------------
# PLOT
# ---------------------------------------
plt.figure(figsize=(18, 8))

bars_load   = plt.bar(x - 3.5*width, load_gwh,     width, label="Load",      color="#4b4b4b")
bars_solar  = plt.bar(x - 2.5*width, solar_gwh,    width, label="Solar",     color="#fae70f")
bars_wind   = plt.bar(x - 1.5*width, wind_gwh,     width, label="Wind",      color="#17becf")
bars_hydro  = plt.bar(x - 0.5*width, hydro_gwh,    width, label="Hydro",     color="#440dfa")

bars_bdis   = plt.bar(x + 0.5*width, batt_dis_gwh, width, label="Battery discharge", color="black")
bars_bchg   = plt.bar(x + 1.5*width, batt_chg_gwh, width, label="Battery charge",    color="black", alpha=0.4)

bars_import = plt.bar(x + 2.5*width, imports_gwh,  width, label="Imports",   color="#069832")
bars_unmet  = plt.bar(x + 3.5*width, unmet_gwh,    width, label="Unmet",     color="#e50910")

plt.xticks(x, labels, fontsize=12)
plt.ylabel("Annual Energy (GWh)", fontsize=13)
plt.title("Annual Energy Balance by Technology (SQ – demand)", fontsize=16)
plt.legend()
plt.grid(axis="y", alpha=0.25)

# ---------------------------------------
# LABEL BARS
# ---------------------------------------
def label_bars(bars):
    for bar in bars:
        h = bar.get_height()
        if abs(h) > 0:
            plt.text(
                bar.get_x() + bar.get_width() / 2,
                h,
                f"{h:.1f}",
                ha="center",
                va="bottom" if h > 0 else "top",
                fontsize=9
            )

for b in [bars_load, bars_solar, bars_wind, bars_hydro, bars_bdis, bars_bchg, bars_import, bars_unmet]:
    label_bars(b)

plt.tight_layout()
plt.savefig(OUT_DIR / "SQ_demand.png", dpi=300)
plt.close()

print("Saved annual energy balance plot")

# ============================================================
# PART B: PEAK CAPACITY BALANCE (MW)
# ============================================================

records = []

for year in YEARS:
    n = pypsa.Network(NETWORK_DIR / f"solved_{year}.nc")

    load_ts = n.loads_t.p.sum(axis=1)
    peak_snap = load_ts.idxmax()
    peak_load = load_ts.loc[peak_snap]

    gen_peak = (
        n.generators_t.p.loc[peak_snap]
        .groupby(n.generators.carrier)
        .sum()
    )

    if not n.storage_units.empty:
        batt_dis_mw = n.storage_units_t.p_dispatch.loc[peak_snap].sum()
        batt_chg_mw = -n.storage_units_t.p_store.loc[peak_snap].sum()
    else:
        batt_dis_mw = 0.0
        batt_chg_mw = 0.0

    row = {
        "year": year,
        "peak_load": peak_load,
        "battery_discharge": batt_dis_mw,
        "battery_charge": batt_chg_mw,
    }

    for carrier, val in gen_peak.items():
        row[carrier] = val

    records.append(row)

df = pd.DataFrame(records).set_index("year").fillna(0.0)

# ---------------------------------------
# SERIES
# ---------------------------------------
load_mw     = df["peak_load"].values
solar_mw    = df.get("solar", 0).values
wind_mw     = df.get("wind", 0).values
hydro_mw    = df.get("hydro", 0).values
imports_mw  = df.get("imports", 0).values
unmet_mw    = df.get("load_shedding", 0).values

batt_dis_mw = df["battery_discharge"].values
batt_chg_mw = df["battery_charge"].values

# ---------------------------------------
# PLOT
# ---------------------------------------
plt.figure(figsize=(18, 8))

bars_load   = plt.bar(x - 3.5*width, load_mw,     width, label="Peak Load", color="#4b4b4b")
bars_solar  = plt.bar(x - 2.5*width, solar_mw,    width, label="Solar",     color="#fae70f")
bars_wind   = plt.bar(x - 1.5*width, wind_mw,     width, label="Wind",      color="#17becf")
bars_hydro  = plt.bar(x - 0.5*width, hydro_mw,    width, label="Hydro",     color="#440dfa")

bars_bdis   = plt.bar(x + 0.5*width, batt_dis_mw, width, label="Battery discharge", color="black")
bars_bchg   = plt.bar(x + 1.5*width, batt_chg_mw, width, label="Battery charge",    color="black", alpha=0.4)

bars_import = plt.bar(x + 2.5*width, imports_mw,  width, label="Imports",   color="#069832")
bars_unmet  = plt.bar(x + 3.5*width, unmet_mw,    width, label="Unmet",     color="#e50910")

plt.xticks(x, labels, fontsize=12)
plt.ylabel("Power (MW)", fontsize=13)
plt.title("Peak Capacity Balance at System Peak (SQ – demand)", fontsize=16)
plt.legend()
plt.grid(axis="y", alpha=0.25)

# ---------------------------------------
# LABEL BARS
# ---------------------------------------
def label_bars(bars):
    for bar in bars:
        h = bar.get_height()
        if abs(h) > 0:
            plt.text(
                bar.get_x() + bar.get_width() / 2,
                h,
                f"{h:.1f}",
                ha="center",
                va="bottom" if h > 0 else "top",
                fontsize=9
            )

for b in [bars_load, bars_solar, bars_wind, bars_hydro, bars_bdis, bars_bchg, bars_import, bars_unmet]:
    label_bars(b)


plt.tight_layout()
plt.savefig(OUT_DIR / "m300_peak_capacity_balance.png", dpi=300)
plt.close()

print("Saved peak capacity balance plot")

def add_center_labels(ax, containers, fmt="{:.0f}", min_val=1e-6, fontsize=8):
    """
    Add centered white labels inside each stacked bar segment.
    Only labels segments with height > min_val.
    """
    for cont in containers:
        for rect in cont.patches:
            h = rect.get_height()
            if h > min_val:
                x = rect.get_x() + rect.get_width() / 2
                y = rect.get_y() + h / 2
                ax.text(
                    x, y,
                    fmt.format(h),
                    ha="center", va="center",
                    color="white",
                    fontsize=fontsize,
                    clip_on=True
                )


def add_total_labels(ax, x_positions, totals, fmt="{:.0f}", min_total=1e-6, fontsize=9):
    """
    Add total labels above each bar (optional, useful for quick check).
    """
    for xp, tot in zip(x_positions, totals):
        if tot > min_total:
            ax.text(
                xp, tot,
                fmt.format(tot),
                ha="center", va="bottom",
                color="black",
                fontsize=fontsize
            )

# ============================================================
# PART C (FIXED): TWO-BAR STACKED ANNUAL ENERGY BALANCE (GWh)
# ============================================================

fig, ax = plt.subplots(figsize=(14, 6))

x = np.arange(len(df.index))
bar_width = 0.35

# -------------------------------
# DEMAND BAR (LEFT)
# -------------------------------
demand_x = x - bar_width/2
demand_bottom = np.zeros(len(x))

c_load = ax.bar(
    demand_x, load_gwh, bar_width,
    bottom=demand_bottom,
    label="Load",
    color="#4b4b4b"
)
demand_bottom += load_gwh

c_bchg = ax.bar(
    demand_x, batt_chg_gwh, bar_width,
    bottom=demand_bottom,
    label="Battery charging",
    color="black",
    alpha=0.4
)
demand_bottom += batt_chg_gwh



# -------------------------------
# SUPPLY BAR (RIGHT)
# -------------------------------
supply_x = x + bar_width/2
supply_bottom = np.zeros(len(x))

c_solar = ax.bar(
    supply_x, solar_gwh, bar_width,
    bottom=supply_bottom,
    label="Solar",
    color="#fae70f"
)
supply_bottom += solar_gwh

c_wind = ax.bar(
    supply_x, wind_gwh, bar_width,
    bottom=supply_bottom,
    label="Wind",
    color="#17becf"
)
supply_bottom += wind_gwh

c_hydro = ax.bar(
    supply_x, hydro_gwh, bar_width,
    bottom=supply_bottom,
    label="Hydro",
    color="#440dfa"
)
supply_bottom += hydro_gwh

c_bdis = ax.bar(
    supply_x, batt_dis_gwh, bar_width,
    bottom=supply_bottom,
    label="Battery discharge",
    color="black"
)
supply_bottom += batt_dis_gwh

c_imports = ax.bar(
    supply_x, imports_gwh, bar_width,
    bottom=supply_bottom,
    label="Imports",
    color="#069832"
)

c_unmet = ax.bar(
    demand_x, unmet_gwh, bar_width,
    bottom=demand_bottom,
    label="Unmet demand",
    color="#e50910"
)

# -------------------------------
# CENTERED WHITE LABELS
# -------------------------------

add_center_labels(
    ax,
    containers=[c_load, c_bchg, c_solar, c_wind, c_hydro, c_bdis, c_imports,c_unmet],
    fmt="{:.0f}",
    min_val=0.001,
    fontsize=8
)


# Totals (sanity check)
demand_totals = load_gwh - batt_chg_gwh + unmet_gwh
supply_totals = solar_gwh + wind_gwh + hydro_gwh + batt_dis_gwh + imports_gwh

add_total_labels(ax, demand_x, demand_totals, fmt="{:.0f}")
add_total_labels(ax, supply_x, supply_totals, fmt="{:.0f}")

# -------------------------------
# FORMATTING
# -------------------------------
ax.set_xticks(x)
ax.set_xticklabels(labels, fontsize=11)
ax.set_ylabel("Annual Energy (GWh)")
ax.set_title("Annual Energy Balance: Demand vs Supply (SQ – demand)")
ax.grid(axis="y", alpha=0.25)

ax.legend(loc="center left", bbox_to_anchor=(1.02, 0.5))

plt.tight_layout()
plt.savefig(OUT_DIR / "SQ_annual_energy_balance_2bars_FIXED.png", dpi=300)
plt.close()



# ============================================================
# PART D: TWO-BAR STACKED PEAK CAPACITY BALANCE (MW) + LABELS
# ============================================================

fig, ax = plt.subplots(figsize=(14, 6))

x = np.arange(len(df.index))
bar_width = 0.35

# -------------------------------
# DEMAND BAR (LEFT)
# -------------------------------
demand_x = x - bar_width/2
demand_bottom = np.zeros(len(x))

c_load = ax.bar(
    demand_x, load_mw, bar_width,
    bottom=demand_bottom,
    label="Peak load",
    color="#4b4b4b"
)
demand_bottom += load_mw

c_bchg = ax.bar(
    demand_x, batt_chg_mw, bar_width,
    bottom=demand_bottom,
    label="Battery charge",
    color="black",
    alpha=0.4
)
demand_bottom += batt_chg_mw



# -------------------------------
# SUPPLY BAR (RIGHT)
# -------------------------------
supply_x = x + bar_width/2
supply_bottom = np.zeros(len(x))

c_solar = ax.bar(
    supply_x, solar_mw, bar_width,
    bottom=supply_bottom,
    label="Solar",
    color="#fae70f"
)
supply_bottom += solar_mw

c_wind = ax.bar(
    supply_x, wind_mw, bar_width,
    bottom=supply_bottom,
    label="Wind",
    color="#17becf"
)
supply_bottom += wind_mw

c_hydro = ax.bar(
    supply_x, hydro_mw, bar_width,
    bottom=supply_bottom,
    label="Hydro",
    color="#440dfa"
)
supply_bottom += hydro_mw

c_bdis = ax.bar(
    supply_x, batt_dis_mw, bar_width,
    bottom=supply_bottom,
    label="Battery discharge",
    color="black"
)
supply_bottom += batt_dis_mw

c_imports = ax.bar(
    supply_x, imports_mw, bar_width,
    bottom=supply_bottom,
    label="Imports",
    color="#069832"
)

c_unmet = ax.bar(
    demand_x, unmet_mw, bar_width,
    bottom=demand_bottom,
    label="Unmet demand",
    color="#e50910"
)

# -------------------------------
# LABELS (CENTER, WHITE, ONLY > 0)
# -------------------------------
add_center_labels(
    ax,
    containers=[c_load,c_bchg, c_unmet, c_solar, c_wind, c_hydro, c_bdis, c_imports],
    fmt="{:.0f}",
    min_val=0.001,
    fontsize=8
)

# Optional totals above each full bar
demand_totals = load_mw - batt_chg_mw + unmet_mw
supply_totals = solar_mw + wind_mw + hydro_mw + batt_dis_mw + imports_mw
add_total_labels(ax, demand_x, demand_totals, fmt="{:.0f}", fontsize=9)
add_total_labels(ax, supply_x, supply_totals, fmt="{:.0f}", fontsize=9)

# -------------------------------
# FORMATTING
# -------------------------------
ax.set_xticks(x)
ax.set_xticklabels(labels, fontsize=11)
ax.set_ylabel("Power (MW)")
ax.set_title("Peak Capacity Balance: Demand vs Supply (SQ – demand)")
ax.grid(axis="y", alpha=0.25)

ax.legend(loc="center left", bbox_to_anchor=(1.02, 0.5))

plt.tight_layout()
plt.savefig(OUT_DIR / "SQ_peak_capacity_balance_2bars.png", dpi=300)
plt.close()

print("Saved two-bar peak capacity balance plot (with labels)")



print("\n================ ENERGY BALANCE CHECK =================")

TOL = 1e-3  # GWh tolerance

for year in YEARS:
    n = pypsa.Network(NETWORK_DIR / f"solved_{year}.nc")

    # -------------------------------
    # SUPPLY
    # -------------------------------
    gen_supply_gwh = (
        n.generators_t.p.sum().sum() / 1000
    )

    if not n.storage_units.empty:
        batt_discharge_gwh = (
            n.storage_units_t.p_dispatch.sum().sum() / 1000
        )
    else:
        batt_discharge_gwh = 0.0

    total_supply = gen_supply_gwh + batt_discharge_gwh

    # -------------------------------
    # DEMAND
    # -------------------------------
    load_gwh = n.loads_t.p.sum().sum() / 1000

    if not n.storage_units.empty:
        batt_charge_gwh = (
            n.storage_units_t.p_store.sum().sum() / 1000
        )
    else:
        batt_charge_gwh = 0.0

    load_shedding_gwh = (
        n.generators_t.p.loc[:, n.generators.carrier == "load_shedding"]
        .sum().sum() / 1000
        if "load_shedding" in n.generators.carrier.values
        else 0.0
    )

    total_demand = load_gwh + batt_charge_gwh + load_shedding_gwh

    # -------------------------------
    # BALANCE
    # -------------------------------
    imbalance = total_supply - total_demand
    rel_error = imbalance / load_gwh * 100 if load_gwh > 0 else 0.0

    status = "OK" if abs(imbalance) <= TOL else "WARNING"

    print(
        f"{year} | "
        f"Supply={total_supply:.2f} GWh | "
        f"Demand={total_demand:.2f} GWh | "
        f"Δ={imbalance:+.4f} GWh | "
        f"Error={rel_error:.4f}% | "
        f"{status}"
    )

    if abs(imbalance) > TOL:
        print(
            f"  ↳ Breakdown {year}: "
            f"Gen={gen_supply_gwh:.2f}, "
            f"Batt_dis={batt_discharge_gwh:.2f}, "
            f"Load={load_gwh:.2f}, "
            f"Batt_chg={batt_charge_gwh:.2f}, "
            f"LS={load_shedding_gwh:.2f}"
        )

print("=======================================================\n")
