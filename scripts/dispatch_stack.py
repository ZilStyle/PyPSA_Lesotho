import pypsa
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from pathlib import Path
import numpy as np

# ---------------------------------------
# SETTINGS
# ---------------------------------------
YEARS   = [2025, 2026, 2027, 2028, 2029, 2030, 2035, 2040, 2045, 2050]
DEMANDS = ["BAU", "M300"]   # demand scenarios to plot
OPTION  = "B"               # planned generation expansion
DISPATCH_YEAR = 2050

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
    "hydro":              "#440dfa",   # Muela baseload, dark blue
    "oxbow":              "#00bfff",   # Oxbow peaking, sky blue
    "battery_discharge":  "#000000",
    "imports":            "#069832",
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


# ---------------------------------------
# HELPER: split hydro vs oxbow (hourly series, not scalar)
# ---------------------------------------
def get_hydro_oxbow_ts(n):
    """
    Return (hydro_ts, oxbow_ts) as full-year hourly Series (MW),
    same split logic as the annual/peak-snapshot plots.
    """
    oxbow_gens = n.generators.index[
        n.generators.index.str.contains("Oxbow", case=False)
    ]
    hydro_gens = n.generators.index[
        (n.generators.carrier == "hydro") &
        ~n.generators.index.str.contains("Oxbow", case=False)
    ]

    hydro_ts = n.generators_t.p[hydro_gens].sum(axis=1) if len(hydro_gens) > 0 else pd.Series(0.0, index=n.snapshots)
    oxbow_ts = n.generators_t.p[oxbow_gens].sum(axis=1) if len(oxbow_gens) > 0 else pd.Series(0.0, index=n.snapshots)

    return hydro_ts, oxbow_ts


# ================================================================
# SECTION 4: REPRESENTATIVE WEEKLY DISPATCH STACK (PEAK JULY WEEK)
# ================================================================
print("\n" + "="*60)
print("SECTION 4: Weekly Hourly Dispatch Stack, Peak July Week")
print("="*60)

for demand in DEMANDS:

    NETWORK_DIR = Path(f"networks/{demand}/{OPTION}")
    OUT_DIR     = Path(f"results/{demand}/{OPTION}/plots")
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    nc = NETWORK_DIR / f"solved_{DISPATCH_YEAR}.nc"
    if not nc.exists():
        print(f"{demand}: {nc} not found, skipped")
        continue
    print(f"\n--- {demand} | Option {OPTION} | {nc} ---")
    n = pypsa.Network(nc)

    total_load_ts = n.loads_t.p.sum(axis=1)

    # Restrict to July, find the hour of peak system load within that month,
    # then take the 7-day window (168 hours) centred on the day containing that peak.
    july_load = total_load_ts[total_load_ts.index.month == 7]
    if july_load.empty:
        raise ValueError(f"No July snapshots found for {DISPATCH_YEAR}, check snapshot resolution/timezone.")

    peak_ts = july_load.idxmax()
    peak_day = peak_ts.normalize()

    # Window: the Monday on/before the peak day, through the following Sunday 23:00
    week_start = peak_day - pd.Timedelta(days=peak_day.dayofweek)
    week_end = week_start + pd.Timedelta(days=7) - pd.Timedelta(hours=1)

    # Clip to what's actually in the snapshot index (in case the week runs past year-end)
    mask = (n.snapshots >= week_start) & (n.snapshots <= week_end)
    week_snaps = n.snapshots[mask]

    print(f"Peak July load: {july_load.max():.1f} MW at {peak_ts}")
    print(f"Plotting week: {week_snaps[0]} to {week_snaps[-1]} ({len(week_snaps)} hours)")

    # ---------------------------------------
    # BUILD HOURLY SUPPLY/DEMAND DATAFRAME FOR THE WEEK
    # ---------------------------------------
    gen_by_carrier = n.generators_t.p.loc[week_snaps].T.groupby(n.generators.carrier).sum().T

    hydro_ts, oxbow_ts = get_hydro_oxbow_ts(n)
    hydro_ts = hydro_ts.loc[week_snaps]
    oxbow_ts = oxbow_ts.loc[week_snaps]

    batt_dis_ts = n.storage_units_t.p_dispatch.loc[week_snaps].sum(axis=1) if not n.storage_units.empty else pd.Series(0.0, index=week_snaps)
    batt_chg_ts = n.storage_units_t.p_store.loc[week_snaps].sum(axis=1) if not n.storage_units.empty else pd.Series(0.0, index=week_snaps)

    export_gens = n.generators.index[n.generators.carrier == "export"]
    export_ts = -n.generators_t.p.loc[week_snaps, export_gens].sum(axis=1) if len(export_gens) > 0 else pd.Series(0.0, index=week_snaps)

    week = pd.DataFrame({
        "load":              total_load_ts.loc[week_snaps],
        "battery_charge":    batt_chg_ts,
        "export":            export_ts,
        "solar":             gen_by_carrier.get("solar", pd.Series(0.0, index=week_snaps)),
        "wind":              gen_by_carrier.get("wind", pd.Series(0.0, index=week_snaps)),
        "hydro":             hydro_ts,
        "oxbow":             oxbow_ts,
        "battery_discharge": batt_dis_ts,
        "imports":           gen_by_carrier.get("imports", pd.Series(0.0, index=week_snaps)),
        "unmet":             gen_by_carrier.get("load_shedding", pd.Series(0.0, index=week_snaps)),
    }).fillna(0.0)

    # ---------------------------------------
    # PLOT: stacked supply area + load line
    # ---------------------------------------
    fig, ax = plt.subplots(figsize=(15, 7))

    supply_arrays = [week[c].values for c in SUPPLY_STACK]
    supply_colors = [COLORS[c] for c in SUPPLY_STACK]
    supply_labels = [SUPPLY_LABELS[c] for c in SUPPLY_STACK]

    ax.stackplot(week.index, *supply_arrays, colors=supply_colors, labels=supply_labels, alpha=0.95)

    # Battery charging drawn as a shaded negative-axis area (load being served + charging)
    if week["battery_charge"].abs().max() > 1e-6:
        ax.fill_between(
            week.index, 0, -week["battery_charge"].values,
            color=COLORS["battery_charge"], alpha=0.6, step=None,
            label="Battery charging"
        )

    # Exports drawn as a shaded negative-axis area beneath battery charging
    if week["export"].abs().max() > 1e-6:
        bottom = -week["battery_charge"].values
        ax.fill_between(
            week.index, bottom, bottom - week["export"].values,
            color=COLORS["export"], alpha=0.6, step=None,
            label="Exports/Excess"
        )

    # Load line on top
    ax.plot(week.index, week["load"].values, color=COLORS["load"], linewidth=2.0, label="Load")

    # Unmet demand, if any, as a hatched marker line
    if week["unmet"].abs().max() > 1e-6:
        ax.plot(week.index, week["unmet"].values, color=COLORS["unmet"], linewidth=1.5,
                linestyle="--", label="Unmet demand")

    ax.set_ylabel("Power (MW)")
    ax.set_title(
        f"Representative Weekly Dispatch: Peak July Week, {demand} demand, Option {OPTION}, {DISPATCH_YEAR}\n"
        f"({week_snaps[0]:%d %b} to {week_snaps[-1]:%d %b}, system peak {july_load.max():.0f} MW on {peak_ts:%d %b %H:%M})",
        fontsize=12, fontweight="bold"
    )

    ax.xaxis.set_major_locator(mdates.DayLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%a %d"))
    ax.xaxis.set_minor_locator(mdates.HourLocator(byhour=[6, 12, 18]))
    fig.autofmt_xdate()

    ax.axhline(0, color="black", linewidth=0.8)
    ax.legend(loc="center left", bbox_to_anchor=(1.01, 0.5))
    ax.grid(axis="y", alpha=0.25)

    plt.tight_layout()
    out_path = OUT_DIR / f"dispatch_stack_week_july_{demand}_{DISPATCH_YEAR}.png"
    plt.savefig(out_path, dpi=300, bbox_inches="tight")
    plt.close()

    print(f"\nSaved: {out_path}")