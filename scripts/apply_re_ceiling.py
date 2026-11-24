"""
Apply a renewable expansion ceiling to an Option B (costed) network.

ceiling = 0.25 -> solar and wind can grow to at most 1.25 x their planned p_nom (25% ceiling)
ceiling = inf  -> solar and wind can expand without limit (no ceiling)

This REPLACES the 1.50 x ceiling set by assign_costs.py (EXPANSION_FACTOR) for these runs.
Only solar and wind that assign_costs.py already made extendable are changed, so:
  - plants with planned p_nom = 0 stay at 0 (no speculative build, as in assign_costs.py)
  - nothing expands before EXPANSION_START_YEAR (2027), as in assign_costs.py
Batteries, lines, hydro and imports keep the Option B settings.
"""
import numpy as np
import pypsa

network_in  = snakemake.input.network
network_out = snakemake.output.network
ceiling     = float(snakemake.params.ceiling)      # 0.25 or inf
year        = int(snakemake.wildcards.year)

RE_CARRIERS = ["solar", "wind"]

n = pypsa.Network(network_in)
g = n.generators
re_idx = g.index[g.carrier.isin(RE_CARRIERS)]

label = "no ceiling" if np.isinf(ceiling) else f"{ceiling:.0%} ceiling"
print(f"[RE ceiling] year {year}: {label} on {RE_CARRIERS} ({len(re_idx)} generators)")

for gen in re_idx:
    if bool(g.at[gen, "p_nom_extendable"]):
        p_nom = float(g.at[gen, "p_nom"])
        n.generators.at[gen, "p_nom_min"] = p_nom                       # no shrinking below planned
        n.generators.at[gen, "p_nom_max"] = np.inf if np.isinf(ceiling) else p_nom * (1.0 + ceiling)
    # non-extendable (p_nom = 0 candidates, or years before 2027) stay as assign_costs.py set them

    gg = n.generators.loc[gen]
    print(f"  {gen:<25} {gg.carrier:<6} p_nom {gg.p_nom:7.1f}  "
          f"max {gg.p_nom_max:>9.1f}  extendable {bool(gg.p_nom_extendable)}")

n.export_to_netcdf(network_out)
print(f"[RE ceiling] saved {network_out}")