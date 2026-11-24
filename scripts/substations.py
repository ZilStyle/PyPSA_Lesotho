import pypsa
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature
from cartopy.mpl.gridliner import LONGITUDE_FORMATTER, LATITUDE_FORMATTER
import cartopy.io.shapereader as shpreader
import matplotlib.patches as mpatches

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

##########################################################################################################

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
###################################################################################################

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
        ("Roma", 33, -29.6500, 27.5167)
    ]
    
    for name, voltage, lat, lon in sample_buses:
        network.add("Bus", name, v_nom=voltage, x=lon, y=lat)
    
    print(f"✓ Added {len(sample_buses)} sample buses with GPS coordinates")
    return True

def create_geographic_map(network):
    """Create a geographic map of Lesotho with buses plotted using GPS coordinates"""
    print(f"Creating geographic map of Lesotho with {len(network.buses)} buses...")
    
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
            '''
            # Add bus name annotation
            ax.annotate(f'{bus}\n{voltage}kV', (lon, lat), xytext=(5, 5), 
                       textcoords='offset points', fontsize=8, fontweight='bold',
                       bbox=dict(boxstyle="round,pad=0.3", facecolor='white', 
                                edgecolor='red', alpha=0.8),
                       transform=projection, ha='left', va='bottom')
            '''
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
            '''
            # Add bus name annotation
            ax.annotate(f'{bus}\n{voltage}kV', (lon, lat), xytext=(5, 5), 
                       textcoords='offset points', fontsize=8, fontweight='bold',
                       bbox=dict(boxstyle="round,pad=0.3", facecolor='white', 
                                edgecolor='blue', alpha=0.8),
                       transform=projection, ha='left', va='bottom')
            '''
    # Add title and labels
    ax.set_title(f'Lesotho Electrical Network - Geographic Map\n'
                f'{len(network.buses)} Buses ({len(transmission_buses)} Transmission, '
                f'{len(distribution_buses)} Distribution)', 
                fontsize=16, fontweight='bold', pad=20)
   
   # Add legend
    legend_elements = [
    mpatches.Patch(color=color, label=f'{int(v)} kV')
    for v, color in voltage_colors.items()
    ]

    plt.legend(
    handles=legend_elements,
    title='Voltage Levels (kV)',
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
    
    # Add transmission lines 
    #plt.plot([27.5382, 27.9150], [-29.2841, -28.9140], 'r-', linewidth=3, alpha=0.7, label='Transmission Line')
    #########################################################################################################
    # Simply replace the sample data with:
    #file_path = r"C:/Users/Mothala/Documents/BusData.xlsx" # Make sure this path is correct relative to your script
    #lines = pd.read_excel(file_path, sheet_name='Sheet3')


# The rest of the code works automatically!
    ########################################################################################################
    plt.tight_layout()
    plt.show()
    print("✓ Geographic map created successfully!")
    
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

# Display network summary
print(f"\nNetwork Summary:")
print("-" * 25)
print(f"Total Buses: {len(network.buses)}")

# Separate buses by voltage level
transmission_buses = network.buses[network.buses.v_nom >= 66]
distribution_buses = network.buses[network.buses.v_nom < 66]

print(f"Transmission Level (≥66 kV): {len(transmission_buses)}")
print(f"Distribution Level (<66 kV): {len(distribution_buses)}")

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

# Create the geographic visualization
print(f"\nCreating Geographic Network Visualization...")
geo_fig = create_geographic_map(network)

print(f"\n" + "="*70)
print("Lesotho Electrical Network Geographic Map Complete!")
print("✓ Buses plotted using GPS coordinates directly from Excel sheet")
print("✓ No coordinate conversion performed - using original GPS values")
print("✓ Map includes coastlines, borders, and topographic features")
print("✓ Map extent focused on Lesotho boundaries")
print("✓ Transmission and distribution buses clearly distinguished")
print("\nMap Features:")
print("- Natural Earth background imagery")
print("- Country borders and coastlines")
print("- Rivers, lakes, and topographic features")
print("- Coordinate grid with lat/lon labels")
print("- North arrow and scale information")
print("="*70)