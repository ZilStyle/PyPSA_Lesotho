import pypsa
import pandas as pd
import geopandas as gpd
import holoviews as hv
import geoviews as gv
from shapely.geometry import Point, LineString
import cartopy.crs as ccrs

hv.extension("bokeh")

# -------------------------------------------------
# LOAD NETWORK
# -------------------------------------------------

network = pypsa.Network("networks/A/network_2050.nc")
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
# LINES → GeoDataFrame
# -------------------------------------------------

line_rows = []

for name, line in network.lines.iterrows():
    b0 = network.buses.loc[line.bus0]
    b1 = network.buses.loc[line.bus1]

    geom = LineString([(b0.x, b0.y), (b1.x, b1.y)])

    num_parallel = int(line.num_parallel) if pd.notna(line.num_parallel) else 1
    line_width = 2 * num_parallel

    status = line.line_status if "line_status" in network.lines.columns else "existing"

    line_rows.append({
        "name": name,
        "line_status": status,
        "line_width": line_width,
        "v_nom": line.v_nom,
        "geometry": geom
    })

line_gdf = gpd.GeoDataFrame(line_rows, geometry="geometry", crs="EPSG:4326")

existing_lines = line_gdf[line_gdf.line_status == "existing"]
planned_lines  = line_gdf[line_gdf.line_status == "planned"]

# -------------------------------------------------
# GENERATORS → GeoDataFrame
# -------------------------------------------------

gen_rows = []

for name, gen in network.generators.iterrows():
    bus = network.buses.loc[gen.bus]
    geom = Point(bus.x, bus.y)

    status = gen.plant_status if "plant_status" in network.generators.columns else "existing"

    gen_rows.append({
        "name": name,
        "carrier": gen.carrier,
        "p_nom": gen.p_nom,
        "plant_status": status,
        "geometry": geom
    })

gen_gdf = gpd.GeoDataFrame(gen_rows, geometry="geometry", crs="EPSG:4326")

existing_plant = gen_gdf[gen_gdf.plant_status == "existing"]
planned_plant  = gen_gdf[gen_gdf.plant_status == "planned"]

# -------------------------------------------------
# STORAGE UNITS → GeoDataFrame
# -------------------------------------------------

storage_rows = []

if hasattr(network, "storage_units") and not network.storage_units.empty:
    for name, su in network.storage_units.iterrows():
        bus = network.buses.loc[su.bus]
        geom = Point(bus.x, bus.y)

        storage_rows.append({
            "name": name,
            "carrier": su.carrier if "carrier" in su else "battery",
            "p_nom": su.p_nom,
            "geometry": geom
        })

storage_gdf = gpd.GeoDataFrame(storage_rows, geometry="geometry", crs="EPSG:4326")


# -------------------------------------------------
# SYMBOL AND COLOR MAPS
# -------------------------------------------------

icon_map = {
    "solar": "triangle",
    "hydro": "circle",
    "imports": "square",
    "battery": "rect"   # rectangle for battery
}

color_map = {
    "solar": "#fae70f",
    "hydro": "#440dfa",
    "imports": "#069832",
    "battery": "black"
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
# LINE PLOTS
# -------------------------------------------------

existing_line_plot = gv.Path(existing_lines, label="Existing Lines").opts(
    projection=ccrs.GOOGLE_MERCATOR,
    color="black",
    line_width="line_width",
    tools=["hover"],
    show_legend=True
)

planned_line_plot = gv.Path(planned_lines, label="Planned Lines").opts(
    projection=ccrs.GOOGLE_MERCATOR,
    color="brown",
    line_width="line_width",
    line_dash="dashed",
    tools=["hover"],
    show_legend=True
)

# -------------------------------------------------
# BUS PLOT
# -------------------------------------------------

bus_plot = gv.Points(bus_gdf, label="Bus").opts(
    projection=ccrs.GOOGLE_MERCATOR,
    size=7,
    color="grey",
    alpha=0.7,
    tools=["hover"],
    show_legend=True
)

# -------------------------------------------------
# GENERATOR PLOTS
# -------------------------------------------------

gen_layers = []

for carrier in sorted(gen_gdf.carrier.unique()):
    subset = gen_gdf[gen_gdf.carrier == carrier]

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

generator_layer = gen_layers[0]
for layer in gen_layers[1:]:
    generator_layer *= layer

# -------------------------------------------------
# STORAGE PLOT (BATTERY)
# -------------------------------------------------

storage_layer = None

if not storage_gdf.empty:
    storage_layer = gv.Points(
        storage_gdf,
        label="Battery"
    ).opts(
        projection=ccrs.GOOGLE_MERCATOR,
        size=16,
        marker="star",     # rectangle/square
        color="black",
        tools=["hover"],
        show_legend=True
    )


# -------------------------------------------------
# FINAL MAP
# -------------------------------------------------
layers = (
    tiles
    * existing_line_plot
    * planned_line_plot
    * bus_plot
    * generator_layer
)

if storage_layer is not None:
    layers = layers * storage_layer

final_map = layers.opts(
    legend_position="right",
    title="Planned Transmission, Generation and Storage Network (2050)"
)


hv.save(final_map, "results/planned/interactive_network_map_2050.html")
print("Saved map to results/planned/interactive_network_map_2050.html")
