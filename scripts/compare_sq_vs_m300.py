import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
import re

# =========================================================
# DIRECTORIES
# =========================================================
SQ_DIR    = Path(r"C:\Users\USER\pypsa-lesotho\data\article\load_BAU_supply_end")
M300_DIR  = Path(r"C:\Users\USER\pypsa-lesotho\data\article\load_M300_supply_end")
HIGH_DIR  = Path(r"C:\Users\USER\pypsa-lesotho\data\article\load_HE_supply_end")
LOW_DIR   = Path(r"C:\Users\USER\pypsa-lesotho\data\article\load_LE_supply_end")   # check: was "loads_LE_supply_end"

OUT_DIR = Path(r"C:\Users\USER\pypsa-lesotho\data\article\comparison_plots")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# =========================================================
# HELPERS
# =========================================================
def read_load_file(path: Path):
    df = pd.read_excel(path, sheet_name="Sheet1")
    df.columns = (
        df.columns.astype(str)
        .str.strip()
        .str.replace(r"\s+", " ", regex=True)
    )
    return df


def get_p_cols(df):
    return [c for c in df.columns if c.lower().endswith("_p")]


def annual_energy_and_peak(path: Path):
    df = read_load_file(path)
    p_cols = get_p_cols(df)

    system_p = df[p_cols].sum(axis=1, skipna=True)

    energy_gwh = system_p.sum() / 1000
    peak_mw = system_p.max()

    return energy_gwh, peak_mw


def build_summary(folder: Path, suffix: str):
    if not folder.exists():
        raise FileNotFoundError(f"Folder not found for '{suffix}': {folder}")

    rows = []

    for f in sorted(folder.glob("*.xlsx")):
        if f.name.startswith("~$"):
            continue

        match = re.search(r"(19|20)\d{2}", f.stem)
        if not match:
            continue

        year = int(match.group())
        energy, peak = annual_energy_and_peak(f)

        rows.append({
            "year": year,
            f"energy_{suffix}": energy,
            f"peak_{suffix}": peak
        })

    if not rows:
        raise FileNotFoundError(f"No yearly .xlsx load files found for '{suffix}' in {folder}")

    df = pd.DataFrame(rows).set_index("year").sort_index()
    print(f"{suffix}: {len(df)} years read from {folder}")
    return df


# =========================================================
# BUILD SUMMARIES
# =========================================================
sq_df    = build_summary(SQ_DIR, "sq")
m300_df  = build_summary(M300_DIR, "m300")
high_df  = build_summary(HIGH_DIR, "high")
low_df   = build_summary(LOW_DIR, "low")

comparison = (
    sq_df
    .join(m300_df, how="inner")
    .join(high_df, how="inner")
    .join(low_df, how="inner")
)

print("\nComparison table:")
print(comparison)
comparison.to_csv(OUT_DIR / "comparison_all_scenarios.csv")

# =========================================================
# PLOT 1: ANNUAL ENERGY (GWh)
# =========================================================
plt.figure(figsize=(10, 6))

plt.plot(comparison.index, comparison["energy_sq"],   marker="o", linewidth=2, label="BAU")
plt.plot(comparison.index, comparison["energy_m300"], marker="s", linewidth=2, linestyle="--", label="M300")
plt.plot(comparison.index, comparison["energy_high"], marker="^", linewidth=2, linestyle=":",  label="High Economy")
plt.plot(comparison.index, comparison["energy_low"],  marker="d", linewidth=2, linestyle="-.", label="Low Economy")

plt.xlabel("Year")
plt.ylabel("Annual Energy Demand (GWh)")
plt.title("Electricity Demand Outlook (Supply Side): Scenario Comparison")
plt.grid(True)
plt.legend()
plt.tight_layout()

energy_plot = OUT_DIR / "energy_comparison_all_scenarios.png"
plt.savefig(energy_plot, dpi=300)
plt.show()

# =========================================================
# PLOT 2: PEAK DEMAND (MW)
# =========================================================
plt.figure(figsize=(10, 6))

plt.plot(comparison.index, comparison["peak_sq"],   marker="o", linewidth=2, label="BAU")
plt.plot(comparison.index, comparison["peak_m300"], marker="s", linewidth=2, linestyle="--", label="M300")
plt.plot(comparison.index, comparison["peak_high"], marker="^", linewidth=2, linestyle=":",  label="High Economy")
plt.plot(comparison.index, comparison["peak_low"],  marker="d", linewidth=2, linestyle="-.", label="Low Economy")

plt.xlabel("Year")
plt.ylabel("Peak Demand (MW)")
plt.title("Peak Demand Outlook (Supply Side): Scenario Comparison")
plt.grid(True)
plt.legend()
plt.tight_layout()

peak_plot = OUT_DIR / "peak_comparison_all_scenarios.png"
plt.savefig(peak_plot, dpi=300)
plt.show()

print("\nPlots saved to:")
print(energy_plot)
print(peak_plot)