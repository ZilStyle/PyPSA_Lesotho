import pandas as pd
import os
import calendar

# ===============================
# INPUTS
# ===============================
FILE = "data/load_timeseries_2022_2024.xlsx"
OUTPUT_DIR = "data/IRP/BAU/load_BAU"
os.makedirs(OUTPUT_DIR, exist_ok=True)

ANCHOR_YEAR = 2024                 # growth anchor AND hourly profile year
# IRP planning years. ANCHOR_YEAR itself is included (growth factor 1.0);
# growth still compounds every calendar year between the milestone years.
PLANNING_YEARS = [2024, 2025, 2026, 2027, 2028, 2029, 2030,
                  2031, 2032, 2033, 2034, 2035, 2036, 2037,
                  2038, 2039, 2040, 2041, 2042, 2043, 2044,
                  2045, 2046, 2047, 2048, 2049,2050]

# BAU: year-by-year growth of annual ENERGY. The rate under each year is the
# growth from the previous year to that year (2025: 2024 -> 2025). Rates
# compound from ANCHOR_YEAR; the resulting scale factor is applied to every
# substation's hourly P and Q.
GROWTH_BY_YEAR = {
    2025: 0.022, 2026: 0.028, 2027: 0.023, 2028: 0.024, 2029: 0.023, 2030: 0.018,
    2031: 0.022, 2032: 0.021, 2033: 0.021, 2034: 0.020, 2035: 0.015,
    2036: 0.020, 2037: 0.019, 2038: 0.019, 2039: 0.019, 2040: 0.014,
    2041: 0.019, 2042: 0.018, 2043: 0.018, 2044: 0.018, 2045: 0.012,
    2046: 0.018, 2047: 0.018, 2048: 0.018, 2049: 0.019, 2050: 0.014,
}


def energy_growth_factor(year):
    """Annual energy relative to ANCHOR_YEAR: product of (1 + g) for every year after the anchor."""
    f = 1.0
    for y in range(ANCHOR_YEAR + 1, year + 1):
        f *= 1 + GROWTH_BY_YEAR[y]          # KeyError here means a year is missing from the table
    return f


# Average rate over the horizon, used only in printouts and plot labels
AVG_GROWTH = energy_growth_factor(max(PLANNING_YEARS)) ** (1 / (max(PLANNING_YEARS) - ANCHOR_YEAR)) - 1

# Units for the plots. The _p columns are assumed to be hourly MW, so the
# annual sum is MWh and dividing by 1000 gives GWh. Change these if not.
POWER_UNIT = "MW"
ENERGY_UNIT = "GWh"
ENERGY_DIVISOR = 1000
PLOT_DIR = os.path.join(OUTPUT_DIR, "plots")

HIST_START_YEAR = 2022            # diagnostics only, not used in the projection
MIN_COVERAGE = 0.98                # warn if the anchor year has less data than this
MAX_GAP_HOURS = 6                  # interpolate gaps up to this length in the anchor year

# ===============================
# STEP 1: LOAD DATA
# ===============================
df = pd.read_excel(FILE, sheet_name="Sheet1")

df["Date"] = pd.to_datetime(df["Date"], errors="coerce").dt.round("h")
df = df.dropna(subset=["Date"])
# rounding can create duplicate timestamps; collapse them
df = df.groupby("Date", as_index=False).mean(numeric_only=True)
df["year"] = df["Date"].dt.year

# ===============================
# STEP 2: IDENTIFY SUBSTATIONS
# ===============================
p_cols = [c for c in df.columns if c.endswith("_p")]
q_cols = [c for c in df.columns if c.endswith("_q")]

# strip only the suffix (replace("_p", "") also hits "_p" inside a name)
substations = [c[:-2] for c in p_cols]

print("Substations detected:")
print(substations)

# ===============================
# STEP 3: HISTORICAL DIAGNOSTICS (not used in the projection)
# ===============================
annual_df = df.groupby("year")[p_cols].sum()
annual_df.columns = substations

print("\nAnnual energy table (raw sums):")
print(annual_df)

e_sys = annual_df.sum(axis=1)
if HIST_START_YEAR in e_sys.index and e_sys[HIST_START_YEAR] > 0:
    n_hist = ANCHOR_YEAR - HIST_START_YEAR
    g_hist = (e_sys[ANCHOR_YEAR] / e_sys[HIST_START_YEAR]) ** (1 / n_hist) - 1
    print(f"\nHistorical system CAGR {HIST_START_YEAR} to {ANCHOR_YEAR}: {g_hist:.2%} "
          f"(for reference only; projection uses year-by-year rates, average {AVG_GROWTH:.2%})")

# ===============================
# STEP 4: BUILD THE HOURLY PROFILE (anchor year)
# ===============================
assert calendar.isleap(ANCHOR_YEAR), "ANCHOR_YEAR must be a leap year so every planning year can be built from it"

profile = df[df["year"] == ANCHOR_YEAR].drop(columns=["year"]).set_index("Date")

# force a complete hourly index so the profile always matches the target year length
full_idx = pd.date_range(f"{ANCHOR_YEAR}-01-01 00:00", f"{ANCHOR_YEAR}-12-31 23:00", freq="h")

coverage = profile[p_cols].count() / len(full_idx)
low = coverage[coverage < MIN_COVERAGE]
if len(low):
    print(f"\nWARNING: {ANCHOR_YEAR} coverage below {MIN_COVERAGE:.0%} for:")
    print(low.round(3))

n_missing = len(full_idx.difference(profile.index))
profile = profile.reindex(full_idx).interpolate(limit=MAX_GAP_HOURS, limit_area="inside")
n_unfilled = int(profile[p_cols].isna().sum().sum())
profile = profile.fillna(0.0)
print(f"\nProfile year {ANCHOR_YEAR}: {n_missing} missing timestamps, "
      f"{n_unfilled} substation-hours left at zero (gaps longer than {MAX_GAP_HOURS} h)")

# Anchor-year annual energy per substation (full 366-day 2024)
e_anchor = profile[p_cols].sum()

# ===============================
# STEP 5: GENERATE FUTURE YEARS
# ===============================
summary = []

for year in PLANNING_YEARS:
    assert year >= ANCHOR_YEAR, "planning years must not precede ANCHOR_YEAR"

    growth_factor = energy_growth_factor(year)

    out = profile.copy()
    if not calendar.isleap(year):
        # drop 29 Feb (keeps seasons aligned, unlike truncating the last day)
        out = out[~((out.index.month == 2) & (out.index.day == 29))]

    out.index = pd.date_range(f"{year}-01-01 00:00", f"{year}-12-31 23:00", freq="h")
    out.index.name = "Date"

    # Target annual energy per substation, then the scale factor that makes
    # this year's profile hit it. In leap years scale == growth_factor; in
    # non-leap years it is slightly higher to make up for the dropped day.
    e_target = e_anchor * growth_factor
    e_base = out[p_cols].sum()
    scale = (e_target / e_base).where(e_base > 0, 0.0)

    for p_col in p_cols:
        out[p_col] *= scale[p_col]
        q_col = p_col[:-2] + "_q"
        if q_col in out.columns:
            out[q_col] *= scale[p_col]   # same factor keeps the power factor unchanged

    out.reset_index().to_csv(os.path.join(OUTPUT_DIR, f"load_timeseries_{year}.csv"), index=False)

    p_total = out[p_cols].sum(axis=1)
    summary.append({
        "year": year,
        "energy_growth_factor": growth_factor,
        "energy_sum_p": p_total.sum(),
        "coincident_peak": p_total.max(),
        "load_factor": p_total.mean() / p_total.max(),
    })

summary_df = pd.DataFrame(summary).set_index("year")
summary_df.to_csv(os.path.join(OUTPUT_DIR, "summary.csv"))

print(f"\nSystem summary, BAU year-by-year energy growth from {ANCHOR_YEAR} "
      f"(average {AVG_GROWTH:.2%} per year) "
      f"(same units as the input _p columns):")
print(summary_df.round(4).to_string())

# ===============================
# STEP 6: PLOTS (annual energy and peak power per planning year)
# ===============================
import matplotlib
matplotlib.use("Agg")              # write files only, no window (safe under Snakemake)
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

os.makedirs(PLOT_DIR, exist_ok=True)

INK, MUTED, GRID, SERIES = "#0b0b0b", "#52514e", "#e6e5e0", "#2a78d6"


def plot_planning_years(values, title, ylabel, filename, label_years):
    """One series on a true time axis, so the 5-year steps after 2030 are not squeezed."""
    years = list(values.index)
    fig, ax = plt.subplots(figsize=(9, 4.8), dpi=200)

    ax.plot(years, values.values, color=SERIES, linewidth=2, solid_capstyle="round",
            marker="o", markersize=7, markeredgecolor="white", markeredgewidth=1.5, zorder=3)

    # a few direct labels; the rest are read off the axis or summary.csv
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
    ax.text(0, 1.03, f"BAU: year-by-year annual energy growth from {ANCHOR_YEAR} "
                     f"(average {AVG_GROWTH:.2%} per year to {max(PLANNING_YEARS)})",
            transform=ax.transAxes, color=MUTED, fontsize=9.5)

    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(colors=MUTED, labelsize=9, length=3, color=GRID)
    ax.tick_params(axis="y", length=0)

    fig.tight_layout()
    path = os.path.join(PLOT_DIR, filename)
    fig.savefig(path, facecolor="white")
    plt.close(fig)
    print(f"Saved {path}")


label_years = [PLANNING_YEARS[0], 2030, 2040, PLANNING_YEARS[-1]]

plot_planning_years(
    summary_df["energy_sum_p"] / ENERGY_DIVISOR,
    "Annual electricity demand by planning year",
    f"Annual energy ({ENERGY_UNIT})",
    "annual_energy.png",
    label_years,
)

plot_planning_years(
    summary_df["coincident_peak"],
    "System coincident peak demand by planning year",
    f"Peak demand ({POWER_UNIT})",
    "peak_demand.png",
    label_years,
)

print("\nDemand timeseries generation complete.")