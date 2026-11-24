import os
import pypsa
import pandas as pd
import geopandas as gpd
import holoviews as hv
import geoviews as gv
from shapely.geometry import Point, LineString
import cartopy.crs as ccrs
import numpy as np

hv.extension("bokeh")

# -------------------------------------------------
# SETTINGS
# -------------------------------------------------
DEMANDS = ["BAU"]                    # demand scenarios to map (add "M300" to include it)
OPTIONS = ["B_RE25", "B_NOCAP"]      # add "B" for the 50% ceiling run
YEAR    = 2050

OPTION_LABELS = {
    "B":       "Option B, 50% RE ceiling",
    "B_RE25":  "Option B, 25% RE ceiling",
    "B_NOCAP": "Option B, no RE ceiling",
}

# Optional extra tag for the output names (e.g. "50pct_ceiling_no_battery_cap"); "" for none
SCENARIO_TAG = ""

SKIP_CARRIERS = ["load_shedding", "export"]   # not physical plants, left off the map
MIN_MW = 0.1                                  # hide plants/batteries the model built at ~0 MW

# -------------------------------------------------
# SYMBOLS
# -------------------------------------------------
icon_map = {
    "solar": "triangle",
    "hydro": "circle",
    "hydro_peaking": "circle",
    "imports": "square",
    "wind": "diamond",
    "battery": "star",
}

color_map = {
    "solar": "#fae70f",
    "hydro": "#440dfa",
    "hydro_peaking": "#00bfff",
    "imports": "#069832",
    "wind": "#00bcd4",
    "battery": "black",
}


def capacity(df, nom, nom_opt):
    """Optimised capacity after the solve, falling back to the input value."""
    if nom_opt in df.columns:
        return df[nom_opt].where(df[nom_opt].notna(), df[nom])
    return df[nom]


def make_map(demand, OPTION):
    network_path = f"networks/{demand}/{OPTION}/solved_{YEAR}.nc"
    out_dir = f"results/{demand}/{OPTION}/network_map"

    if not os.path.exists(network_path):
        print(f"{demand}: {network_path} not found, skipped")
        return
    os.makedirs(out_dir, exist_ok=True)

    label = f"{demand}_{OPTION}_{YEAR}" + (f"_{SCENARIO_TAG}" if SCENARIO_TAG else "")

    # -------------------------------------------------
    # LOAD NETWORK
    # -------------------------------------------------
    network = pypsa.Network(network_path)
    print(f"\n=== {demand} | {OPTION_LABELS.get(OPTION, OPTION)} | {YEAR} ===")
    print("Loaded network with", len(network.buses), "buses")

    # -------------------------------------------------
    # BUSES
    # -------------------------------------------------
    bus_df = network.buses.reset_index().rename(columns={"index": "bus_name", "Bus": "bus_name"})
    bus_df["geometry"] = [Point(xy) for xy in zip(bus_df.x, bus_df.y)]
    bus_gdf = gpd.GeoDataFrame(bus_df[["bus_name", "v_nom", "geometry"]],
                               geometry="geometry", crs="EPSG:4326")

    # -------------------------------------------------
    # LINE LOADING TIME SERIES (FULL YEAR)
    # -------------------------------------------------
    lines = network.lines
    s_nom_opt_all = capacity(lines, "s_nom", "s_nom_opt")

    loading = None
    loading_ts = None
    weights = None

    if hasattr(network, "lines_t") and not network.lines_t.p0.empty:
        p0 = network.lines_t.p0.abs()
        loading_ts = p0.div(s_nom_opt_all, axis=1)       # LF(l,t) for every line, every snapshot
        loading = loading_ts.max().fillna(0)             # peak loading per line

        if "objective" in network.snapshot_weightings:
            weights = network.snapshot_weightings.objective
        else:
            weights = pd.Series(1.0, index=network.snapshots)

    # -------------------------------------------------
    # LINES (STYLING)
    # -------------------------------------------------
    line_rows = []

    for name, line in lines.iterrows():
        b0 = network.buses.loc[line.bus0]
        b1 = network.buses.loc[line.bus1]
        x0, y0 = b0.x, b0.y
        x1, y1 = b1.x, b1.y

        s_nom = line.s_nom if pd.notna(line.s_nom) else 0.0
        s_opt = s_nom_opt_all[name]
        expanded = pd.notna(s_opt) and s_opt > s_nom + 1e-3

        load_val = loading[name] if loading is not None else 0.0

        if expanded:
            color = "red"
        elif load_val >= 0.8:
            color = "green"
        elif load_val >= 0.6:
            color = "blue"
        else:
            color = "black"

        num_parallel = int(line.num_parallel) if pd.notna(line.num_parallel) else 1

        common = {
            "name": name,
            "v_nom": line.v_nom,
            "loading_pct": round(load_val * 100, 1),
            "s_nom_MVA": round(s_nom, 1),
            "s_nom_opt_MVA": round(s_opt, 1),
            "color": color,
        }

        if num_parallel > 1:
            dx, dy = x1 - x0, y1 - y0
            length = np.sqrt(dx**2 + dy**2) or 1.0
            offset = 0.02
            ox, oy = -dy / length * offset, dx / length * offset
            for geom in [LineString([(x0 + ox, y0 + oy), (x1 + ox, y1 + oy)]),
                         LineString([(x0 - ox, y0 - oy), (x1 - ox, y1 - oy)])]:
                line_rows.append({**common, "geometry": geom})
        else:
            line_rows.append({**common, "geometry": LineString([(x0, y0), (x1, y1)])})

    line_gdf = gpd.GeoDataFrame(line_rows, geometry="geometry", crs="EPSG:4326")

    # -------------------------------------------------
    # LINE LOADING-DURATION TABLE (PRINT + SAVE)
    # -------------------------------------------------
    if loading_ts is not None:
        total_hours = weights.sum()
        loading_table = []

        for name, line in lines.iterrows():
            s_nom = line.s_nom if pd.notna(line.s_nom) else 0.0
            s_opt = s_nom_opt_all[name]
            lf = loading_ts[name]

            max_loading_pct  = lf.max() * 100
            mean_loading_pct = (lf.mul(weights).sum() / total_hours) * 100
            hrs_gt_90  = lf.gt(0.90).mul(weights).sum()
            hrs_gt_95  = lf.gt(0.95).mul(weights).sum()
            hrs_gt_100 = lf.gt(1.00).mul(weights).sum()

            if max_loading_pct >= 80:
                status = "Critical"
            elif max_loading_pct >= 60:
                status = "Major"
            else:
                status = "Normal"

            loading_table.append({
                "demand": demand,
                "option": OPTION,
                "year": YEAR,
                "line": name,
                "bus0": line.bus0,
                "bus1": line.bus1,
                "v_nom_kV": line.v_nom,
                "s_nom_MVA": round(s_nom, 2),
                "s_nom_opt_MVA": round(s_opt, 2),
                "expanded": bool(s_opt > s_nom + 1e-3),
                "max_loading_pct": round(max_loading_pct, 2),
                "mean_loading_pct": round(mean_loading_pct, 2),
                "hours_gt_90pct": round(hrs_gt_90, 1),
                "hours_gt_95pct": round(hrs_gt_95, 1),
                "hours_gt_100pct": round(hrs_gt_100, 1),
                "pct_of_year_gt_90pct": round(100 * hrs_gt_90 / total_hours, 2),
                "pct_of_year_gt_95pct": round(100 * hrs_gt_95 / total_hours, 2),
                "pct_of_year_gt_100pct": round(100 * hrs_gt_100 / total_hours, 2),
                "status": status,
            })

        loading_df = pd.DataFrame(loading_table).sort_values("max_loading_pct", ascending=False)

        print("\n================ LINE LOADING-DURATION SUMMARY ================\n")
        print(loading_df.to_string(index=False))

        out_csv = f"{out_dir}/line_loading_duration_{label}.csv"
        loading_df.to_csv(out_csv, index=False)
        print(f"\nSaved loading-duration table to {out_csv}\n")
    else:
        print("No line flow time series found, loading table skipped.")

    # -------------------------------------------------
    # GENERATORS (optimised capacity, no load shedding / export sink)
    # -------------------------------------------------
    gens = network.generators
    gen_cap = capacity(gens, "p_nom", "p_nom_opt")

    gen_rows = []
    for name, gen in gens.iterrows():
        if gen.carrier in SKIP_CARRIERS or gen_cap[name] < MIN_MW:
            continue
        bus = network.buses.loc[gen.bus]
        gen_rows.append({
            "name": name,
            "carrier": gen.carrier,
            "p_nom_MW": round(gen.p_nom, 1),
            "p_nom_opt_MW": round(gen_cap[name], 1),
            "geometry": Point(bus.x, bus.y),
        })
    gen_gdf = gpd.GeoDataFrame(gen_rows, geometry="geometry", crs="EPSG:4326")

    # -------------------------------------------------
    # STORAGE (optimised capacity)
    # -------------------------------------------------
    storage_rows = []
    su = network.storage_units
    if not su.empty:
        su_cap = capacity(su, "p_nom", "p_nom_opt")
        for name, s in su.iterrows():
            if su_cap[name] < MIN_MW:
                continue
            bus = network.buses.loc[s.bus]
            storage_rows.append({
                "name": name,
                "carrier": "battery",
                "p_nom_MW": round(s.p_nom, 1),
                "p_nom_opt_MW": round(su_cap[name], 1),
                "MWh": round(su_cap[name] * s.max_hours, 1),
                "geometry": Point(bus.x, bus.y),
            })
    storage_gdf = gpd.GeoDataFrame(storage_rows, geometry="geometry", crs="EPSG:4326")

    # -------------------------------------------------
    # BASE MAP
    # -------------------------------------------------
    tiles = gv.tile_sources.EsriWorldStreetMap.options(width=900, height=700, alpha=0.9)

    # -------------------------------------------------
    # LINE LAYERS (one per category, for a clean legend)
    # -------------------------------------------------
    line_layers = []
    for colour, lab in [("red",   "Expansion (Reinforced)"),
                        ("green", "Critical (80% or more)"),
                        ("blue",  "Major (60% to 79%)"),
                        ("black", "Normal (below 60%)")]:
        sub = line_gdf[line_gdf["color"] == colour]
        if sub.empty:
            continue
        line_layers.append(
            gv.Path(sub, label=lab).opts(color=colour, line_width=2,
                                          show_legend=True, tools=["hover"])
        )

    bus_plot = gv.Points(bus_gdf).opts(
        projection=ccrs.GOOGLE_MERCATOR, size=6, color="grey", alpha=0.7, tools=["hover"]
    )

    layers = tiles
    for lyr in line_layers:
        layers = layers * lyr
    layers = layers * bus_plot

    # -------------------------------------------------
    # GENERATOR LAYERS
    # -------------------------------------------------
    if not gen_gdf.empty:
        for carrier in sorted(gen_gdf.carrier.unique()):
            subset = gen_gdf[gen_gdf.carrier == carrier]
            layers = layers * gv.Points(subset, label=carrier.replace("_", " ").capitalize()).opts(
                projection=ccrs.GOOGLE_MERCATOR,
                size=12,
                marker=icon_map.get(carrier, "circle"),
                color=color_map.get(carrier, "purple"),
                show_legend=True,
                tools=["hover"],
            )

    # -------------------------------------------------
    # STORAGE LAYER
    # -------------------------------------------------
    if not storage_gdf.empty:
        layers = layers * gv.Points(storage_gdf, label="Battery").opts(
            projection=ccrs.GOOGLE_MERCATOR, size=14, marker="star",
            color="black", show_legend=True, tools=["hover"],
        )

    # -------------------------------------------------
    # FINAL MAP
    # -------------------------------------------------
    final_map = layers.opts(
        legend_position="right",
        title=f"Transmission Expansion, Generation and Storage Network ({YEAR}): "
              f"{demand} demand, {OPTION_LABELS.get(OPTION, OPTION)}",
    )

    out_html = f"{out_dir}/interactive_network_map_{label}.html"
    hv.save(final_map, out_html)
    print(f"Saved map to {out_html}")


# -------------------------------------------------
# RUN FOR EVERY DEMAND AND OPTION
# -------------------------------------------------
for demand in DEMANDS:
    for option in OPTIONS:
        make_map(demand, option)

print("\nDone.")