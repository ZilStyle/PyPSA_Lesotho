import pypsa
import pandas as pd
from pathlib import Path

# =================================================
# SETTINGS
# =================================================
YEARS = [2027, 2028, 2029, 2030]
SCENARIO = "B"

NETWORK_DIR = Path(f"networks/{SCENARIO}")
OUT_FILE = Path(f"results/{SCENARIO}/import_vs_storage_costs.csv")

records = []

# =================================================
# LOOP OVER YEARS
# =================================================
for year in YEARS:
    print(f"\nProcessing {year}...")

    n = pypsa.Network(NETWORK_DIR / f"solved_{year}.nc")

    # =================================================
    # IMPORTS
    # =================================================
    import_gens = n.generators[n.generators.carrier == "imports"]

    if not import_gens.empty:
        imp_p = n.generators_t.p[import_gens.index].clip(lower=0)

        imp_MWh = imp_p.sum().sum()

        imp_cost = (
            imp_p
            .multiply(import_gens["marginal_cost"], axis=1)
            .sum()
            .sum()
        )

        import_cost_per_MWh = imp_cost / imp_MWh if imp_MWh > 0 else 0

    else:
        imp_MWh = 0.0
        imp_cost = 0.0
        import_cost_per_MWh = 0.0

    # =================================================
    # STORAGE (ANNUALISED COST ALREADY)
    # =================================================
    su = n.storage_units.copy()

    if "p_nom_opt" not in su.columns:
        su["p_nom_opt"] = su["p_nom"]

    su["delta_MW"] = su["p_nom_opt"] - su["p_nom"]

    new_storage = su[su["delta_MW"] > 1e-3]

    total_new_storage_MW = new_storage["delta_MW"].sum()

    if not new_storage.empty:
        cap_cost = new_storage["capital_cost"].mean()  # USD/MW/year
    else:
        cap_cost = 0.0

    storage_annual_cost = total_new_storage_MW * cap_cost

    # =================================================
    # 🔥 ACTUAL STORAGE DISCHARGE
    # =================================================
    if not n.storage_units.empty:
        discharge = n.storage_units_t.p_dispatch.clip(lower=0)
        storage_MWh = discharge.sum().sum()
    else:
        storage_MWh = 0.0

    # TRUE cost per MWh
    storage_cost_per_MWh = (
        storage_annual_cost / storage_MWh
        if storage_MWh > 0 else 0
    )

        # =================================================
    # 🔍 STORAGE DIAGNOSTICS (VERY IMPORTANT)
    # =================================================
    print(f"\n--- STORAGE BREAKDOWN {year} ---")

    su = n.storage_units.copy()

    if "p_nom_opt" not in su.columns:
        su["p_nom_opt"] = su["p_nom"]

    su["delta_MW"] = su["p_nom_opt"] - su["p_nom"]

    print("\nInstalled capacities:")
    print(su[["bus", "p_nom", "p_nom_opt", "delta_MW"]])

    # ---------------------------------------------
    # DISPATCH PER STORAGE UNIT
    # ---------------------------------------------
    if not n.storage_units.empty:
        dispatch = n.storage_units_t.p_dispatch.clip(lower=0)

        discharge_per_unit = dispatch.sum()

        peak_discharge = dispatch.max()
        peak_time = dispatch.idxmax()

        storage_summary = pd.DataFrame({
            "discharge_MWh": discharge_per_unit,
            "peak_MW": peak_discharge,
            "peak_time": peak_time
        })

        print("\nDischarge by storage unit:")
        print(storage_summary)

        # -----------------------------------------
        # TOTAL DISCHARGE (CHECK)
        # -----------------------------------------
        total_discharge = discharge_per_unit.sum()

        print(f"\nTotal discharge (check): {total_discharge:.2f} MWh")

        # -----------------------------------------
        # UTILISATION FACTOR
        # -----------------------------------------
        total_capacity = su["p_nom_opt"].sum()

        if total_capacity > 0:
            utilisation = total_discharge / (total_capacity * 4 * 365)
        else:
            utilisation = 0

        print(f"Storage utilisation factor: {utilisation:.4f}")

    else:
        print("No storage in system.")

    # =================================================
    # SAVE RESULTS
    # =================================================
    records.append({
        "year": year,
        "imports_MWh": round(imp_MWh, 2),
        "imports_cost_USD": round(imp_cost, 2),
        "import_cost_per_MWh_USD": round(import_cost_per_MWh, 2),
        "new_storage_MW": round(total_new_storage_MW, 2),
        "storage_discharge_MWh": round(storage_MWh, 2),
        "storage_annual_cost_USD": round(storage_annual_cost, 2),
        "storage_cost_per_MWh_USD": round(storage_cost_per_MWh, 2)
    })

# =================================================
# OUTPUT
# =================================================
df = pd.DataFrame(records)

print("\n======================================")
print("IMPORT vs STORAGE COST COMPARISON")
print("======================================")
print(df)

OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
df.to_csv(OUT_FILE, index=False)

print(f"\nSaved results to: {OUT_FILE}")