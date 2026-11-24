import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

# -------------------------------------------------
# SETTINGS
# -------------------------------------------------
YEARS   = [2025, 2026, 2027, 2028, 2029, 2030, 2035, 2040, 2045, 2050]
DEMANDS = ["BAU", "M300"]      # demand scenarios to process
OPTION  = "B"                  # planned generation expansion (Option B)

LABELS  = {"BAU": "BAU demand", "M300": "M300 demand"}
COLORS  = {"BAU": "#1f77b4", "M300": "#d62728"}

COMPARE_DIR = Path(f"results/cost_analysis_{OPTION}")
COMPARE_DIR.mkdir(parents=True, exist_ok=True)


# -------------------------------------------------
# READ ONE DEMAND SCENARIO
# -------------------------------------------------
def collect(demand):
    results_dir = Path(f"results/{demand}/{OPTION}")
    records = []

    for year in YEARS:
        system_file = results_dir / f"summary_{year}_system.csv"
        gen_file    = results_dir / f"summary_{year}.csv"

        if not (system_file.exists() and gen_file.exists()):
            print(f"  {demand} {year}: files missing, skipped")
            continue

        system = pd.read_csv(system_file)
        gen    = pd.read_csv(gen_file)

        # ---- CAPEX (new builds only) ----
        gen_capex     = system["gen_new_build_cost"].iloc[0]
        storage_capex = system["storage_new_build_cost"].iloc[0]
        trans_capex   = system["transmission_reinforcement_cost"].iloc[0]
        capex_total   = gen_capex + storage_capex + trans_capex

        # ---- EXPORT REVENUE ----
        # Export_Mabote dispatches negative at +80 USD/MWh, so its operating_cost is negative
        export_rows    = gen[gen["carrier"] == "export"]
        export_revenue = -export_rows["operating_cost"].sum() if not export_rows.empty else 0.0
        export_GWh     = -export_rows["energy_GWh"].sum() if not export_rows.empty else 0.0

        # ---- OPEX ----
        # opex_total from solve_option_B.py sums ALL generators, export included,
        # so it is already NET of export revenue.
        opex_net   = system["opex_total"].iloc[0]
        opex_gross = opex_net + export_revenue

        # load shedding cost (VOLL), shown separately for information
        ls_rows = gen[gen["carrier"] == "load_shedding"]
        ls_cost = ls_rows["operating_cost"].sum() if not ls_rows.empty else 0.0
        ls_GWh  = ls_rows["energy_GWh"].sum() if not ls_rows.empty else 0.0

        # ---- GROSS + NET COST ----
        gross_cost = capex_total + opex_gross      # before export revenue
        net_cost   = capex_total + opex_net        # after export revenue

        # ---- DOMESTIC ENERGY SERVED ----
        # exclude exports (negative) and load shedding (energy NOT served)
        served = gen[~gen["carrier"].isin(["export", "load_shedding"])]
        served_kWh = served["energy_GWh"].sum() * 1e6

        cost_per_kwh = net_cost / served_kWh if served_kWh > 0 else 0.0

        records.append({
            "demand":            demand,
            "year":              year,
            "capex_gen":         gen_capex,
            "capex_storage":     storage_capex,
            "capex_trans":       trans_capex,
            "capex_total":       capex_total,
            "opex_gross":        opex_gross,
            "export_revenue":    export_revenue,
            "opex_net":          opex_net,
            "gross_cost":        gross_cost,
            "net_cost":          net_cost,
            "load_shedding_cost": ls_cost,
            "load_shedding_GWh": ls_GWh,
            "export_GWh":        export_GWh,
            "served_GWh":        served_kWh / 1e6,
            "cost_per_kWh":      cost_per_kwh,
        })

    return pd.DataFrame(records)


# -------------------------------------------------
# PER-DEMAND OUTPUTS
# -------------------------------------------------
all_dfs = []

for demand in DEMANDS:
    print(f"\n=== {demand} | Option {OPTION} ===")
    df = collect(demand)
    if df.empty:
        print(f"  No results for {demand}, skipped")
        continue
    all_dfs.append(df)

    out_dir = Path(f"results/{demand}/{OPTION}/cost_analysis")
    out_dir.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_dir / f"cost_summary_clean_{demand}.csv", index=False)

    x = df["year"]

    # ---- FIGURE 1: GROSS vs NET COST ----
    plt.figure(figsize=(8, 5))
    plt.plot(x, df["gross_cost"] / 1e6, marker="o", label="Gross cost (before exports)")
    plt.plot(x, df["net_cost"] / 1e6, marker="s", label="Net cost (after exports)")
    plt.xlabel("Year")
    plt.ylabel("Cost (million USD)")
    plt.title(f"Gross vs Net System Cost: {LABELS[demand]}, Option {OPTION}")
    plt.legend()
    plt.grid(alpha=0.5)
    plt.tight_layout()
    plt.savefig(out_dir / f"gross_vs_net_cost_{demand}.png", dpi=150)
    plt.close()

    # ---- FIGURE 2: COST STACK ----
    # Expenditure (CAPEX, gross OPEX) below zero, export revenue above zero.
    # Gross OPEX is used so export revenue is not shown twice.
    fig, ax = plt.subplots(figsize=(8, 5))
    bar_width = 0.6
    ax.bar(x, -df["capex_total"] / 1e6, width=bar_width, label="CAPEX", color="#1f77b4")
    ax.bar(x, -df["opex_gross"] / 1e6, width=bar_width, bottom=-df["capex_total"] / 1e6,
           label="OPEX", color="#ff7f0e")
    ax.bar(x, df["export_revenue"] / 1e6, width=bar_width, label="Export revenue", color="#2ca02c")
    ax.plot(x, -df["net_cost"] / 1e6, color="black", marker="D", linewidth=1.2,
            label="Net cost")
    ax.axhline(0, color="red", linestyle="--", linewidth=1.2)
    ax.set_xlabel("Year")
    ax.set_ylabel("Million USD (costs negative, revenue positive)")
    ax.legend()
    ax.grid(axis="y", linestyle="--", alpha=0.5)
    fig.tight_layout()
    fig.savefig(out_dir / f"cost_stack_{demand.lower()}.png", dpi=150)
    plt.close(fig)

    # ---- FIGURE 3: COST PER kWh ----
    plt.figure(figsize=(8, 5))
    plt.plot(x, df["cost_per_kWh"], marker="o")
    plt.xlabel("Year")
    plt.ylabel("USD/kWh")
    plt.title(f"Net Cost of Electricity Served: {LABELS[demand]}, Option {OPTION}")
    plt.grid(alpha=0.5)
    plt.tight_layout()
    plt.savefig(out_dir / f"cost_per_kwh_{demand}.png", dpi=150)
    plt.close()

    print(f"  Saved to {out_dir}")


# -------------------------------------------------
# BAU vs M300 COMPARISON
# -------------------------------------------------
if all_dfs:
    comp = pd.concat(all_dfs, ignore_index=True)
    comp.to_csv(COMPARE_DIR / "cost_summary_clean_BAU_vs_M300.csv", index=False)

    for col, ylabel, scale, fname in [
        ("net_cost",       "Net system cost (million USD)", 1e6, "net_cost_BAU_vs_M300.png"),
        ("capex_total",    "CAPEX (million USD)",           1e6, "capex_BAU_vs_M300.png"),
        ("export_revenue", "Export revenue (million USD)",  1e6, "export_revenue_BAU_vs_M300.png"),
        ("cost_per_kWh",   "Net cost (USD/kWh)",            1,   "cost_per_kwh_BAU_vs_M300.png"),
    ]:
        plt.figure(figsize=(8, 5))
        for demand, d in comp.groupby("demand"):
            plt.plot(d["year"], d[col] / scale, marker="o",
                     color=COLORS.get(demand), label=LABELS.get(demand, demand))
        plt.xlabel("Year")
        plt.ylabel(ylabel)
        plt.title(f"{ylabel.split(' (')[0]}: BAU vs M300, Option {OPTION}")
        plt.legend()
        plt.grid(alpha=0.5)
        plt.tight_layout()
        plt.savefig(COMPARE_DIR / fname, dpi=150)
        plt.close()

    print(f"\nComparison saved to {COMPARE_DIR}")

print("All figures generated successfully.")