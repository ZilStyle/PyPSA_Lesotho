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
# DATA EXTRACTION
# ---------------------------------------
records = []

for year in YEARS:
    n = pypsa.Network(NETWORK_DIR / f"solved_{year}.nc")

    # Physical generators only (NO imports / exports)
    phys_gens = n.generators[
        ~n.generators.carrier.isin(["imports", "export", "load_shedding"])
    ]

    gen_caps = (
        phys_gens
        .groupby("carrier")["p_nom_opt"]
        .sum()
    )

    row = {"year": year}

    for carrier, cap in gen_caps.items():
        row[carrier] = cap

    # Storage power capacity (MW)
    if not n.storage_units.empty:
        row["storage"] = n.storage_units["p_nom_opt"].sum()
    else:
        row["storage"] = 0.0

    records.append(row)

df = (
    pd.DataFrame(records)
    .set_index("year")
    .fillna(0.0)
)

# ---------------------------------------
# ORDER FOR STACKING
# ---------------------------------------
carrier_order = ["solar", "wind", "hydro", "storage"]
carrier_order = [c for c in carrier_order if c in df.columns]
df = df[carrier_order]

# ---------------------------------------
# PLOTTING
# ---------------------------------------
fig, ax = plt.subplots(figsize=(14, 7))

x = np.arange(len(df.index))
bottom = np.zeros(len(df.index))

colors = {
    "solar": "#fae70f",
    "wind": "#17becf",
    "hydro": "#440dfa",
    "storage": "#000000"
}

bars = {}

for carrier in df.columns:
    bars[carrier] = ax.bar(
        x,
        df[carrier],
        bottom=bottom,
        label=carrier.title(),
        color=colors.get(carrier, "grey")
    )

    # --- CENTERED WHITE LABELS ---
    for rect, val in zip(bars[carrier], df[carrier].values):
        if val > 0:
            ax.text(
                rect.get_x() + rect.get_width() / 2,
                rect.get_y() + rect.get_height() / 2,
                f"{val:.0f}",
                ha="center",
                va="center",
                color="white",
                fontsize=9,
                fontweight="bold"
            )

    bottom += df[carrier].values

# ---------------------------------------
# FORMATTING
# ---------------------------------------
ax.set_xticks(x)
ax.set_xticklabels(df.index.astype(str))
ax.set_ylabel("Installed Capacity (MW)")
ax.set_title("Installed Capacity Expansion (M300)")

ax.legend(
    loc="center left",
    bbox_to_anchor=(1.02, 0.5),
    frameon=False
)

ax.grid(axis="y", alpha=0.3)

plt.tight_layout()
plt.savefig(
    OUT_DIR / "installed_capacity_expansion_physical_only_optionB.png",
    dpi=300
)
plt.close()

print("Installed capacity plot with centered white labels saved successfully")
