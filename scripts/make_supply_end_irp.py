import pandas as pd
from pathlib import Path

# =========================================================
# PATHS
# =========================================================
# CHANGED: read from the folder the BAU projection script writes to
DEMAND_DIR = Path(r"C:\Users\USER\pypsa-lesotho\data\IRP\M300_C\load_M300_C")
OUT_DIR    = Path(r"C:\Users\USER\pypsa-lesotho\data\IRP\M300_C\load_M300_C_supply_end")
OUT_DIR.mkdir(parents=True, exist_ok=True)
PLOT_DIR   = OUT_DIR / "plots"

# Units for the plots. The _p columns are assumed to be hourly MW, so the
# annual sum is MWh and dividing by 1000 gives GWh. Change these if not.
POWER_UNIT = "MW"
ENERGY_UNIT = "GWh"
ENERGY_DIVISOR = 1000

# =========================================================
# INPUT: PEAKS (given by you)
# =========================================================
peaks = pd.DataFrame(
    {
        "year": [2022, 2023, 2024],
        "peak_demand_mw": [169.91, 181.45, 184.87],
        "peak_supply_mw": [222.12, 209.62, 244.86],
    }
).set_index("year")

# uplift factors per year
peaks["k"] = peaks["peak_supply_mw"] / peaks["peak_demand_mw"]

k_avg = peaks["k"].mean()

print("Per-year uplift factors k = peak_supply / peak_demand")
print(peaks[["k"]])
print(f"\nAverage uplift factor k_avg = {k_avg:.4f}")

# =========================================================
# YEARS TO SCALE (you can include any years here)
# =========================================================
YEARS = [2024, 2025, 2026, 2027, 2028, 2029, 2030, 2035, 2040, 2045, 2050]

# =========================================================
# HELPERS
# =========================================================
def read_load_csv(path: Path) -> pd.DataFrame:
    # CHANGED: the BAU script writes CSV, not xlsx. parse_dates keeps "Date"
    # as real timestamps so the Excel output has proper datetime cells.
    df = pd.read_csv(path, parse_dates=["Date"])
    df.columns = (
        df.columns.astype(str)
        .str.strip()
        .str.replace(r"\s+", " ", regex=True)
    )
    return df

def get_pq_cols(df: pd.DataFrame):
    p_cols = [c for c in df.columns if c.lower().endswith("_p")]
    q_cols = [c for c in df.columns if c.lower().endswith("_q")]
    if not p_cols:
        raise ValueError("No _p columns detected")
    return p_cols, q_cols

# =========================================================
# SCALE AND SAVE
# =========================================================
if not DEMAND_DIR.exists():
    raise FileNotFoundError(f"Input folder not found: {DEMAND_DIR}")

summary = []

for year in YEARS:
    in_file = DEMAND_DIR / f"load_timeseries_{year}.csv"   # CHANGED: .csv

    if not in_file.exists():
        print(f"{year}: missing input file, skipped  ({in_file})")
        continue

    df = read_load_csv(in_file)
    p_cols, q_cols = get_pq_cols(df)

    # Scale both P and Q by the average uplift factor
    df[p_cols] = df[p_cols] * k_avg
    if q_cols:
        df[q_cols] = df[q_cols] * k_avg

    out_file = OUT_DIR / f"load_timeseries_{year}_supply_end.xlsx"
    df.to_excel(out_file, sheet_name="Sheet1", index=False)

    print(f"{year}: saved -> {out_file.name}")

    p_total = df[p_cols].sum(axis=1)
    summary.append({
        "year": year,
        "energy_sum_p": p_total.sum(),
        "coincident_peak": p_total.max(),
        "load_factor": p_total.mean() / p_total.max(),
    })

if not summary:
    raise SystemExit("No input files were found, nothing to summarise or plot.")

summary_df = pd.DataFrame(summary).set_index("year")
summary_df.to_csv(OUT_DIR / "summary_supply_end.csv")

print("\nSupply-end system summary (same units as the input _p columns):")
print(summary_df.round(4).to_string())

# =========================================================
# PLOTS (annual energy and peak demand per planning year, supply end)
# =========================================================
import matplotlib
matplotlib.use("Agg")              # write files only, no window (safe under Snakemake)
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

PLOT_DIR.mkdir(parents=True, exist_ok=True)

INK, MUTED, GRID, SERIES = "#0b0b0b", "#52514e", "#e6e5e0", "#2a78d6"


def plot_planning_years(values, title, ylabel, filename, label_years):
    """One series on a true time axis, so the 5-year steps after 2030 are not squeezed."""
    years = list(values.index)
    fig, ax = plt.subplots(figsize=(9, 4.8), dpi=200)

    ax.plot(years, values.values, color=SERIES, linewidth=2, solid_capstyle="round",
            marker="o", markersize=7, markeredgecolor="white", markeredgewidth=1.5, zorder=3)

    # a few direct labels; the rest are read off the axis or summary_supply_end.csv
    for y in label_years:
        if y in values.index:
            ax.annotate(f"{values[y]:,.0f}", (y, values[y]), xytext=(0, 9),
                        textcoords="offset points", ha="center", fontsize=9, color=INK)

    # tick every planning year, but only label ticks at least 2 years apart
    ax.set_xticks(years)
    labels, last = [], None
    for y in years:
        show = last is None or y - last >= 2
        labels.append(str(y) if show else "")
        last = y if show else last
    ax.set_xticklabels(labels)

    ax.set_ylim(0, values.max() * 1.15)
    ax.set_xlim(years[0] - 1, years[-1] + 1)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:,.0f}"))
    ax.set_ylabel(ylabel, color=MUTED, fontsize=10)
    ax.set_title(title, loc="left", color=INK, fontsize=12, fontweight="bold", pad=24)
    ax.text(0, 1.03, f"M300 at supply end: demand x uplift factor {k_avg:.4f}",
            transform=ax.transAxes, color=MUTED, fontsize=9.5)

    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(colors=MUTED, labelsize=9, length=3, color=GRID)
    ax.tick_params(axis="y", length=0)

    fig.tight_layout()
    path = PLOT_DIR / filename
    fig.savefig(path, facecolor="white")
    plt.close(fig)
    print(f"Saved {path}")


label_years = [summary_df.index[0], 2030, 2040, summary_df.index[-1]]

plot_planning_years(
    summary_df["energy_sum_p"] / ENERGY_DIVISOR,
    "Annual electricity demand at supply end by planning year",
    f"Annual energy ({ENERGY_UNIT})",
    "annual_energy_supply_end.png",
    label_years,
)

plot_planning_years(
    summary_df["coincident_peak"],
    "System coincident peak demand at supply end by planning year",
    f"Peak demand ({POWER_UNIT})",
    "peak_demand_supply_end.png",
    label_years,
)

print(f"\nDone. Supply-end demand files written to:\n{OUT_DIR}")