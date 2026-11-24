import pypsa
import numpy as np
import pandas as pd
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

# Create a new PyPSA network
network = pypsa.Network()

print("Creating Lesotho Electrical Network from Excel Data...")
print("=" * 55)

voltage_colors = {
    132.0: '#FF6B6B',  # Red for 132kV
    88.0: '#505050',   # grey for 88kV  
    66.0: '#45B7D1',   # Blue for 66kV
    33.0: '#96CEB4',   # Green for 33kV
    22.0: '#FFEAA7'    # Yellow for 22kV
}

voltage_sizes = {
    132.0: 150,
    88.0: 150,
    66.0: 150,
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
    132.0: 4.0,
    88.0: 3.5,
    66.0: 3.0,
    33.0: 2.5,
    22.0: 2.0
}

# Generator colors and markers
generator_colors = {
    'solar': '#FFD700',  # Gold for solar
    'hydro': '#1E90FF'   # DodgerBlue for hydro
}

generator_markers = {
    'solar': '^',  # Triangle for solar
    'hydro': 's'   # Square for hydro
}

def load_bus_data_from_excel(file_path):
    """Load bus data from Excel file"""
    try:
        print(f"Loading bus data from Excel file: {file_path}")
        
        # Try to read the Excel file
        bus_data = pd.read_excel(file_path,sheet_name='Sheet1')
        
        # Display the column names to understand the structure
        print(f"Excel columns found: {list(bus_data.columns)}")
        print(f"Number of buses in Excel file: {len(bus_data)}")
        
        # Show first few rows to understand the data structure
        print("\nFirst few rows of data:")
        print(bus_data.head())
        
        return bus_data
        
    except FileNotFoundError:
        print(f"Error: Excel file '{file_path}' not found!")
        print("Please make sure the file path is correct.")
        return None
    except Exception as e:
        print(f"Error reading Excel file: {str(e)}")
        return None


def add_buses_from_dataframe(network, bus_data):
    """Add buses to PyPSA network from pandas DataFrame using GPS coordinates directly"""
    
    if bus_data is None:
        print("No bus data available. Using sample data instead.")
        return add_sample_buses(network)
    
    print("Adding buses from Excel data using GPS coordinates directly...")
    
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
    
    # Check if we found all required columns
    missing_cols = []
    if name_col is None:
        missing_cols.append("Bus Name")
    if voltage_col is None:
        missing_cols.append("Voltage")
    if lat_col is None:
        missing_cols.append("Latitude")
    if lon_col is None:
        missing_cols.append("Longitude")
    
    if missing_cols:
        print(f"Warning: Could not find columns for: {', '.join(missing_cols)}")
        print("Please ensure your Excel file has columns for:")
        print("- Bus Name (Bus_Name, name, Name, etc.)")
        print("- Voltage (v_nom, Voltage, kV, etc.)")
        print("- Latitude (lat, latitude, Latitude, etc.)")
        print("- Longitude (lon, longitude, Longitude, etc.)")
        print("\nUsing sample data instead...")
        return add_sample_buses(network)
    
    print(f"Found columns:")
    print(f"  Bus Name: {name_col}")
    print(f"  Voltage: {voltage_col}")
    print(f"  Latitude: {lat_col}")
    print(f"  Longitude: {lon_col}")
    
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
    
    print(f"✓ Successfully added {buses_added} buses")
    print(f"  - {transmission_count} transmission buses (≥66 kV)")
    print(f"  - {distribution_count} distribution buses (<66 kV)")
    
    return buses_added > 0

def read_lines_from_excel(file_path):
    """
    Read transmission line data from Excel file
    
    Expected columns: Line_id, bus0, bus1, r, x, s_nom, length, num_parallel, v_nom
    """
    try:
        df = pd.read_excel(file_path,sheet_name='Sheet3')
        print(f"Successfully read {len(df)} lines from {file_path}")
        return df
    except FileNotFoundError:
        print(f"Excel file not found: {file_path}")
        return None
    except Exception as e:
        print(f"Error reading Excel file: {e}")
        return None
    
def add_lines_from_dataframe(network, lines_df):
    """Add transmission lines to PyPSA network from DataFrame"""
    
    if lines_df is None:
        print("No line data available.")
        return
    
    print(f"\nADDING TRANSMISSION LINES:")
    print("=" * 60)
    
    for idx, row in lines_df.iterrows():
        
        # Set thermal limit if s_nom is 0 or missing
        if row['s_nom'] == 0 or pd.isna(row['s_nom']):
            # Estimate based on voltage level and number of circuits
            if row['v_nom'] == 33:
                s_nom_value = 50 * row['num_parallel']   # MVA
            elif row['v_nom'] == 132:
                s_nom_value = 200 * row['num_parallel']  # MVA
            elif row['v_nom'] == 400:
                s_nom_value = 800 * row['num_parallel']  # MVA
            else:
                s_nom_value = 100 * row['num_parallel']  # Default
        else:
            s_nom_value = row['s_nom']
        
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
                   s_nom=s_nom_value,
                   num_parallel=row['num_parallel'])
        
        # Print line details
        circuit_type = "Double Circuit" if row['num_parallel'] == 2 else "Single Circuit"
        print(f"Line {row['Line_id']:2d}: {row['bus0']} → {row['bus1']}")
        print(f"         {circuit_type}, {row['v_nom']}kV, {row['length']}km")
        print(f"         Z = {row['r']:.3f} + j{row['x']:.3f} Ω/km")
        print(f"         S_nom = {s_nom_value} MVA\n")

def add_sample_buses(network):
    """Add sample buses with GPS coordinates if Excel file cannot be read"""
    print("Adding sample Lesotho buses with GPS coordinates...")
    
    # Sample buses with GPS coordinates (lat, lon)
    sample_buses = [
        ("Ramarothole", 132, -29.6833, 27.4833),
        ("Mohale Dam", 132, -29.5667, 27.4500),
        ("Mohale Intake", 132, -29.5833, 27.4667),
        ("Mabote Trans", 132, -29.6667, 27.4667),
        ("Mazenod Trans", 132, -29.6667, 27.5000),
        ("Maputose Trans", 132, -29.6500, 27.3500),
        ("Lejone", 132, -29.5500, 27.4333),
        ("Pitseng", 132, -29.6000, 27.3667),
        ("Mabote Distr", 33, -29.6667, 27.4667),
        ("Mazenod Distr", 33, -29.6667, 27.5000),
        ("Botsabelo", 33, -29.6667, 27.4833),
        ("LEC-Boarder", 33, -29.6750, 27.4667),
        ("LEC HQ", 33, -29.6750, 27.4700),
        ("Pioneer", 33, -29.6750, 27.4750),
        ("Thetsane", 33, -29.6800, 27.4833),
        ("Highway", 33, -29.6667, 27.4750),
        ("Roma", 33, -29.6500, 27.5167),
        ("Muela", 132, -29.5000, 27.5500)  # Added Muela bus for hydro generator
    ]
    
    for name, voltage, lat, lon in sample_buses:
        network.add("Bus", name, v_nom=voltage, x=lon, y=lat)
    
    print(f"✓ Added {len(sample_buses)} sample buses with GPS coordinates")
    return True

def add_generators(network):
    """Add solar and hydro generators to the network"""
    print(f"\nADDING GENERATORS:")
    print("=" * 40)
    
    # Check if required buses exist
    required_buses = ['Ramarothole', 'Muela']
    missing_buses = []
    
    for bus in required_buses:
        if bus not in network.buses.index:
            missing_buses.append(bus)
    
    if missing_buses:
        print(f"Warning: Required buses not found: {missing_buses}")
        print("Adding missing buses...")
        
        # Add missing buses if they don't exist
        if 'Ramarothole' in missing_buses:
            network.add("Bus", "Ramarothole", v_nom=132, x=27.4833, y=-29.6833)
            print("✓ Added Ramarothole bus for solar generator")
        
        if 'Muela' in missing_buses:
            network.add("Bus", "Muela", v_nom=132, x=27.5500, y=-29.5000)
            print("✓ Added Muela bus for hydro generator")
    
    # Add Solar Generator at Ramarothole
    print("\nAdding Solar Generator at Ramarothole...")
    network.add("Generator",
                name="Solar_Ramarothole",
                bus="Ramarothole",
                p_nom=25,  # 25 MW nominal capacity
                p_max_pu=1.0,  # Maximum power output (per unit)
                p_min_pu=0.0,  # Minimum power output (per unit)
                marginal_cost=0,  # Solar has zero marginal cost
                carrier="solar",
                efficiency=0.95)
    
    print("✓ Solar Generator Added:")
    print(f"  Location: Ramarothole (132 kV)")
    print(f"  Capacity: 25 MW")
    print(f"  Type: Solar PV")
    print(f"  Marginal Cost: $0/MWh")
    
    # Add Hydro Generator at Muela
    print("\nAdding Hydro Generator at Muela...")
    network.add("Generator",
                name="Hydro_Muela", 
                bus="Muela",
                p_nom=72,  # 72 MW nominal capacity (typical for Muela)
                p_max_pu=1.0,  # Maximum power output (per unit)
                p_min_pu=0.2,  # Minimum power output (20% of capacity)
                marginal_cost=10,  # Low marginal cost for hydro
                carrier="hydro",
                efficiency=0.90)
    
    print("✓ Hydro Generator Added:")
    print(f"  Location: Muela (132 kV)")
    print(f"  Capacity: 72 MW")
    print(f"  Type: Hydroelectric")
    print(f"  Marginal Cost: $10/MWh")
    
    print(f"\n✓ Successfully added {len(network.generators)} generators to the network")
    
    return True

def get_line_voltage(network, line_name):
    """Get the voltage level of a transmission line based on its connected buses"""
    try:
        line = network.lines.loc[line_name]
        bus0_voltage = network.buses.loc[line['bus0'], 'v_nom']
        bus1_voltage = network.buses.loc[line['bus1'], 'v_nom']
        # Use the higher voltage level
        return max(bus0_voltage, bus1_voltage)
    except:
        return 132.0  # Default voltage

def plot_transmission_lines(ax, network, projection):
    """Plot transmission lines on the map with smooth curves"""
    if len(network.lines) == 0:
        print("No transmission lines to plot.")
        return

    print(f"Plotting {len(network.lines)} transmission lines...")
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
            lon0, lat0 = bus0['x'], bus0['y']
            lon1, lat1 = bus1['x'], bus1['y']

            # Get line voltage for styling
            line_voltage = get_line_voltage(network, line_name)
            color = line_colors.get(line_voltage, '#000000')
            width = line_widths.get(line_voltage, 2.0)

            # Compute midpoint and apply curvature
            mid_lon = (lon0 + lon1) / 2
            mid_lat = (lat0 + lat1) / 2

            # Curvature vector: perpendicular offset
            dx = lon1 - lon0
            dy = lat1 - lat0
            norm = np.hypot(dx, dy)
            if norm == 0:
                continue  # Avoid division by zero

            curvature_strength = 0.03  # tweak this to adjust curve
            offset_lon = -dy / norm * curvature_strength
            offset_lat = dx / norm * curvature_strength

            control_lon = mid_lon + offset_lon
            control_lat = mid_lat + offset_lat

            # Bezier path
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

    print(f"✓ Successfully plotted {lines_plotted} transmission lines")

def plot_generators(ax, network, projection):
    """Plot generators on the map"""
    if len(network.generators) == 0:
        print("No generators to plot.")
        return
    
    print(f"Plotting {len(network.generators)} generators...")
    generators_plotted = 0
    
    for gen_name in network.generators.index:
        try:
            generator = network.generators.loc[gen_name]
            bus_name = generator['bus']
            carrier = generator['carrier']
            capacity = generator['p_nom']
            
            # Get bus coordinates
            if bus_name not in network.buses.index:
                print(f"Warning: Bus {bus_name} for generator {gen_name} not found")
                continue
            
            bus = network.buses.loc[bus_name]
            lon, lat = bus['x'], bus['y']
            
            # Get generator styling
            color = generator_colors.get(carrier, '#808080')  # Default to gray
            marker = generator_markers.get(carrier, 'o')      # Default to circle
            
            # Plot the generator
            ax.scatter(lon, lat, s=300, c=color, marker=marker, 
                      edgecolors='black', linewidth=2, alpha=0.9,
                      transform=projection, zorder=15,
                      label=f'{carrier.capitalize()} Generator' if generators_plotted == 0 or 
                            (generators_plotted == 1 and carrier != network.generators.iloc[0]['carrier']) else "")
            
            """# Add generator label
            ax.annotate(f'{carrier.capitalize()}\n{capacity}MW', 
                       (lon, lat), xytext=(10, 10), 
                       textcoords='offset points', fontsize=9, fontweight='bold',
                       bbox=dict(boxstyle="round,pad=0.3", facecolor='white', 
                                edgecolor=color, alpha=0.9),
                       transform=projection, ha='left', va='bottom', zorder=16)"""
            
            generators_plotted += 1
            
        except Exception as e:
            print(f"Warning: Could not plot generator {gen_name}: {str(e)}")
            continue
    
    print(f"✓ Successfully plotted {generators_plotted} generators")

def create_geographic_map(network):
    """Create a geographic map of Lesotho with buses, transmission lines, and generators"""
    print(f"Creating geographic map of Lesotho with {len(network.buses)} buses, {len(network.lines)} lines, and {len(network.generators)} generators...")
    
    # Set up the map projection and extent
    # Lesotho boundaries approximately: 27°S to 30.5°S, 27°E to 29.5°E
    projection = ccrs.PlateCarree()
    
    # Create figure with cartopy
    fig = plt.figure(figsize=(20, 14))
    ax = plt.axes(projection=projection)
    
    # Set map extent to focus on Lesotho
    lesotho_extent = [27.0, 29.5, -30.7, -28.5]  # [west, east, south, north]
    ax.set_extent(lesotho_extent, crs=projection)
    
    # Add map features
    ax.add_feature(cfeature.COASTLINE, linewidth=0.8, color='navy')
    ax.add_feature(cfeature.BORDERS, linewidth=1.5, color='black')
    ax.add_feature(cfeature.LAND, facecolor='lightgray', alpha=0.3)
    ax.add_feature(cfeature.OCEAN, facecolor='lightblue', alpha=0.3)
    ax.add_feature(cfeature.LAKES, facecolor='lightblue', alpha=0.5)
    ax.add_feature(cfeature.RIVERS, linewidth=0.5, color='blue', alpha=0.7)
    
    # Add topographic features
    ax.add_feature(cfeature.COASTLINE, linewidth=0.5)
    ax.stock_img()  # Add natural earth background
    
    # Add gridlines
    gl = ax.gridlines(crs=projection, draw_labels=True, linewidth=0.5, 
                      color='gray', alpha=0.7, linestyle='--')
    gl.xlabels_top = False
    gl.ylabels_right = False
    gl.xformatter = LONGITUDE_FORMATTER
    gl.yformatter = LATITUDE_FORMATTER
    
    # Plot transmission lines FIRST (so they appear behind buses)
    plot_transmission_lines(ax, network, projection)
    
    # Separate buses by voltage level
    transmission_buses = network.buses[network.buses.v_nom >= 66]
    distribution_buses = network.buses[network.buses.v_nom < 66]
    
    # Plot transmission buses (red circles)
    if len(transmission_buses) > 0:
        for bus in transmission_buses.index:
            lat = transmission_buses.loc[bus, 'y']  # y coordinate is latitude
            lon = transmission_buses.loc[bus, 'x']  # x coordinate is longitude
            voltage = transmission_buses.loc[bus, 'v_nom']
            
            color = voltage_colors.get(voltage, 'gray')  # Default to gray if voltage not mapped
            size = voltage_sizes.get(voltage, 150)
            
            # Plot bus location
            ax.scatter(lon, lat, s=size, c=color, edgecolors='darkred', 
                      linewidth=2, alpha=0.8, zorder=10, transform=projection,
                      label='Transmission' if bus == transmission_buses.index[0] else "")
            
    # Plot distribution buses (blue circles)
    if len(distribution_buses) > 0:
        for bus in distribution_buses.index:
            lat = distribution_buses.loc[bus, 'y']  # y coordinate is latitude
            lon = distribution_buses.loc[bus, 'x']  # x coordinate is longitude
            voltage = distribution_buses.loc[bus, 'v_nom']

            color = voltage_colors.get(voltage, 'gray')  # Default to gray if voltage not mapped
            size = voltage_sizes.get(voltage, 150)

            # Plot bus location
            ax.scatter(lon, lat, s=size, c=color, edgecolors='darkgreen',
                      linewidth=2, alpha=0.8, zorder=10, transform=projection,
                      label='Distribution' if bus == distribution_buses.index[0] else "")
    
    # Plot generators (on top of everything)
    plot_generators(ax, network, projection)
    
    # Add title and labels
    ax.set_title(f'LEC PyPSA Network with Generators\n'
                f'{len(network.buses)} Buses, {len(network.lines)} Lines, {len(network.generators)} Generators',
                fontsize=16, fontweight='bold', pad=20)
   
    # Create comprehensive legend
    legend_elements = []

    # Try to get voltage counts from bus_data if available, otherwise from network
    try:
        voltage_counts = bus_data['Voltage'].value_counts() if 'bus_data' in globals() and bus_data is not None else network.buses['v_nom'].value_counts()
    except:
        voltage_counts = network.buses['v_nom'].value_counts()

    # Create dummy scatter plots for voltage levels
    for v, color in voltage_colors.items():
        if v in voltage_counts.index:
            sc = plt.scatter([], [],
                            c=[color],
                            s=150 if v >= 66 else 80,
                            edgecolors='darkred',
                            alpha=0.8 if v >= 66 else 0.6,
                            label=f'{int(v)} kV ({voltage_counts[v]} buses)')
            legend_elements.append(sc)
    
    # Line voltage level patches
    for v, color in line_colors.items():
        if v in [get_line_voltage(network, line) for line in network.lines.index]:
            legend_elements.append(Line2D([0], [0], color=color, linestyle='-', linewidth=2, 
                                    label=f'{int(v)} kV Line'))
    
    # Generator legend elements
    for carrier, color in generator_colors.items():
        if any(network.generators['carrier'] == carrier):
            marker = generator_markers.get(carrier, 'o')
            capacity = network.generators[network.generators['carrier'] == carrier]['p_nom'].iloc[0]
            legend_elements.append(plt.scatter([], [], c=[color], s=150, marker=marker,
                                            edgecolors='black', alpha=0.9,
                                            label=f'{carrier.capitalize()} ({capacity}MW)'))

    plt.legend(
        handles=legend_elements,
        bbox_to_anchor=(1.10, 1),
        loc='upper left'
    )
    
    # Add North arrow
    ax.annotate('N', xy=(0.95, 0.95), xycoords='axes fraction',
                fontsize=20, fontweight='bold', ha='center', va='center',
                bbox=dict(boxstyle="round,pad=0.3", facecolor='white', 
                         edgecolor='black'))
    ax.annotate('↑', xy=(0.95, 0.92), xycoords='axes fraction',
                fontsize=16, ha='center', va='center')
    
    # Add scale information
    ax.text(0.02, 0.02, 'Coordinate System: WGS84\nProjection: Geographic (Lat/Lon)',
            transform=ax.transAxes, fontsize=8, verticalalignment='bottom',
            bbox=dict(boxstyle="round,pad=0.3", facecolor='white', alpha=0.8))
    
    plt.tight_layout()
    plt.show()
    print("✓ Geographic map with generators created successfully!")
    
    return fig

# Try to load bus data from Excel file
# MODIFY THIS PATH TO POINT TO YOUR EXCEL FILE
excel_file_path = r"C:/Users/Mothala/Documents/BusData.xlsx"  # Change this to your actual file path

bus_data = load_bus_data_from_excel(excel_file_path)
success = add_buses_from_dataframe(network, bus_data)

lines_df = read_lines_from_excel(excel_file_path)
add_lines_from_dataframe(network, lines_df)

if not success:
    print("Falling back to sample data...")
    add_sample_buses(network)

# Add generators to the network
add_generators(network)

# Display network summary
print(f"\nNetwork Summary:")
print("-" * 25)
print(f"Total Buses: {len(network.buses)}")
print(f"Total Lines: {len(network.lines)}")
print(f"Total Generators: {len(network.generators)}")

# Separate buses by voltage level
transmission_buses = network.buses[network.buses.v_nom >= 66]
distribution_buses = network.buses[network.buses.v_nom < 66]

print(f"Transmission Level (≥66 kV): {len(transmission_buses)}")
print(f"Distribution Level (<66 kV): {len(distribution_buses)}")

# Display generator summary
if len(network.generators) > 0:
    print(f"\nGenerator Summary:")
    print("-" * 25)
    total_capacity = 0
    for gen_name in network.generators.index:
        gen = network.generators.loc[gen_name]
        capacity = gen['p_nom']
        carrier = gen['carrier']
        bus = gen['bus']
        total_capacity += capacity
        print(f"{gen_name}: {capacity}MW {carrier} at {bus}")
    print(f"Total Generation Capacity: {total_capacity}MW")

# Display coordinate information
if len(network.buses) > 0:
    print(f"\nGPS Coordinate Information:")
    print("-" * 25)
    print("Using GPS coordinates directly from Excel (no conversion needed)...")
    
    for i, bus in enumerate(network.buses.index[:5]):  # Show first 5 buses as example
        lat = network.buses.loc[bus, 'y']  # y is latitude
        lon = network.buses.loc[bus, 'x']  # x is longitude
        voltage = network.buses.loc[bus, 'v_nom']
        print(f"{bus} ({voltage}kV): Lat {lat:.4f}, Lon {lon:.4f}")
        
        # Check if coordinates are reasonable for Lesotho
        if not (27.0 <= lon <= 30.0 and -31.0 <= lat <= -28.0):
            print(f"  WARNING: {bus} coordinates appear to be outside Lesotho!")
    
    if len(network.buses) > 5:
        print(f"... and {len(network.buses) - 5} more buses")
    
    # Show coordinate ranges
    all_lats = [network.buses.loc[bus, 'y'] for bus in network.buses.index]
    all_lons = [network.buses.loc[bus, 'x'] for bus in network.buses.index]
    print(f"\nCoordinate Ranges:")
    print(f"Latitude:  {min(all_lats):.4f} to {max(all_lats):.4f}")
    print(f"Longitude: {min(all_lons):.4f} to {max(all_lons):.4f}")
    print(f"Expected for Lesotho - Lat: -31.0 to -28.0, Lon: 27.0 to 30.0")

# Display line information
if len(network.lines) > 0:
    print(f"\nTransmission Line Information:")
    print("-" * 25)
    for i, line in enumerate(network.lines.index[:5]):  # Show first 5 lines as example
        line_data = network.lines.loc[line]
        bus0 = line_data['bus0']
        bus1 = line_data['bus1']
        length = line_data['length']
        print(f"{line}: {bus0} → {bus1} ({length}km)")
    
    if len(network.lines) > 5:
        print(f"... and {len(network.lines) - 5} more lines")

# Create the geographic visualization
print(f"\nCreating Geographic Network Visualization...")
geo_fig = create_geographic_map(network)

print(f"\n" + "="*70)
print("Lesotho Electrical Network Geographic Map with Generators Complete!")
print("✓ Buses plotted using GPS coordinates directly from Excel sheet")
print("✓ Transmission lines plotted connecting buses")
print("✓ Solar generator added at Ramarothole bus (50 MW)")
print("✓ Hydro generator added at Muela bus (72 MW)")
print("✓ No coordinate conversion performed - using original GPS values")
print("✓ Map includes coastlines, borders, and topographic features")
print("✓ Map extent focused on Lesotho boundaries")
print("✓ Transmission and distribution buses clearly distinguished")
print("✓ Lines colored and styled by voltage level")
print("✓ Generators plotted with distinctive symbols and labels")
print("\nMap Features:")
print("- Natural Earth background imagery")
print("- Country borders and coastlines")
print("- Rivers, lakes, and topographic features")
print("- Coordinate grid with lat/lon labels")
print("- North arrow and scale information")
print("- Transmission lines with voltage-based styling")
print("- Solar generator (triangle symbol) at Ramarothole")
print("- Hydro generator (square symbol) at Muela")
print("- Generator capacity labels and legend")
print("\nGenerator Details:")
print("- Solar: 50 MW capacity, $0/MWh marginal cost, 95% efficiency")
print("- Hydro: 72 MW capacity, $10/MWh marginal cost, 90% efficiency, 20% minimum output")
print("="*70)