import pypsa
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
import numpy as np

# ---------------------------------------
# SETTINGS
# ---------------------------------------
YEARS = [2025, 2026, 2027, 2028, 2029, 2030, 2035, 2040, 2045, 2050]
NETWORK_DIR = Path("networks/m300/B")
OUT_DIR = Path("results/B")
OUT_DIR.mkdir(parents=True, exist_ok=True)

EXPORT_GEN_NAME = "Export_Mabote"

# ---------------------------------------
# DATA EXTRACTION
# ---------------------------------------
records = []

for year in YEARS:
    n = pypsa.Network(NETWORK_DIR / f"solved_{year}.nc")

    # Imports: positive
    if "imports" in n.generators.carrier.values:
        imports_gwh = (
            n.generators_t.p.loc[:, n.generators.carrier == "imports"]
            .sum()
            .sum() / 1000
        )
    else:
        imports_gwh = 0.0

    # Exports: already negative in PyPSA
    if EXPORT_GEN_NAME in n.generators.index:
        exports_gwh = (
            n.generators_t.p[EXPORT_GEN_NAME]
            .sum() / 1000
        )
    else:
        exports_gwh = 0.0

    # Net import (+ve = importer, -ve = exporter)
    net_gwh = imports_gwh + exports_gwh

    records.append({
        "year": year,
        "imports": imports_gwh,
        "exports": exports_gwh,   # keep negative
        "net": net_gwh
    })

df = pd.DataFrame(records).set_index("year")

# ---------------------------------------
# PLOTTING
# ---------------------------------------
fig, ax = plt.subplots(figsize=(14, 6))

x = np.arange(len(df.index))
bar_w = 0.4

# Bars
ax.bar(
    x,
    df["imports"],
    width=bar_w,
    label="Imports",
    color="#1ca33a"
)

ax.bar(
    x,
    df["exports"],
    width=bar_w,
    label="Exports",
    color="#790D77"
)

# Net line
ax.plot(
    x,
    df["net"],
    color="grey",
    linewidth=3,
    marker="o",
    label="Net import"
)

# Zero reference line
ax.axhline(0, color="black", linewidth=0.8)

# Labels
ax.set_xticks(x)
ax.set_xticklabels(df.index.astype(str))
ax.set_ylabel("Annual Energy (GWh)")
ax.set_title("Imports vs Exports with Net Import Export Balance (SQ)")

ax.legend(loc="upper right")
ax.grid(axis="y", alpha=0.3)

plt.tight_layout()
plt.savefig(OUT_DIR / "imports_exports_net_balance_negative.png", dpi=300)
plt.close()

print("Imports vs exports (negative) net balance plot saved successfully")
