import pandas as pd
import numpy as np
from pathlib import Path

# --------------------------------------------------
# SETTINGS
# --------------------------------------------------

COST_FILE = Path("data/planned/expansion_costs.xlsx")
OUTPUT_DIR = Path("data/planned/processed_costs")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# --------------------------------------------------
# HELPER FUNCTIONS
# --------------------------------------------------

def annuity(r, n):
    """
    Annualisation factor
    """
    return r / (1 - (1 + r) ** (-n))


def split_round_trip_efficiency(rte):
    """
    Split round-trip efficiency evenly
    """
    eta = np.sqrt(rte)
    return eta, eta


# --------------------------------------------------
# LOAD RAW COST DATA
# --------------------------------------------------

df = pd.read_excel(COST_FILE)

# Normalise carrier names
df["Carrier"] = df["Carrier"].str.lower().str.strip()

# --------------------------------------------------
# GENERATORS (INCLUDING IMPORTS)
# --------------------------------------------------

gen_mask = (
    (
        df["Investment_usd_per_Kw"].notna() |
        (df["Carrier"] == "imports")
    ) &
    (~df["Carrier"].isin(["storage", "transmission"]))
)

gens = df[gen_mask].copy()

# Fill missing values safely
gens["Investment_usd_per_Kw"] = gens["Investment_usd_per_Kw"].fillna(0.0)
gens["FOM_percent_per_year"] = gens["FOM_percent_per_year"].fillna(0.0)
gens["VOM_usd_per_mwh"] = gens["VOM_usd_per_mwh"].fillna(0.0)

# CAPEX in USD/MW
gens["capex_usd_per_mw"] = gens["Investment_usd_per_Kw"] * 1000

# Annuity factor
gens["annuity_factor"] = annuity(
    gens["Discount_rate"], gens["Lifetime_years"]
)

# Annualised capital cost (USD/MW/year)
gens["capital_cost"] = (
    gens["capex_usd_per_mw"] * gens["annuity_factor"] +
    gens["capex_usd_per_mw"] * gens["FOM_percent_per_year"] / 100
)

# Marginal cost (USD/MWh)
gens["marginal_cost"] = gens["VOM_usd_per_mwh"]

generators_out = gens[
    [
        "Technology",
        "Carrier",
        "year",
        "capital_cost",
        "marginal_cost",
        "Efficiency",
        "CO2_emissions_t_per_mwh"
    ]
]

generators_out.to_csv(
    OUTPUT_DIR / "generators_costs.csv",
    index=False
)

print("✔ Generator costs processed (including imports)")

# --------------------------------------------------
# STORAGE UNITS
# --------------------------------------------------

storage = df[df["Carrier"] == "storage"].copy()

storage["Investment_usd_per_Kw"] = storage["Investment_usd_per_Kw"].fillna(0.0)
storage["FOM_percent_per_year"] = storage["FOM_percent_per_year"].fillna(0.0)

storage["capex_usd_per_mw"] = storage["Investment_usd_per_Kw"] * 1000

storage["annuity_factor"] = annuity(
    storage["Discount_rate"], storage["Lifetime_years"]
)

storage["capital_cost"] = (
    storage["capex_usd_per_mw"] * storage["annuity_factor"] +
    storage["capex_usd_per_mw"] * storage["FOM_percent_per_year"] / 100
)

# Storage duration
storage["max_hours"] = storage["Battery_duration_hours"].fillna(
    storage["PHS_duration_hours"]
)

# Efficiencies
storage[["efficiency_store", "efficiency_dispatch"]] = (
    storage["round_trip_efficiency"]
    .apply(split_round_trip_efficiency)
    .to_list()
)

storage_out = storage[
    [
        "Technology",
        "Carrier",
        "year",
        "capital_cost",
        "max_hours",
        "efficiency_store",
        "efficiency_dispatch"
    ]
]

storage_out.to_csv(
    OUTPUT_DIR / "storage_costs.csv",
    index=False
)

print("✔ Storage costs processed")

# --------------------------------------------------
# TRANSMISSION (MW-km BASED)
# --------------------------------------------------

tx = df[df["Carrier"].isin(["transmission", "ac", "line", "lines"])].copy()

tx["annuity_factor"] = annuity(
    tx["Discount_rate"], tx["Lifetime_years"]
)

transmission_out = tx[
    [
        "Technology",
        "Carrier",
        "year",
        "Investment_usd_per_MW_km",
        "FOM_percent_per_year",
        "annuity_factor"
    ]
]

transmission_out.to_csv(
    OUTPUT_DIR / "transmission_costs.csv",
    index=False
)

print("✔ Transmission costs processed")

# --------------------------------------------------
# DONE
# --------------------------------------------------

print("\nAll cost preprocessing completed successfully.")
print(f"Processed files written to: {OUTPUT_DIR}")
