import pypsa
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path

# ---------------------------------------
# SETTINGS
# ---------------------------------------
YEARS = [2025, 2026, 2027, 2028, 2029, 2030, 2035, 2040, 2045, 2050]
NETWORK_DIR = Path("networks/A")

OUT_DIR = Path("results/A")
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT_FILE = OUT_DIR / "installed_capacity_stacked.png"

TECHS = ["solar", "wind", "hydro", "battery"]

COLORS = {
    "solar": "#fae70f",
    "wind": "#17becf",
    "hydro": "#440dfa",
    "battery": "black"
}

# ---------------------------------------
# COLLECT CAPACITY DATA
# ---------------------------------------
records = []

for year in YEARS:
    n = pypsa.Network(NETWORK_DIR / f"solved_{year}.nc")

    row = {"year": year}

    # Generator capacity
    gen_caps = (
        n.generators
        .groupby("carrier")["p_nom"]
        .sum()
    )

    # Battery power capacity (MW)
    battery_cap = (
        n.storage_units.p_nom.sum()
        if not n.storage_units.empty
        else 0.0
    )

    row["solar"] = gen_caps.get("solar", 0.0)
    row["wind"]  = gen_caps.get("wind", 0.0)
    row["hydro"] = gen_caps.get("hydro", 0.0)
    row["battery"] = battery_cap

    records.append(row)

df = pd.DataFrame(records).set_index("year")

# ---------------------------------------
# PLOT
# ---------------------------------------
fig, ax = plt.subplots(figsize=(12, 6))

x = np.arange(len(df.index))
bottom = np.zeros(len(df.index))

for tech in TECHS:
    values = df[tech].values

    bars = ax.bar(
        x,
        values,
        bottom=bottom,
        label=tech.capitalize(),
        color=COLORS[tech],
        width=0.65
    )

    # Centered white labels
    for i, v in enumerate(values):
        if v > 1:
            ax.text(
                x[i],
                bottom[i] + v / 2,
                f"{v:.0f}",
                ha="center",
                va="center",
                fontsize=9,
                color="white",
                fontweight="bold"
            )

    bottom += values

# ---------------------------------------
# FORMATTING
# ---------------------------------------
ax.set_xticks(x)
ax.set_xticklabels(df.index.astype(str))
ax.set_ylabel("Installed Capacity (MW)", fontsize=12)


ax.legend(
    title="Technology",
    bbox_to_anchor=(1.02, 0.5),
    loc="center left"
)

ax.grid(axis="y", alpha=0.25)

plt.tight_layout()
plt.savefig(OUT_FILE, dpi=300)
plt.close()

print(f"Saved stacked installed capacity plot to: {OUT_FILE}")
