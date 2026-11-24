# Snakefile for PyPSA Lesotho

import os

configfile: "config.yaml"

# ----------------------------
# CONFIGURATION
# ----------------------------

DEMANDS   = ["BAU", "M300"]          # demand scenarios, each with its own output folders
SCENARIOS = ["A", "B"]               # model options
PLANNING_YEARS = config["years"]

# Supply-side load folder for each demand scenario
LOAD_DIRS = {
    "BAU":  "data/article/load_BAU_supply_end",
    "M300": "data/article/load_M300_supply_end",
}

# Renewable expansion ceiling sensitivities (Option B, BAU only)
#   RE25  -> solar and wind up to 1.25 x planned MW (25% ceiling)
#   NOCAP -> solar and wind can expand without limit (no ceiling)
# Option B itself (folder "B") keeps EXPANSION_FACTOR = 1.50 from assign_costs.py (50% ceiling)
RE_CASES   = {"RE25": 0.25, "NOCAP": float("inf")}
RE_DEMANDS = ["BAU"]

wildcard_constraints:
    demand   = "|".join(DEMANDS),
    scenario = "A|B",
    year     = r"\d{4}",
    re       = "|".join(RE_CASES)

# ----------------------------
# CREATE OUTPUT FOLDERS
# ----------------------------

for d in DEMANDS:
    for s in SCENARIOS:
        os.makedirs(f"networks/{d}/{s}", exist_ok=True)
        os.makedirs(f"results/{d}/{s}", exist_ok=True)

for d in RE_DEMANDS:
    for r in RE_CASES:
        os.makedirs(f"networks/{d}/B_{r}", exist_ok=True)
        os.makedirs(f"results/{d}/B_{r}", exist_ok=True)

# ----------------------------
# RULE: ALL (both demand scenarios, both options)
# ----------------------------

rule all:
    input:
        expand(
            "results/{demand}/{scenario}/summary_{year}.csv",
            demand=DEMANDS,
            scenario=SCENARIOS,
            year=PLANNING_YEARS
        )

# One demand scenario at a time:  snakemake -j 8 all_BAU   or   snakemake -j 8 all_M300
rule all_BAU:
    input:
        expand("results/BAU/{scenario}/summary_{year}.csv",
               scenario=SCENARIOS, year=PLANNING_YEARS)

rule all_M300:
    input:
        expand("results/M300/{scenario}/summary_{year}.csv",
               scenario=SCENARIOS, year=PLANNING_YEARS)

# One option at a time, for both demands:  snakemake -j 8 all_A   or   snakemake -j 8 all_B
rule all_A:
    input:
        expand("results/{demand}/A/summary_{year}.csv",
               demand=DEMANDS, year=PLANNING_YEARS)

rule all_B:
    input:
        expand("results/{demand}/B/summary_{year}.csv",
               demand=DEMANDS, year=PLANNING_YEARS)

# Renewable ceiling runs, BAU only:  snakemake -j 8 all_RE   (or all_RE25 / all_NOCAP)
rule all_RE:
    input:
        expand("results/{demand}/B_{re}/summary_{year}.csv",
               demand=RE_DEMANDS, re=list(RE_CASES), year=PLANNING_YEARS)

rule all_RE25:
    input:
        expand("results/{demand}/B_RE25/summary_{year}.csv",
               demand=RE_DEMANDS, year=PLANNING_YEARS)

rule all_NOCAP:
    input:
        expand("results/{demand}/B_NOCAP/summary_{year}.csv",
               demand=RE_DEMANDS, year=PLANNING_YEARS)

# ----------------------------
# BUILD BASE NETWORK
# ----------------------------

rule build_network:
    input:
        buses      = "data/planned/m300/buses.xlsx",
        lines      = "data/planned/m300/lines.xlsx",
        generators = "data/planned/m300/generators.xlsx",
        storage    = "data/planned/m300/storage_units.xlsx",
        loads      = lambda wc: f"{LOAD_DIRS[wc.demand]}/load_timeseries_{wc.year}_supply_end.xlsx"
    output:
        network = "networks/{demand}/{scenario}/network_{year}.nc"
    script:
        "scripts/build_network.py"

# ----------------------------
# ADD GENERATOR PROFILES
# ----------------------------

rule add_profiles:
    input:
        network = "networks/{demand}/{scenario}/network_{year}.nc",
        solar   = "data/planned/m300/profiles/solar_ready/solar_p_max_pu_{year}.csv",
        wind    = "data/planned/m300/profiles/wind_ready/wind_p_max_pu_{year}.csv",
        hydro   = "data/planned/m300/profiles/hydro_ready/hydro_p_max_pu_{year}.csv"
    output:
        network = "networks/{demand}/{scenario}/profiled_{year}.nc"
    script:
        "scripts/add_profiles.py"

# ----------------------------
# Assign costs for option B
# ----------------------------

rule assign_costs_B:
    input:
        network = "networks/{demand}/B/profiled_{year}.nc"
    output:
        network = "networks/{demand}/B/costed_{year}.nc"
    script:
        "scripts/assign_costs.py"

# ----------------------------
# SOLVE OPTION A
# Dispatch only, fixed capacities
# ----------------------------

rule solve_option_A:
    input:
        network = "networks/{demand}/A/profiled_{year}.nc",
        costs   = "data/planned/m300/costs.xlsx"
    output:
        network = "networks/{demand}/A/solved_{year}.nc",
        summary = "results/{demand}/A/summary_{year}.csv"
    script:
        "scripts/solve_option_A.py"

# ----------------------------
# SOLVE OPTION B
# Expansion + reserve margin
# ----------------------------

rule solve_option_B:
    input:
        network = "networks/{demand}/B/costed_{year}.nc"
    output:
        network = "networks/{demand}/B/solved_{year}.nc",
        summary = "results/{demand}/B/summary_{year}.csv"
    script:
        "scripts/solve_option_B.py"

# ----------------------------
# OPTION B WITH RENEWABLE EXPANSION CEILING
# Starts from the same costed network as Option B, replaces the solar/wind
# p_nom_max (1.25 x planned for RE25, unlimited for NOCAP),
# then solves with the same solve_option_B.py
# ----------------------------

rule apply_re_ceiling:
    input:
        network = "networks/{demand}/B/costed_{year}.nc"
    output:
        network = "networks/{demand}/B_{re}/costed_{year}.nc"
    params:
        ceiling = lambda wc: RE_CASES[wc.re]
    script:
        "scripts/apply_re_ceiling.py"

rule solve_option_B_re:
    input:
        network = "networks/{demand}/B_{re}/costed_{year}.nc"
    output:
        network = "networks/{demand}/B_{re}/solved_{year}.nc",
        summary = "results/{demand}/B_{re}/summary_{year}.csv"
    script:
        "scripts/solve_option_B.py"
