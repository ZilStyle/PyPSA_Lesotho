
import logging
import warnings

warnings.filterwarnings("ignore", message=".*were not assigned to the network.*")
logging.getLogger("pypsa.optimization.optimize").setLevel(logging.ERROR)
import pypsa
import pandas as pd
import numpy as np
import os
import linopy
# -------------------------------------------------
# INPUTS (OPTION B ONLY)
# -------------------------------------------------
network_file  = snakemake.input.network
output_network = snakemake.output.network
output_summary = snakemake.output.summary

# At the top of both solve scripts
solver_name = snakemake.config["solving"]["solver"]
solver_options = snakemake.config["solving"].get("solver_options", {})


year = int(snakemake.wildcards.year)

print(f"Running Option B (planning + expansion) | Year {year}")

# -------------------------------------------------
# LOAD NETWORK (ALREADY PREPROCESSED & COSTED)
# -------------------------------------------------
n = pypsa.Network(network_file)
#++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
snapshots = n.snapshots

peak_hours = snapshots[(snapshots.hour >= 18) & (snapshots.hour <= 21)]
offpeak_hours = snapshots[~snapshots.isin(peak_hours)]
#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# -------------------------------------------------
# LOAD SHEDDING (PLANNING BACKSTOP)
# -------------------------------------------------
VOLL = 10_000.0  # USD/MWh

for bus in n.buses.index:
    ls = f"LoadShedding_{bus}"
    if ls not in n.generators.index:
        n.add(
            "Generator",
            name=ls,
            bus=bus,
            carrier="load_shedding",
            p_nom_extendable=True,
            marginal_cost=VOLL
        )

# -------------------------------------------------
# ENSURE ALL CARRIERS EXIST
# -------------------------------------------------
all_carriers = set()

for comp in [n.generators, n.lines, n.links, n.buses]:
    if "carrier" in comp.columns:
        all_carriers |= set(comp.carrier.dropna().unique())

if not n.storage_units.empty and "carrier" in n.storage_units.columns:
    all_carriers |= set(n.storage_units.carrier.dropna().unique())

if "export" not in n.carriers.index:
    n.add("Carrier", "export")


for c in all_carriers:
    if c not in n.carriers.index:
        n.add("Carrier", name=c)

# -------------------------------------------------
# OXBOW DAILY ENERGY LIMIT
# -------------------------------------------------
def add_oxbow_daily_energy_limit(n, snapshots):

    if "Oxbow" not in n.generators.index:
        return

    model = n.model
    sns = pd.Index(snapshots)

    for day in sns.normalize().unique():
        idx = sns[sns.normalize() == day]

        model.add_constraints(
            model.variables["Generator-p"].sel(Generator="Oxbow", snapshot=idx).sum()
            <= 90 * 7,
            name=f"oxbow_daily_energy_{day.date()}"
        )

# -------------------------------------------------
# IRP-STYLE PLANNING RESERVE MARGIN
# -------------------------------------------------
def add_planning_reserve_margin_irp(
    n,
    sns,
    reserve_margin=0.15,
    top_n_peak_hours=100,
    peak_duration_hours=4.0,
    import_capacity_credit=1.0, #was 1.0
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

def add_import_cap(n, sns, import_cap_mw=220.0):
    model = n.model
    imports = n.generators.index[n.generators.carrier == "imports"]
    if len(imports) == 0:
        return

    p = model.variables["Generator-p"]

    # For each snapshot: sum(imports dispatch) <= 220 MW
    for sn in sns:
        model.add_constraints(
            p.sel(snapshot=sn, Generator=imports).sum() <= import_cap_mw,
            name=f"imports_cap_{sn}"
        )

# -------------------------------------------------
# PEAK HOUR IMPORT CAP
# Restricts imports during peak hours (18-21)
# to force battery investment for peak adequacy
# Reflects real transmission congestion constraints
# -------------------------------------------------
def add_peak_import_cap(n, sns, peak_import_cap_mw=150.0):
    model = n.model
    imports = n.generators.index[n.generators.carrier == "imports"]

    if len(imports) == 0:
        return

    p = model.variables["Generator-p"]
    peak_hours = sns[(sns.hour >= 18) & (sns.hour <= 21)]

    for sn in peak_hours:
        model.add_constraints(
            p.sel(snapshot=sn, Generator=imports).sum() <= peak_import_cap_mw,
            name=f"peak_imports_cap_{sn}"
        )

    print(f"[Peak Import Cap] Imports capped at {peak_import_cap_mw} MW during peak hours ({len(peak_hours)} snapshots)")

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# ============================================================
# BATTERY OPERATION WINDOWS
# Charge: solar hours only (06-17)
# Discharge: peak hours only (18-21)
# Idle: night hours (22-05)
# ============================================================

solar_hours = snapshots[(snapshots.hour >= 6) & (snapshots.hour <= 17)]
peak_hours  = snapshots[(snapshots.hour >= 18) & (snapshots.hour <= 21)]
night_hours = snapshots[(snapshots.hour < 6) | (snapshots.hour > 21)]

for su in n.storage_units.index:
    # Charge ONLY during solar hours
    n.storage_units_t.p_store.loc[peak_hours, su]  = 0  # no charging at peak
    n.storage_units_t.p_store.loc[night_hours, su] = 0  # no charging at night

    # Discharge ONLY during peak hours
    n.storage_units_t.p_dispatch.loc[solar_hours, su] = 0  # no discharge during solar
    n.storage_units_t.p_dispatch.loc[night_hours, su] = 0  # no discharge at night


# ============================================================
# MINIMUM PEAK DISCHARGE CONSTRAINT
def enforce_peak_discharge(n, snapshots):
    # No storage units in network — skip entirely
    if n.storage_units.empty:
        print("[Peak Discharge] No storage units found — skipping")
        return

    peak_hours = snapshots[(snapshots.hour >= 18) & (snapshots.hour <= 21)]
    non_peak   = snapshots[~snapshots.isin(peak_hours)]

    # Check if model variables exist before accessing
    if "StorageUnit-p_dispatch" not in n.model.variables:
        print("[Peak Discharge] StorageUnit-p_dispatch not in model — skipping")
        return

    if "StorageUnit-p_store" not in n.model.variables:
        print("[Peak Discharge] StorageUnit-p_store not in model — skipping")
        return

    p_dispatch = n.model.variables["StorageUnit-p_dispatch"]
    p_store    = n.model.variables["StorageUnit-p_store"]

    ext_su = n.storage_units.index[n.storage_units.p_nom_extendable.astype(bool)]
    fix_su = n.storage_units.index[~n.storage_units.p_nom_extendable.astype(bool)]

    for su in n.storage_units.index:
        # -----------------------------------------------
        # 1. NO discharge outside peak
        # -----------------------------------------------
        for t in non_peak:
            n.model.add_constraints(
                p_dispatch.loc[t, su] == 0,
                name=f"no_discharge_nonpeak_{su}_{t}"
            )

        # -----------------------------------------------
        # 2. NO charging during peak — HARD CONSTRAINT
        # This is the key fix — enforced by optimizer
        # not just by pre-setting p_store values
        # -----------------------------------------------
        for t in peak_hours:
            n.model.add_constraints(
                p_store.loc[t, su] == 0,
                name=f"no_charging_peak_{su}_{t}"
            )

    # -----------------------------------------------
    # 3. Minimum discharge during peak
    # -----------------------------------------------
    for su in fix_su:
        p_nom = n.storage_units.at[su, "p_nom"]
        min_discharge = 0.5 * p_nom
        for t in peak_hours:
            n.model.add_constraints(
                p_dispatch.loc[t, su] >= min_discharge,
                name=f"min_peak_discharge_{su}_{t}"
            )

    for su in ext_su:
        p_nom_var = n.model.variables["StorageUnit-p_nom"].loc[su]
        for t in peak_hours:
            n.model.add_constraints(
                p_dispatch.loc[t, su] >= 0.5 * p_nom_var,
                name=f"min_peak_discharge_{su}_{t}"
            )

    print(f"[Peak Discharge] No charging during peak enforced via hard constraints")
#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def enforce_battery_discharge_at_18(n, snapshots):
    if n.storage_units.empty:
        print("[Battery 18h] No storage units — skipping")
        return

    if "StorageUnit-p_nom" not in n.model.variables:
        print("[Battery 18h] StorageUnit-p_nom not in model — skipping")
        return
        
    m = n.model

    all_su = n.storage_units.index
    ext_su = n.storage_units.index[n.storage_units.p_nom_extendable.astype(bool)]
    fix_su = n.storage_units.index[~n.storage_units.p_nom_extendable.astype(bool)]

    if len(all_su) == 0:
        return

    snaps18 = snapshots[snapshots.hour == 18]
    if len(snaps18) == 0:
        print("[Battery 18h] No 18:00 snapshots found — skipping")
        return

    p_dispatch = m.variables["StorageUnit-p_dispatch"]
    alpha = 0.8

    for sn in snaps18:
        # LHS: total dispatch at 18:00 across all storage units
        lhs = p_dispatch.loc[sn, all_su].sum()

        # RHS: build entirely as a LinearExpression
        if len(ext_su) > 0 and "StorageUnit-p_nom" in m.variables:
            p_nom_var = m.variables["StorageUnit-p_nom"]

            # Start RHS from extendable variable expression
            rhs = alpha * p_nom_var.loc[ext_su].sum()

            # Add fixed unit contribution as a constant to the LHS side
            # by subtracting from LHS instead of adding to RHS
            if len(fix_su) > 0:
                fixed_capacity = float(
                    (n.storage_units.loc[fix_su, "p_nom"] * alpha).sum()
                )
                # Move fixed constant to LHS: lhs - fixed >= rhs_var
                m.add_constraints(
                    lhs - fixed_capacity >= rhs,
                    name=f"battery_discharge_min_18_{sn}"
                )
            else:
                m.add_constraints(
                    lhs >= rhs,
                    name=f"battery_discharge_min_18_{sn}"
                )
        else:
            # All fixed — pure constant RHS
            fixed_capacity = float(
                (n.storage_units.loc[fix_su, "p_nom"] * alpha).sum()
            )
            m.add_constraints(
                lhs >= fixed_capacity,
                name=f"battery_discharge_min_18_{sn}"
            )

    print(
        f"[Battery 18h Dispatch] Forced ≥{int(alpha*100)}% discharge at 18:00 "
        f"across {len(snaps18)} days | "
        f"Fixed={len(fix_su)} units, Extendable={len(ext_su)} units"
    )
# -------------------------------------------------
def extra_functionality(n, snapshots):
    add_oxbow_daily_energy_limit(n, snapshots)
    add_planning_reserve_margin_irp(n, snapshots)
    add_import_cap(n, snapshots, import_cap_mw=220.0)
   # add_peak_import_cap(n, snapshots, peak_import_cap_mw=182.0)  # ← ADD
    enforce_peak_discharge(n, snapshots)
    enforce_battery_discharge_at_18(n, snapshots)
    

    
# -------------------------------------------------
# SAFETY CHECK: COSTS MUST EXIST
# -------------------------------------------------
mc_by_carrier = n.generators.groupby("carrier")["marginal_cost"].mean()
print("Mean marginal cost by carrier:\n", mc_by_carrier)

if mc_by_carrier.dropna().max() == 0:
    raise ValueError(
        "All generator marginal costs are zero. "
        "Cost preprocessing was not applied."
    )


# -----------------------------
# EXPORT SINK AT MABOTE (Option B)
# Negative generator dispatch = consumes power, and "marginal_cost" becomes revenue
# -----------------------------
EXPORT_BUS   = "Mabote Trans"   # <-- MUST match your actual bus name
EXPORT_NAME  = "Export_Mabote"
EXPORT_PRICE = 80            # USD/MWh, set your assumed export tariff
EXPORT_CAP   = 180            # MW, set the interconnector/export cap you want (or keep moderate)
Export_Start_year = 2027

if EXPORT_BUS not in n.buses.index:
    raise ValueError(f"Export bus '{EXPORT_BUS}' not found. Check spelling vs buses.xlsx.")

if year >=Export_Start_year:
    if EXPORT_NAME not in n.generators.index:
        n.add(
            "Generator",
            name=EXPORT_NAME,
            bus=EXPORT_BUS,
            carrier="export",
            # negative dispatch window: p in [-p_nom, 0]
            p_min_pu=-1.0,
            p_max_pu=0.0,
            p_nom=0.0,
            p_nom_extendable=True,     # allow export capability to expand if you want
            p_nom_max=EXPORT_CAP,      # hard cap on export capability
            capital_cost=0.0,          # exporting itself has no capex unless you want to price interconnector upgrades
            marginal_cost=EXPORT_PRICE # this becomes REVENUE because dispatch is negative
    )




# -------------------------------------------------
# SOLVE (EXPANSION + DISPATCH)
# -------------------------------------------------

print("Available solvers:", linopy.solvers.available_solvers)

# -------------------------------------------------
# SOLVE (REPLACE YOUR CURRENT STEP 1 + STEP 2)
# -------------------------------------------------

n.optimize(
    solver_name=solver_name,
    solver_options=solver_options,
    extra_functionality=extra_functionality
)

print("Solver used:", solver_name)
# ---------------------------------------
# SAVE OBJECTIVE VALUE
# ---------------------------------------
objective_value = n.objective

objective_df = pd.DataFrame({
    "year": [year],
    "objective_cost": [objective_value]
})

objective_file = output_summary.replace(".csv", "_objective.csv")
objective_df.to_csv(objective_file, index=False)

print(f"Objective cost saved: {objective_value}")

# -------------------------------------------------
# CAPACITY + COST TRACKING (NEW IMPLEMENTATION)
# -------------------------------------------------

# -----------------------------
# GENERATORS
# -----------------------------
gen_df = n.generators.copy()

gen_df["p_nom"] = gen_df["p_nom"].fillna(0)
gen_df["p_nom_opt"] = gen_df["p_nom_opt"].fillna(gen_df["p_nom"])

gen_df["delta_MW"] = (gen_df["p_nom_opt"] - gen_df["p_nom"]).clip(lower=0)

gen_df["capital_cost"] = gen_df["capital_cost"].fillna(0)

# total fleet cost (full system in that year)
gen_df["total_fleet_cost"] = gen_df["p_nom_opt"] * gen_df["capital_cost"]

# incremental expansion cost
gen_df["new_build_cost"] = gen_df["delta_MW"] * gen_df["capital_cost"]


# -----------------------------
# STORAGE
# -----------------------------
if not n.storage_units.empty:
    su_df = n.storage_units.copy()

    su_df["p_nom"] = su_df["p_nom"].fillna(0)
    su_df["p_nom_opt"] = su_df["p_nom_opt"].fillna(su_df["p_nom"])

    su_df["delta_MW"] = (su_df["p_nom_opt"] - su_df["p_nom"]).clip(lower=0)

    su_df["capital_cost"] = su_df["capital_cost"].fillna(0)

    su_df["total_fleet_cost"] = su_df["p_nom_opt"] * su_df["capital_cost"]
    su_df["new_build_cost"] = su_df["delta_MW"] * su_df["capital_cost"]

else:
    su_df = pd.DataFrame()


# -----------------------------
# TRANSMISSION
# -----------------------------
line_df = n.lines.copy()

line_df["s_nom"] = line_df["s_nom"].fillna(0)
line_df["s_nom_opt"] = line_df["s_nom_opt"].fillna(line_df["s_nom"])

line_df["delta_MVA"] = (line_df["s_nom_opt"] - line_df["s_nom"]).clip(lower=0)

line_df["capital_cost"] = line_df["capital_cost"].fillna(0)

# total line system cost
line_df["total_line_cost"] = line_df["s_nom_opt"] * line_df["capital_cost"]

# reinforcement only
line_df["reinforcement_cost"] = line_df["delta_MVA"] * line_df["capital_cost"]

# -------------------------------------------------
# GENERATOR ENERGY + COST SUMMARY
# -------------------------------------------------
dispatch = n.generators_t.p
energy_MWh = dispatch.sum()

mc = n.generators.marginal_cost.reindex(energy_MWh.index).fillna(0)
operating_cost = energy_MWh * mc

gen_summary = (
    pd.DataFrame({
        "carrier": n.generators.carrier,
        "energy_GWh": energy_MWh / 1e3,
        "operating_cost": operating_cost,
        "total_fleet_cost": gen_df["total_fleet_cost"],
        "new_build_cost": gen_df["new_build_cost"]
    })
    .groupby("carrier")
    .sum()
    .reset_index()
)

gen_summary["year"] = year


# -------------------------------------------------
# SYSTEM-LEVEL COST SUMMARY
# -------------------------------------------------
system_summary = pd.DataFrame({
    "year": [year],

    # generator costs
    "gen_total_fleet_cost": [gen_df["total_fleet_cost"].sum()],
    "gen_new_build_cost": [gen_df["new_build_cost"].sum()],

    # storage costs
    "storage_total_fleet_cost": [su_df["total_fleet_cost"].sum() if len(su_df) else 0],
    "storage_new_build_cost": [su_df["new_build_cost"].sum() if len(su_df) else 0],

    # transmission costs
    "transmission_total_cost": [line_df["total_line_cost"].sum()],
    "transmission_reinforcement_cost": [line_df["reinforcement_cost"].sum()],

    # operational cost
    "opex_total": [operating_cost.sum()]
})

gen_summary.to_csv(output_summary, index=False)
system_summary.to_csv(output_summary.replace(".csv", "_system.csv"), index=False)

# -------------------------------------------------
# SAVE DETAILED TABLES
# -------------------------------------------------
gen_df.to_csv(output_summary.replace(".csv", "_gen_detail.csv"))
line_df.to_csv(output_summary.replace(".csv", "_line_detail.csv"))

if len(su_df):
    su_df.to_csv(output_summary.replace(".csv", "_storage_detail.csv"))
# -------------------------------------------------
# SAVE SOLVED NETWORK
# -------------------------------------------------
os.makedirs(os.path.dirname(output_network), exist_ok=True)
n.export_to_netcdf(output_network)

print("Option B solve completed successfully")
