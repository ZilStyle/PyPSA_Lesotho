import pypsa
import pandas as pd
from pathlib import Path

# ---------------------------------
# USER SETTINGS
# ---------------------------------
YEARS = [2025, 2030, 2035, 2040, 2045, 2050]
NETWORK_DIR = Path("networks/B")
OUTPUT_DIR  = Path("results/B")

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

records = []

# ---------------------------------
# LOOP THROUGH YEARS
# ---------------------------------
for year in YEARS:
    print(f"Processing year {year}")

    network_file = NETWORK_DIR / f"solved_{year}.nc"
    if not network_file.exists():
        print(f"  ⚠️ Network not found: {network_file}")
        continue

    n = pypsa.Network(network_file)

    # ---------------------------------
    # GENERATOR OPERATING COSTS
    # ---------------------------------
    dispatch = n.generators_t.p
    mc = n.generators["marginal_cost"]

    energy_MWh = dispatch.sum()
    opex_USD = energy_MWh * mc

    # ---------------------------------
    # GENERATOR INVESTMENT COSTS
    # ---------------------------------
    # capital_cost in PyPSA is already annualized
    capex_USD = n.generators["capital_cost"] * n.generators["p_nom_opt"]

    # ---------------------------------
    # STORE RESULTS PER GENERATOR
    # ---------------------------------
    for gen in n.generators.index:
        records.append({
            "year": year,
            "generator": gen,
            "carrier": n.generators.at[gen, "carrier"],
            "energy_GWh": energy_MWh.loc[gen] / 1e3,
            "operating_cost_USD": opex_USD.loc[gen],
            "investment_cost_USD": capex_USD.loc[gen],
            "total_cost_USD": opex_USD.loc[gen] + capex_USD.loc[gen],
            "marginal_cost_USD_per_MWh": mc.loc[gen],
            "capital_cost_USD_per_MW_yr": n.generators.at[gen, "capital_cost"],
            "installed_capacity_MW": n.generators.at[gen, "p_nom_opt"],
        })

# ---------------------------------
# CREATE DATAFRAME
# ---------------------------------
df = pd.DataFrame(records)

# ---------------------------------
# AGGREGATE BY CARRIER
# ---------------------------------
carrier_summary = (
    df.groupby(["year", "carrier"], as_index=False)
      .agg(
          energy_GWh=("energy_GWh", "sum"),
          operating_cost_USD=("operating_cost_USD", "sum"),
          investment_cost_USD=("investment_cost_USD", "sum"),
          total_cost_USD=("total_cost_USD", "sum"),
          installed_capacity_MW=("installed_capacity_MW", "sum"),
      )
)

# ---------------------------------
# SAVE OUTPUTS
# ---------------------------------
df.to_csv(OUTPUT_DIR / "generator_costs_detailed_all_years.csv", index=False)
carrier_summary.to_csv(
    OUTPUT_DIR / "generator_costs_by_carrier_all_years.csv",
    index=False
)

print("\n✅ Saved:")
print(" - results/B/generator_costs_detailed_all_years.csv")
print(" - results/B/generator_costs_by_carrier_all_years.csv")
