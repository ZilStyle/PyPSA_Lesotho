import pypsa
import numpy as np
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature
from cartopy.mpl.gridliner import LONGITUDE_FORMATTER, LATITUDE_FORMATTER
import cartopy.io.shapereader as shpreader
import matplotlib.patches as mpatches
from matplotlib.lines import Line2D
from matplotlib.collections import PathCollection
from matplotlib.widgets import Button, RangeSlider
from matplotlib.path import Path
import matplotlib.patches as patches
from shapely.geometry import Point, LineString

# -------------------------
# Paths to your GADM shapefiles (edit if needed)
# -------------------------
gadm0_path = r"C:\Users\Mothala\Downloads\gadm41_LSO_shp (3)\gadm41_LSO_0.shp"
gadm1_path = r"C:\Users\Mothala\Downloads\gadm41_LSO_shp (3)\gadm41_LSO_1.shp"


# -------------------------
# Read GADM and ensure CRS is WGS84 (EPSG:4326)
# -------------------------
gadm_lso = gpd.read_file(gadm0_path).to_crs(epsg=4326)
gadm_dis = gpd.read_file(gadm1_path).to_crs(epsg=4326)

#----------------------
# Create a new PyPSA network
#----------------------
network = pypsa.Network()

# --- style dictionaries (kept from your script) ---

voltage_colors = {
    132.0: '#FF6B6B',  # Red for 132kV
    88.0: '#505050',   # grey for 88kV  
    66.0: '#45B7D1',   # Blue for 66kV
    33.0: '#96CEB4',   # Green for 33kV
    22.0: '#FFEAA7'    # Yellow for 22kV
}

voltage_sizes = {
    132.0: 200,
    88.0: 150,
    66.0: 100,
    33.0: 80,
    22.0: 80
}

# Line colors by voltage level
line_colors = {
    132.0: '#FF0000',  # Red for 132kV lines
    88.0: '#800080',   # Purple for 88kV lines
    66.0: '#0000FF',   # Blue for 66kV lines
    33.0: '#008000',   # Green for 33kV lines
    22.0: '#FFA500'    # Orange for 22kV lines
}

# Line widths by voltage level
line_widths = {
    132.0: 1,
    88.0: 1,
    66.0: 1,
    33.0: 1,
    22.0: 1
}

def load_bus_data_from_excel(file_path):
   
    try:
        print(f"Loading bus data from Excel file: {file_path}")
        
        # Try to read the Excel file
        bus_data = pd.read_excel(file_path,sheet_name='Station1')
        
        return bus_data
        
    except FileNotFoundError:
        print(f"Error: Excel file '{file_path}' not found!")
        print("Please make sure the file path is correct.")
        return None
    except Exception as e:
        print(f"Error reading Excel file: {str(e)}")
        return None


def add_buses_from_dataframe(network, bus_data):
    
    # Common column name variations for GPS coordinates
    name_cols = ['Bus_Name', 'bus_name', 'Name', 'name', 'BusName', 'Bus Name']
    voltage_cols = ['v_nom', 'V_nom', 'Voltage', 'voltage', 'kV', 'Voltage_kV', 'Nominal_Voltage']
    lat_cols = ['lat', 'Lat', 'latitude', 'Latitude', 'LAT', 'LATITUDE']
    lon_cols = ['lon', 'Lon', 'lng', 'longitude', 'Longitude', 'LON', 'LONGITUDE']
    
    # Find the correct column names
    name_col = None
    voltage_col = None
    lat_col = None
    lon_col = None
    
    for col in bus_data.columns:
        if col in name_cols:
            name_col = col
        elif col in voltage_cols:
            voltage_col = col
        elif col in lat_cols:
            lat_col = col
        elif col in lon_cols:
            lon_col = col
       
    # Add buses to network
    buses_added = 0
    transmission_count = 0
    distribution_count = 0
    
    for idx, row in bus_data.iterrows():
        try:
            bus_name = str(row[name_col])
            voltage = float(row[voltage_col])
            latitude = float(row[lat_col])
            longitude = float(row[lon_col])
            
            # Validate GPS coordinates for Lesotho region
            if not (-31.0 <= latitude <= -28.0 and 27.0 <= longitude <= 30.0):
                print(f"Warning: Bus '{bus_name}' has coordinates outside expected Lesotho range")
                print(f"  Lat: {latitude}, Lon: {longitude}")
                print("  Expected - Lat: -31.0 to -28.0, Lon: 27.0 to 30.0")
                # Continue anyway but warn user
            
            # Add bus to network using GPS coordinates directly
            network.add("Bus", bus_name, v_nom=voltage, x=longitude, y=latitude)
            buses_added += 1 
            
            # Count by voltage level
            if voltage >= 66:  # Transmission level
                transmission_count += 1
            else:  # Distribution level
                distribution_count += 1
                
        except Exception as e:
            print(f"Warning: Could not add bus from row {idx}: {str(e)}")
            continue
    
    return buses_added > 0

def read_lines_from_excel(file_path):
    
    try:
        df = pd.read_excel(file_path,sheet_name='transmission1')
        return df
    except FileNotFoundError:
        print(f"Excel file not found: {file_path}")
        return None
    except Exception as e:
        print(f"Error reading Excel file: {e}")
        return None
    
def add_lines_from_dataframe(network, lines_df):
    
    if lines_df is None:
        print("No line data available.")
        return
    
    for idx, row in lines_df.iterrows():
        
        # Create line name
        line_name = f"Line_{row['Line_id']}_{row['bus0']}_to_{row['bus1']}"
        
        # Add line to network
        network.add("Line",
                   name=line_name,
                   bus0=row['bus0'],
                   bus1=row['bus1'],
                   length=row['length'],
                   r=row['r'],
                   x=row['x'],
                   s_nom=row['s_nominal'],
                   num_parallel=row['num_parallel'])

def get_line_voltage(network, line_name):
    try:
        line = network.lines.loc[line_name]
        bus0_voltage = network.buses.loc[line['bus0'], 'v_nom']
        bus1_voltage = network.buses.loc[line['bus1'], 'v_nom']
        return max(bus0_voltage, bus1_voltage)
    except Exception:
        return 132.0  # Default voltage

def plot_transmission_lines(ax, network, projection):

    if len(network.lines) == 0:
        print("No transmission lines to plot.")
        return
    lines_plotted = 0

    for line_name in network.lines.index:
        try:
            line = network.lines.loc[line_name]
            bus0_name = line['bus0']
            bus1_name = line['bus1']

            if bus0_name not in network.buses.index or bus1_name not in network.buses.index:
                print(f"Warning: Skipping line {line_name} - buses not found")
                continue

            bus0 = network.buses.loc[bus0_name]
            bus1 = network.buses.loc[bus1_name]
            lon0, lat0 = float(bus0['x']), float(bus0['y'])
            lon1, lat1 = float(bus1['x']), float(bus1['y'])

            # Get line voltage for styling
            line_voltage = get_line_voltage(network, line_name)
            color = line_colors.get(line_voltage, '#000000')
            width = line_widths.get(line_voltage, 2.0)

            # Compute midpoint and apply curvature
            mid_lon = (lon0 + lon1) / 2
            mid_lat = (lat0 + lat1) / 2

            dx = lon1 - lon0
            dy = lat1 - lat0
            norm = np.hypot(dx, dy)
            if norm == 0:
                continue  # Avoid division by zero

            curvature_strength = 0.03
            offset_lon = -dy / norm * curvature_strength
            offset_lat = dx / norm * curvature_strength

            control_lon = mid_lon + offset_lon
            control_lat = mid_lat + offset_lat

            # Bezier path (cubic/Quadratic support via CURVE3)
            path_data = [
                (Path.MOVETO, (lon0, lat0)),
                (Path.CURVE3, (control_lon, control_lat)),
                (Path.CURVE3, (lon1, lat1)),
            ]
            codes, verts = zip(*path_data)
            path = Path(verts, codes)
            patch = patches.PathPatch(path, facecolor='none',
                                      edgecolor=color, lw=width,
                                      alpha=0.8, transform=projection, zorder=5)
            ax.add_patch(patch)
            lines_plotted += 1

        except Exception as e:
            print(f"Warning: Could not plot line {line_name}: {str(e)}")
            continue


# -------------------------
# Main map creation function (uses GADM background)
# -------------------------
def create_geographic_map_on_gadm(network, gadm0=gadm_lso, gadm1=gadm_dis):

    projection = ccrs.PlateCarree()
    fig = plt.figure(figsize=(30, 22), dpi=150)
    ax = plt.axes(projection=projection)

    # Compute extent from GADM bounds with small padding
    minx, miny, maxx, maxy = gadm0.total_bounds
    pad_x = (maxx - minx) * 0.05
    pad_y = (maxy - miny) * 0.05
    ax.set_extent([minx - pad_x, maxx + pad_x, miny - pad_y, maxy + pad_y], crs=projection)

    # Plot GADM layers (country and districts) -- use transform so geopandas draws in the cartopy axes
    gadm0.plot(ax=ax, color='whitesmoke', edgecolor='dimgray', linewidth=1.4, alpha=0.95, zorder=1, transform=projection)
    gadm1.plot(ax=ax, color='whitesmoke', edgecolor='dimgray', linewidth=1.0, zorder=2, transform=projection)

    # Optionally add rivers/other cartopy features if you like (commented out)
    # ax.add_feature(cfeature.RIVERS, linewidth=0.5, edgecolor='blue', zorder=1)

    # Gridlines with labels
    gl = ax.gridlines(crs=projection, draw_labels=True, linewidth=0.5, 
                      color='gray', alpha=0.7, linestyle='--')
    gl.xlabels_top = False
    gl.ylabels_right = False
    gl.xformatter = LONGITUDE_FORMATTER
    gl.yformatter = LATITUDE_FORMATTER

    # Plot transmission lines and buses/generators on top
    plot_transmission_lines(ax, network, projection)

    # Plot buses by voltage (all buses, with bigger markers for high voltage)
    try:
        buses_df = network.buses
        if 'v_nom' not in buses_df.columns:
            buses_df['v_nom'] = 11.0  # fallback

        # Plot each voltage level separately for consistent legend
        for v in sorted(buses_df['v_nom'].dropna().unique()):
            mask = buses_df['v_nom'] == v
            xs = buses_df.loc[mask, 'x'].astype(float)
            ys = buses_df.loc[mask, 'y'].astype(float)
            if len(xs) == 0:
                continue
            color = voltage_colors.get(float(v), 'gray')
            size = voltage_sizes.get(float(v), 80)
            ax.scatter(xs, ys, s=size, c=color, edgecolors='darkred', linewidth=1.2,
                       alpha=0.9, zorder=10, transform=projection,
                       label=f"{int(v)} kV" if v >= 66 else None)

    except Exception as e:
        print(f"Warning plotting buses: {e}")

    # Title and layout
    fig.suptitle('LEC TRANSMISSION Network using PYPSA', fontsize=16, fontweight='bold')
    plt.subplots_adjust(top=0.88, bottom=0.08, left=0.08, right=0.82)

    # Legend: build from voltage, lines, generators
    legend_elements = []
    # Bus legend
    try:
        v_counts = network.buses['v_nom'].value_counts()
    except Exception:
        v_counts = {}

    for v, color in voltage_colors.items():
        if v in v_counts.index:
            sc = plt.scatter([], [], c=[color], s=150 if v >= 66 else 80,
                             edgecolors='darkred', alpha=0.8 if v >= 66 else 0.6)
            legend_elements.append((sc, f'{int(v)} kV ({int(v_counts.get(v,0))} buses)'))

    # Line legend
    # find unique line voltages present in network
    present_line_voltages = set()
    for line_name in network.lines.index:
        try:
            present_line_voltages.add(int(get_line_voltage(network, line_name)))
        except Exception:
            continue
    for v in sorted(present_line_voltages):
        color = line_colors.get(v, '#444444')
        lw = line_widths.get(v, 2.0)
        legend_elements.append((Line2D([0], [0], color=color, lw=lw), f"{v} kV Line"))


    if legend_elements:
        handles, labels = zip(*legend_elements)
        ax.legend(handles, labels, bbox_to_anchor=(1.2, 1), loc='upper left', frameon=True)

    # North arrow and metadata
    ax.annotate('N', xy=(0.9, 0.9), xycoords='axes fraction',
                fontsize=20, fontweight='bold', ha='center', va='center',
                bbox=dict(boxstyle="round,pad=0.3", facecolor='white', edgecolor='black'), zorder=50)
    ax.annotate('↑', xy=(0.9, 0.87), xycoords='axes fraction',
                fontsize=16, ha='center', va='center', zorder=50)

    ax.text(0.02, 0.02, 'Coordinate System: WGS84\nProjection: PlateCarree (Lat/Lon)',
            transform=ax.transAxes, fontsize=8, verticalalignment='bottom',
            bbox=dict(boxstyle="round,pad=0.3", facecolor='white', alpha=0.8), zorder=50)

    plt.show()
    return fig

# -------------------------
# Rest of your workflow: load Excel, add buses/lines/generators (unchanged)
# -------------------------

# MODIFY THIS PATH TO POINT TO YOUR EXCEL FILE
excel_file_path = r"C:/Users/Mothala/Documents/BusData.xlsx"  # Change this to your actual file path

# (Assumes your helper functions load_bus_data_from_excel, add_buses_from_dataframe, read_lines_from_excel, add_lines_from_dataframe, add_generators are defined earlier in your script)
bus_data = load_bus_data_from_excel(excel_file_path)
success = add_buses_from_dataframe(network, bus_data)

lines_df = read_lines_from_excel(excel_file_path)
add_lines_from_dataframe(network, lines_df)

if not success:
    print("NO DATA...")


# Create the geographic visualization using GADM background
geo_fig = create_geographic_map_on_gadm(network)