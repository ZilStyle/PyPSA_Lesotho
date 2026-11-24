import pypsa
import pandas as pd
import geopandas as gpd
import holoviews as hv
import geoviews as gv
from shapely.geometry import Point, LineString
import cartopy.crs as ccrs

hv.extension("bokeh")

# -------------------------------------------------
# LOAD NETWORK (STATUS QUO 2024)
# -------------------------------------------------

network = pypsa.Network("results/base/network_2024_status_quo.nc")
print("Loaded network with", len(network.buses), "buses")

# -------------------------------------------------
# BUSES → GeoDataFrame
# -------------------------------------------------

bus_df = (
    network.buses
    .copy()
    .reset_index()
    .rename(columns={"index": "bus_name"})
)

bus_df["geometry"] = [Point(xy) for xy in zip(bus_df.x, bus_df.y)]
bus_gdf = gpd.GeoDataFrame(bus_df, geometry="geometry", crs="EPSG:4326")

# -------------------------------------------------
# LINES → GeoDataFrame (ALL EXISTING)
# -------------------------------------------------

line_rows = []

for name, line in network.lines.iterrows():
    b0 = network.buses.loc[line.bus0]
    b1 = network.buses.loc[line.bus1]

    geom = LineString([(b0.x, b0.y), (b1.x, b1.y)])

    num_parallel = int(line.num_parallel) if "num_parallel" in line and pd.notna(line.num_parallel) else 1
    line_width = 2 * num_parallel

    line_rows.append({
        "name": name,
        "line_width": line_width,
        "v_nom": line.v_nom,
        "geometry": geom
    })

line_gdf = gpd.GeoDataFrame(line_rows, geometry="geometry", crs="EPSG:4326")

# -------------------------------------------------
# GENERATORS → GeoDataFrame (ALL EXISTING)
# -------------------------------------------------

gen_rows = []

for name, gen in network.generators.iterrows():
    bus = network.buses.loc[gen.bus]
    geom = Point(bus.x, bus.y)

    gen_rows.append({
        "name": name,
        "carrier": gen.carrier,
        "p_nom": gen.p_nom,
        "geometry": geom
    })

gen_gdf = gpd.GeoDataFrame(gen_rows, geometry="geometry", crs="EPSG:4326")

print("Generator carriers present:", gen_gdf.carrier.unique())

# -------------------------------------------------
# SYMBOL AND COLOR MAPS
# -------------------------------------------------

icon_map = {
    "solar": "triangle",
    "hydro": "circle",
    "imports": "square"
}

color_map = {
    "solar": "#fae70f",
    "hydro": "#440dfa",
    "imports": "#069832"
}

# -------------------------------------------------
# BASE MAP
# -------------------------------------------------

tiles = gv.tile_sources.OSM.options(
    width=900,
    height=700,
    alpha=0.9
)

# -------------------------------------------------
# LINE PLOT
# -------------------------------------------------

line_plot = gv.Path(line_gdf, label="Transmission Lines").opts(
    projection=ccrs.GOOGLE_MERCATOR,
    color="black",
    line_width="line_width",
    tools=["hover"],
    show_legend=True
)

# -------------------------------------------------
# BUS PLOT
# -------------------------------------------------

bus_plot = gv.Points(bus_gdf, label="Buses").opts(
    projection=ccrs.GOOGLE_MERCATOR,
    size=7,
    color="grey",
    alpha=0.7,
    tools=["hover"],
    show_legend=True
)

# -------------------------------------------------
# GENERATOR PLOTS (ROBUST FOR FEW GENERATORS)
# -------------------------------------------------

gen_layers = []

for carrier in sorted(gen_gdf.carrier.unique()):
    subset = gen_gdf[gen_gdf.carrier == carrier]

    if subset.empty:
        continue

    gen_layers.append(
        gv.Points(subset, label=carrier.capitalize()).opts(
            projection=ccrs.GOOGLE_MERCATOR,
            size=14,
            marker=icon_map.get(carrier, "diamond"),
            color=color_map.get(carrier, "purple"),
            tools=["hover"],
            show_legend=True
        )
    )

generator_layer = None
for layer in gen_layers:
    generator_layer = layer if generator_layer is None else generator_layer * layer

# -------------------------------------------------
# FINAL MAP (SAFE OVERLAY)
# -------------------------------------------------

final_map = tiles * line_plot * bus_plot

if generator_layer is not None:
    final_map = final_map * generator_layer

final_map = final_map.opts(
    legend_position="right",
    title="Status Quo Transmission and Generation Network (2024)"
)

# -------------------------------------------------
# SAVE
# -------------------------------------------------

output_file = "results/base/interactive_network_map_2024_status_quo.html"
hv.save(final_map, output_file)
print(f"Saved map to {output_file}")
