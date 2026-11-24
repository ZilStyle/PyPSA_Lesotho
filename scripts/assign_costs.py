import pypsa
import pandas as pd
import numpy as np

import os

# --------------------------------------------------
# LOAD PROCESSED COST TABLES
# --------------------------------------------------

GEN_COSTS = pd.read_csv("data/planned/processed_costs/generators_costs.csv")
STO_COSTS = pd.read_csv("data/planned/processed_costs/storage_costs.csv")
TX_COSTS  = pd.read_csv("data/planned/processed_costs/transmission_costs.csv")

EXPANSION_FACTOR = 1.50   # 50% / 25% rule
#EXPANSION_FACTOR = np.inf # No ceiling

# Expansion is only allowed from this year onward (Option B)
EXPANSION_START_YEAR = 2027


# --------------------------------------------------
# GENERATORS (INCLUDING IMPORTS)
# --------------------------------------------------

def assign_generator_costs(n, year):

    costs = GEN_COSTS[GEN_COSTS["year"] == year]
    assert not costs.empty, f"No generator costs found for year {year}"

    for gen in n.generators.index:

        carrier = n.generators.at[gen, "carrier"]
        p_committed = n.generators.at[gen, "p_nom"]

        row = costs[costs["Carrier"] == carrier]
        if row.empty:
            continue

        row = row.iloc[0]

        # Assign economic parameters
        n.generators.at[gen, "capital_cost"]  = row["capital_cost"]
        n.generators.at[gen, "marginal_cost"] = row["marginal_cost"]
        n.generators.at[gen, "efficiency"]    = row["Efficiency"]

        # --------------------------------------------------
        # EXPANSION LOGIC
        # --------------------------------------------------

        # Imports: fixed, no expansion
        if carrier == "imports":
            n.generators.at[gen, "p_nom_extendable"] = False
            n.generators.at[gen, "capital_cost"] = 0.0
            n.generators.at[gen, "p_nom_min"] = p_committed
            n.generators.at[gen, "p_nom_max"] = p_committed
            continue

        # Hydro: fixed at committed capacity
        if carrier == "hydro":
            n.generators.at[gen, "p_nom_extendable"] = False
            n.generators.at[gen, "p_nom_min"] = p_committed
            n.generators.at[gen, "p_nom_max"] = p_committed
            continue

        # Solar and wind: expansion rule
        if carrier in ["solar", "wind"]:

            if p_committed > 0:
                n.generators.at[gen, "p_nom_extendable"] = True
                n.generators.at[gen, "p_nom_min"] = p_committed
                n.generators.at[gen, "p_nom_max"] = EXPANSION_FACTOR * p_committed
            else:
                # No committed capacity yet, do not allow speculative build
                n.generators.at[gen, "p_nom_extendable"] = False
                n.generators.at[gen, "p_nom_min"] = 0.0
                n.generators.at[gen, "p_nom_max"] = 0.0

        # Default fallback, fixed capacity
        else:
            n.generators.at[gen, "p_nom_extendable"] = False
            n.generators.at[gen, "p_nom_min"] = p_committed
            n.generators.at[gen, "p_nom_max"] = p_committed


# --------------------------------------------------
# STORAGE UNITS (OPTION B CONSISTENT)
# --------------------------------------------------

def assign_storage_costs(n, year):

    costs = STO_COSTS[STO_COSTS["year"] == year]
    assert not costs.empty, f"No storage costs found for year {year}"

    for su in n.storage_units.index:

        carrier = n.storage_units.at[su, "carrier"]
        p_nom = float(n.storage_units.at[su, "p_nom"])

        row = costs[costs["Carrier"] == carrier]
        if row.empty:
            continue
        row = row.iloc[0]

        # -----------------------------
        # TECHNO-ECONOMIC PARAMETERS
        # -----------------------------
        n.storage_units.at[su, "capital_cost"] = row["capital_cost"]

        if not pd.isna(row["max_hours"]):
            n.storage_units.at[su, "max_hours"] = row["max_hours"]

        n.storage_units.at[su, "efficiency_store"]    = row["efficiency_store"]
        n.storage_units.at[su, "efficiency_dispatch"] = row["efficiency_dispatch"]

        # -----------------------------
        # COMMITTED STORAGE (FIXED)
        # -----------------------------
        if p_nom > 0:
            # committed storage must NOT expand
            n.storage_units.at[su, "p_nom_extendable"] = False
            n.storage_units.at[su, "p_nom_min"] = p_nom
            n.storage_units.at[su, "p_nom_max"] = p_nom
            continue

        # -----------------------------
        # CANDIDATE STORAGE (EXPANDABLE)
        # -----------------------------
        n.storage_units.at[su, "p_nom_extendable"] = True
        n.storage_units.at[su, "p_nom_min"] = 0.0

        bus = n.storage_units.at[su, "bus"]

        # cumulative committed VRE at this bus
        vre = n.generators[
            (n.generators.bus == bus) &
            (n.generators.carrier.isin(["solar", "wind"])) &
            (n.generators.p_nom > 0)
        ]

        total_vre_capacity = vre["p_nom"].sum()

        # already committed storage at this bus
        committed_storage = n.storage_units[
            (n.storage_units.bus == bus) &
            (n.storage_units.p_nom > 0)
        ]["p_nom"].sum()

        # 50% rule (disabled for sensitivity test)
        #max_storage_allowed = 0.5 * total_vre_capacity
        #candidate_cap = max(0.0, max_storage_allowed - committed_storage)

        #n.storage_units.at[su, "p_nom_max"] = candidate_cap
        n.storage_units.at[su, "p_nom_max"] = np.inf


# --------------------------------------------------
# TRANSMISSION LINES
# --------------------------------------------------

def assign_transmission_costs(n, year):

    costs = TX_COSTS[TX_COSTS["year"] == year]
    assert len(costs) == 1, (
        f"Expected exactly one transmission cost row for year {year}, "
        f"found {len(costs)}"
    )

    row = costs.iloc[0]

    inv_MWkm = row["Investment_usd_per_MW_km"]
    fom_pct  = row["FOM_percent_per_year"]
    ann      = row["annuity_factor"]

    for line in n.lines.index:

        length_km = n.lines.at[line, "length"]

        capex = inv_MWkm * length_km
        fom_abs = capex * fom_pct / 100

        n.lines.at[line, "capital_cost"] = capex * ann + fom_abs

        # Transmission is extendible
        n.lines.at[line, "s_nom_extendable"] = True
        n.lines.at[line, "s_nom_min"] = n.lines.at[line, "s_nom"]


# --------------------------------------------------
# EXPANSION START YEAR
# --------------------------------------------------

def freeze_expansion_before_start(n, year):
    """Before EXPANSION_START_YEAR only committed capacity exists: nothing is extendable."""
    if year >= EXPANSION_START_YEAR:
        return

    n.generators["p_nom_extendable"] = False
    n.generators["p_nom_min"] = n.generators["p_nom"]
    n.generators["p_nom_max"] = n.generators["p_nom"]

    n.storage_units["p_nom_extendable"] = False
    n.storage_units["p_nom_min"] = n.storage_units["p_nom"]
    n.storage_units["p_nom_max"] = n.storage_units["p_nom"]

    # Delete these three lines if line upgrades should stay allowed before 2027
    n.lines["s_nom_extendable"] = False
    n.lines["s_nom_min"] = n.lines["s_nom"]
    n.lines["s_nom_max"] = n.lines["s_nom"]


network_in  = snakemake.input.network
network_out = snakemake.output.network
year = int(snakemake.wildcards.year)

n = pypsa.Network(network_in)

assign_generator_costs(n, year)
assign_storage_costs(n, year)
assign_transmission_costs(n, year)
freeze_expansion_before_start(n, year)   # must stay last

os.makedirs(os.path.dirname(network_out), exist_ok=True)
n.export_to_netcdf(network_out)

print(f"Assigned Option B costs and bounds for year {year}: {network_out}")