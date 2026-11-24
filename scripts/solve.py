import pypsa
import pandas as pd
import numpy as np
import os

# -----------------------------
# INPUTS
# -----------------------------
network_file = snakemake.input.network
output_network = snakemake.output.network
output_summary = snakemake.output.summary

year = int(snakemake.wildcards.year)

is_option_A = "costs" in snakemake.input

if is_option_A:
    costs_file = snakemake.input.costs
    print("Running Option A: dispatch-only")
else:
    print("Running Option B: expansion + dispatch (with 15% reserve margin)")

# -----------------------------
# LOAD NETWORK
# -----------------------------
n = pypsa.Network(network_file)

# -----------------------------
# OPTION A: READ AND APPLY COSTS
# -----------------------------
if is_option_A:

    costs = pd.read_excel(costs_file)

    required_cols = {"year", "carrier", "marginal_cost"}
    missing = required_cols - set(costs.columns)
    if missing:
        raise ValueError(f"Missing columns in costs.xlsx: {missing}")

    costs_year = costs[costs["year"] == year]
    if costs_year.empty:
        raise ValueError(f"No cost data found for year {year}")

    # Apply marginal costs
    for _, row in costs_year.iterrows():
        carrier = row["carrier"]
        mc = float(row["marginal_cost"])

        if carrier in n.generators.carrier.values:
            n.generators.loc[n.generators.carrier == carrier, "marginal_cost"] = mc

    # Enforce no expansion in Option A
    n.generators["p_nom_extendable"] = False
    if not n.storage_units.empty:
        n.storage_units["p_nom_extendable"] = False

# -----------------------------
# ADD LOAD SHEDDING (A and B)
# -----------------------------
if is_option_A:
    voll = float(
        costs_year.loc[costs_year.carrier == "load_shedding", "marginal_cost"].iloc[0]
    )
else:
    voll = 10_000.0  # USD/MWh safe fallback

for bus in n.buses.index:
    ls = f"LoadShedding_{bus}"
    if ls not in n.generators.index:
        n.add(
            "Generator",
            name=ls,
            bus=bus,
            carrier="load_shedding",
            p_nom_extendable=True,
            marginal_cost=voll
        )

# -----------------------------
# ENSURE ALL CARRIERS EXIST
# -----------------------------
all_carriers = set()

if "carrier" in n.lines.columns:
    all_carriers |= set(n.lines.carrier.dropna().unique())

if "carrier" in n.generators.columns:
    all_carriers |= set(n.generators.carrier.dropna().unique())

if not n.storage_units.empty and "carrier" in n.storage_units.columns:
    all_carriers |= set(n.storage_units.carrier.dropna().unique())

if "carrier" in n.buses.columns:
    all_carriers |= set(n.buses.carrier.dropna().unique())

if "carrier" in n.links.columns:
    all_carriers |= set(n.links.carrier.dropna().unique())


for c in all_carriers:
    if c not in n.carriers.index:
        n.add("Carrier", name=c)

# -----------------------------
# OXBOW DAILY ENERGY CONSTRAINT
# -----------------------------
def add_oxbow_daily_energy_limit(n, sns):
    if "Oxbow" not in n.generators.index:
        return

    model = n.model
    snapshots = pd.Index(sns)
    days = snapshots.normalize().unique()

    for day in days:
        idx = snapshots[snapshots.normalize() == day]

        model.add_constraints(
            model.variables["Generator-p"].loc[idx, "Oxbow"].sum() <= 90 * 7,
            name=f"oxbow_daily_energy_{day.date()}"
        )

# -----------------------------
# OPTION B: IRP-STYLE RESERVE MARGIN CONSTRAINT
# -----------------------------
def add_planning_reserve_margin_irp(
    n,
    sns,
    reserve_margin=0.15,
    top_n_peak_hours=100,
    peak_duration_hours=4.0,
    import_capacity_credit=1.0,
):
    model = n.model
    snapshots = pd.Index(sns)

    if n.loads_t.p_set.empty:
        raise ValueError("loads_t.p_set is empty, cannot compute reserve margin.")

    total_load = n.loads_t.p_set.sum(axis=1).reindex(snapshots).dropna()
    if total_load.empty:
        raise ValueError("Total load series is empty after aligning to snapshots.")

    peak_load = float(total_load.max())
    required_capacity = (1.0 + reserve_margin) * peak_load

    n_hours = min(top_n_peak_hours, len(total_load))
    peak_hours = total_load.nlargest(n_hours).index

    # -----------------------------
    # GENERATOR CAPACITY CREDITS
    # -----------------------------
    credits_gen = pd.Series(1.0, index=n.generators.index, dtype=float)

    # Load shedding must never count as firm capacity
    ls_idx = n.generators.index[n.generators.carrier == "load_shedding"]
    if len(ls_idx) > 0:
        credits_gen.loc[ls_idx] = 0.0

    # Imports credit
    imports_idx = n.generators.index[n.generators.carrier == "imports"]
    if len(imports_idx) > 0:
        credits_gen.loc[imports_idx] = float(import_capacity_credit)

    # Solar/Wind credit as mean availability during peak-risk hours
    vres_idx = n.generators.index[n.generators.carrier.isin(["solar", "wind"])]
    if len(vres_idx) > 0:
        if n.generators_t.p_max_pu.empty:
            raise ValueError("generators_t.p_max_pu is empty, cannot compute VRE credits.")
        pmax_peak = n.generators_t.p_max_pu.loc[peak_hours, vres_idx].astype(float)
        credits_gen.loc[vres_idx] = pmax_peak.mean(axis=0).clip(0.0, 1.0)

    # -----------------------------
    # BUILD SYMBOLIC LHS
    # -----------------------------
    gen_var = model.variables["Generator-p_nom"]

    ext_g = n.generators.index[n.generators.p_nom_extendable.astype(bool)]
    if len(ext_g) > 0:
        lhs = 0 * gen_var.loc[ext_g[0]]
    else:
        any_g = n.generators.index
        lhs = 0 * gen_var.loc[any_g[0]]

    # Fixed generators contribute fixed capacity
    fixed_g = n.generators.index[~n.generators.p_nom_extendable.astype(bool)]
    if len(fixed_g) > 0:
        lhs += float((credits_gen.loc[fixed_g] * n.generators.loc[fixed_g, "p_nom"]).sum())

    # Extendable generators contribute decision capacity
    if len(ext_g) > 0:
        lhs += (gen_var.loc[ext_g] * credits_gen.loc[ext_g]).sum()

    # -----------------------------
    # STORAGE UNITS (POWER CREDIT)
    # -----------------------------
    if not n.storage_units.empty:

        max_hours = n.storage_units["max_hours"].astype(float).fillna(0.0)
        credits_su = (max_hours / float(peak_duration_hours)).clip(0.0, 1.0)

        fixed_su = n.storage_units.index[~n.storage_units.p_nom_extendable.astype(bool)]
        if len(fixed_su) > 0:
            lhs += float(
                (credits_su.loc[fixed_su] *
                 n.storage_units.loc[fixed_su, "p_nom"]).sum()
            )

        ext_su = n.storage_units.index[n.storage_units.p_nom_extendable.astype(bool)]
        if len(ext_su) > 0 and "StorageUnit-p_nom" in model.variables:
            su_var = model.variables["StorageUnit-p_nom"]
            lhs += (su_var.loc[ext_su] * credits_su.loc[ext_su]).sum()

    # Add reserve margin constraint
    model.add_constraints(lhs >= required_capacity, name="planning_reserve_margin_irp")

    print(
        f"[Reserve Margin IRP] Peak load={peak_load:.2f} MW | "
        f"Required={required_capacity:.2f} MW | "
        f"TopPeakHours={n_hours} | "
        f"StoragePeakDuration={peak_duration_hours}h | "
        f"ImportCredit={import_capacity_credit:.2f}"
    )

# -----------------------------
# EXTRA FUNCTIONALITY WRAPPER
# -----------------------------
def extra_constraints(n, sns):
    add_oxbow_daily_energy_limit(n, sns)
    if not is_option_A:
        add_planning_reserve_margin_irp(
            n,
            sns,
            reserve_margin=0.15,
            top_n_peak_hours=100,
            peak_duration_hours=4.0,
            import_capacity_credit=1.0
        )


if not is_option_A:
    mc_by_carrier = n.generators.groupby("carrier")["marginal_cost"].mean()
    print("Mean marginal cost by carrier:\n", mc_by_carrier)

    if mc_by_carrier.dropna().max() == 0:
        raise ValueError("All generator marginal costs are zero in Option B. Preprocessing likely not applied.")

# -----------------------------
# SOLVE
# -----------------------------
n.optimize(
    solver_name="highs",
    extra_functionality=extra_constraints
)

# -----------------------------
# COST BREAKDOWN
# -----------------------------
dispatch = n.generators_t.p
mc = n.generators.marginal_cost

energy_MWh = dispatch.sum()
costs_by_gen = energy_MWh * mc

summary = (
    pd.DataFrame({
        "carrier": n.generators.carrier,
        "energy_GWh": energy_MWh / 1e3,
        "operating_cost": costs_by_gen
    })
    .groupby("carrier")
    .sum()
    .reset_index()
)

summary["year"] = year
summary.to_csv(output_summary, index=False)

# -----------------------------
# SAVE NETWORK
# -----------------------------
os.makedirs(os.path.dirname(output_network), exist_ok=True)
n.export_to_netcdf(output_network)

print("Solve completed successfully")
