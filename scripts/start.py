import pypsa
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import cartopy.crs as ccrs
import cartopy.feature as cfeature

# Create a new PyPSA network
network = pypsa.Network()

print("Creating Lesotho Electrical Network from Excel Data...")
print("=" * 55)

def load_bus_data_from_excel(file_path):
    """Load bus data from Excel file"""
    try:
        print(f"Loading bus data from Excel file: {file_path}")
        
        # Try to read the Excel file
        # You may need to specify the sheet name if there are multiple sheets
        bus_data = pd.read_excel(file_path)
        
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
    """Add buses to PyPSA network from pandas DataFrame using latitude and longitude"""
    
    if bus_data is None:
        print("No bus data available. Using sample data instead.")
        return add_sample_buses(network)
    
    print("Adding buses from Excel data...")
    
    # Common column name variations we might encounter
    name_cols = ['Bus_Name', 'bus_name', 'Name', 'name', 'BusName', 'Bus Name', 'Station', 'station']
    voltage_cols = ['v_nom', 'V_nom', 'Voltage', 'voltage', 'kV', 'Voltage_kV', 'Nominal_Voltage']
    lat_cols = ['lat', 'Lat', 'latitude', 'Latitude', 'LAT', 'LATITUDE', 'Lat_DD', 'lat_dd']
    lon_cols = ['lon', 'Lon', 'lng', 'Lng', 'longitude', 'Longitude', 'LON', 'LONGITUDE', 'Long', 'long', 'Lon_DD', 'lon_dd']
    
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
        print("- Bus Name (Bus_Name, name, Name, Station, etc.)")
        print("- Voltage (v_nom, Voltage, kV, etc.)")
        print("- Latitude (lat, Latitude, LAT, etc.)")
        print("- Longitude (lon, Longitude, lng, Long, etc.)")
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
            
            # Validate coordinates are reasonable for Lesotho
            # Lesotho is approximately between 28-31°S latitude and 27-30°E longitude
            if not (-32 <= latitude <= -28):
                print(f"Warning: Bus '{bus_name}' has unusual latitude {latitude}° (expected -32° to -28° for Lesotho)")
            if not (26 <= longitude <= 31):
                print(f"Warning: Bus '{bus_name}' has unusual longitude {longitude}° (expected 26° to 31° for Lesotho)")
            
            # Add bus to network using latitude as x and longitude as y for PyPSA
            # Note: PyPSA typically uses x,y coordinates but we'll store lat/lon directly
            network.add("Bus", bus_name, v_nom=voltage, x=longitude, y=latitude)
            buses_added += 1
            
            # Count by voltage level
            if voltage >= 66:  # Transmission level (typically 132kV, 220kV, etc.)
                transmission_count += 1
            else:  # Distribution level (typically 33kV, 22kV, 11kV, etc.)
                distribution_count += 1
                
        except Exception as e:
            print(f"Warning: Could not add bus from row {idx}: {str(e)}")
            continue
    
    print(f"✓ Successfully added {buses_added} buses")
    print(f"  - {transmission_count} transmission buses (≥66 kV)")
    print(f"  - {distribution_count} distribution buses (<66 kV)")
    
    return buses_added > 0

def add_sample_buses(network):
    """Add sample buses with Lesotho lat/lon coordinates if Excel file cannot be read"""
    print("Adding sample Lesotho buses with lat/lon coordinates...")
    
    # Sample buses with approximate Lesotho lat/lon coordinates
    sample_buses = [
        ("Maseru Main", 132, -29.3167, 27.4833),
        ("Mohale Dam", 132, -29.4500, 27.4167),
        ("Katse Dam", 132, -29.1167, 28.4333),
        ("Mafeteng", 132, -29.8167, 27.2333),
        ("Roma", 132, -29.4500, 27.7167),
        ("Teyateyaneng", 132, -29.1500, 27.7333),
        ("Leribe", 132, -28.8667, 28.0333),
        ("Butha-Buthe", 132, -28.7667, 28.2500),
        ("Maseru Industrial", 33, -29.3000, 27.5000),
        ("Ha Abia", 33, -29.3500, 27.4500),
        ("Lancers Inn", 33, -29.2833, 27.5167),
        ("Thaba-Bosiu", 33, -29.4167, 27.5833),
        ("Morija", 33, -29.5167, 27.5833),
        ("Mazenod", 33, -29.4333, 27.5000),
        ("Maputsoe", 33, -28.9000, 28.0167),
        ("Peka", 33, -29.0833, 27.9167),
        ("St James", 33, -29.2167, 27.6833)
    ]
    
    for name, voltage, lat, lon in sample_buses:
        network.add("Bus", name, v_nom=voltage, x=lon, y=lat)  # x=longitude, y=latitude
    
    print(f"✓ Added {len(sample_buses)} sample buses with lat/lon coordinates")
    return True

# Try to load bus data from Excel file
# MODIFY THIS PATH TO POINT TO YOUR EXCEL FILE
excel_file_path = r"C:/Users/Mothala/Documents/BusData.xlsx"  # Change this to your actual file path

bus_data = load_bus_data_from_excel(excel_file_path)
success = add_buses_from_dataframe(network, bus_data)

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

# Display bus information grouped by voltage level
if len(transmission_buses) > 0:
    print(f"\nTransmission Buses:")
    print("-" * 20)
    for bus in transmission_buses.index:
        voltage = transmission_buses.loc[bus, 'v_nom']
        longitude = transmission_buses.loc[bus, 'x']  # x stores longitude
        latitude = transmission_buses.loc[bus, 'y']   # y stores latitude
        print(f"{bus}: {voltage} kV at ({latitude:.4f}°, {longitude:.4f}°)")

if len(distribution_buses) > 0:
    print(f"\nDistribution Buses:")
    print("-" * 20)
    for bus in distribution_buses.index:
        voltage = distribution_buses.loc[bus, 'v_nom']
        longitude = distribution_buses.loc[bus, 'x']  # x stores longitude
        latitude = distribution_buses.loc[bus, 'y']   # y stores latitude
        print(f"{bus}: {voltage} kV at ({latitude:.4f}°, {longitude:.4f}°)")

def create_static_network_plot(network):
    """Create static matplotlib plot showing all buses using latitude and longitude"""
    print(f"Creating static network visualization with lat/lon coordinates...")
    
    # Separate buses by voltage level
    transmission_buses = network.buses[network.buses.v_nom >= 66]
    distribution_buses = network.buses[network.buses.v_nom < 66]
    
    # Create matplotlib figure
    fig, ax = plt.subplots(1, 1, figsize=(12, 10))

    # Plot transmission buses
    if len(transmission_buses) > 0:
        for bus in transmission_buses.index:
            longitude = transmission_buses.loc[bus, 'x']  # x stores longitude
            latitude = transmission_buses.loc[bus, 'y']   # y stores latitude
            voltage = transmission_buses.loc[bus, 'v_nom']
            
            # Draw transmission bus
            ax.scatter(longitude, latitude, s=300, c='red', 
                      edgecolors='black', linewidth=2, alpha=0.8, zorder=5)
            
            # Bus label
            ax.annotate(bus, (longitude, latitude), xytext=(0, 30), 
                       textcoords='offset points', ha='center', va='bottom',
                       fontsize=8, fontweight='bold', color='darkred')
            
            # Voltage info
            ax.annotate(f'{voltage} kV', (longitude, latitude), xytext=(0, -25), 
                       textcoords='offset points', ha='center', va='top',
                       bbox=dict(boxstyle="round,pad=0.2", facecolor='lightcoral', alpha=0.7),
                       fontsize=7)
    
    # Plot distribution buses
    if len(distribution_buses) > 0:
        for bus in distribution_buses.index:
            longitude = distribution_buses.loc[bus, 'x']  # x stores longitude
            latitude = distribution_buses.loc[bus, 'y']   # y stores latitude
            voltage = distribution_buses.loc[bus, 'v_nom']
            
            # Draw distribution bus
            ax.scatter(longitude, latitude, s=200, c='blue', 
                      edgecolors='black', linewidth=2, alpha=0.8, zorder=5)
            
            # Bus label
            ax.annotate(bus, (longitude, latitude), xytext=(0, 25), 
                       textcoords='offset points', ha='center', va='bottom',
                       fontsize=8, fontweight='bold', color='darkblue')
            
            # Voltage info
            ax.annotate(f'{voltage} kV', (longitude, latitude), xytext=(0, -20), 
                       textcoords='offset points', ha='center', va='top',
                       bbox=dict(boxstyle="round,pad=0.2", facecolor='lightblue', alpha=0.7),
                       fontsize=7)
    
    # Customize plot
    ax.set_xlabel('Longitude (°E)', fontsize=12)
    ax.set_ylabel('Latitude (°S)', fontsize=12)
    ax.set_title(f'Lesotho Electrical Network - All {len(network.buses)} Buses\nLoaded from Excel Data (Lat/Lon Coordinates)', 
                fontsize=14, fontweight='bold')
    ax.grid(True, alpha=0.3)
    ax.set_aspect('equal')
    
    # Add legend
    legend_elements = []
    if len(transmission_buses) > 0:
        legend_elements.append(
            plt.Line2D([0], [0], marker='o', color='w', markerfacecolor='red', 
                       markersize=15, label=f'Transmission (≥66 kV) - {len(transmission_buses)} buses')
        )
    if len(distribution_buses) > 0:
        legend_elements.append(
            plt.Line2D([0], [0], marker='o', color='w', markerfacecolor='blue', 
                       markersize=12, label=f'Distribution (<66 kV) - {len(distribution_buses)} buses')
        )
    
    if legend_elements:
        ax.legend(handles=legend_elements, loc='upper right', bbox_to_anchor=(0.98, 0.98))
    
    plt.tight_layout()
    plt.show()
    print("✓ Static network plot created successfully!")
    
    return fig

def create_interactive_network_plot(network):
    """Create interactive plot with hover information for all buses using lat/lon"""
    print(f"\nCreating Interactive Network Visualization with Lat/Lon...")
    
    # Separate buses by voltage level
    transmission_buses = network.buses[network.buses.v_nom >= 66]
    distribution_buses = network.buses[network.buses.v_nom < 66]
    
    # Create figure
    fig = go.Figure()
    
    # Add transmission buses
    if len(transmission_buses) > 0:
        print("Adding transmission buses...")
        trans_hover_info = []
        for bus in transmission_buses.index:
            longitude = transmission_buses.loc[bus, 'x']  # x stores longitude
            latitude = transmission_buses.loc[bus, 'y']   # y stores latitude
            hover_text = (
                f"<b>Bus: {bus}</b><br>"
                f"Voltage Level: {transmission_buses.loc[bus, 'v_nom']} kV<br>"
                f"Type: Transmission<br>"
                f"Coordinates: {latitude:.4f}°S, {longitude:.4f}°E<br>"
                f"Status: Standalone (No connections)"
            )
            trans_hover_info.append(hover_text)
        
        fig.add_trace(go.Scatter(
            x=transmission_buses.x.values,  # longitude
            y=transmission_buses.y.values,  # latitude
            mode='markers+text',
            marker=dict(
                size=20,
                color='red',
                line=dict(width=2, color='darkred'),
                opacity=0.8
            ),
            text=transmission_buses.index.tolist(),
            textposition='top center',
            textfont=dict(size=8, color='darkred'),
            hoverinfo='text',
            hovertext=trans_hover_info,
            name=f'Transmission (≥66 kV) - {len(transmission_buses)} buses',
            showlegend=True
        ))
    
    # Add distribution buses
    if len(distribution_buses) > 0:
        print("Adding distribution buses...")
        dist_hover_info = []
        for bus in distribution_buses.index:
            longitude = distribution_buses.loc[bus, 'x']  # x stores longitude
            latitude = distribution_buses.loc[bus, 'y']   # y stores latitude
            hover_text = (
                f"<b>Bus: {bus}</b><br>"
                f"Voltage Level: {distribution_buses.loc[bus, 'v_nom']} kV<br>"
                f"Type: Distribution<br>"
                f"Coordinates: {latitude:.4f}°S, {longitude:.4f}°E<br>"
                f"Status: Standalone (No connections)"
            )
            dist_hover_info.append(hover_text)
        
        fig.add_trace(go.Scatter(
            x=distribution_buses.x.values,  # longitude
            y=distribution_buses.y.values,  # latitude
            mode='markers+text',
            marker=dict(
                size=15,
                color='blue',
                line=dict(width=2, color='darkblue'),
                opacity=0.8
            ),
            text=distribution_buses.index.tolist(),
            textposition='top center',
            textfont=dict(size=8, color='darkblue'),
            hoverinfo='text',
            hovertext=dist_hover_info,
            name=f'Distribution (<66 kV) - {len(distribution_buses)} buses',
            showlegend=True
        ))
    
    # Update layout
    fig.update_layout(
        title=dict(
            text=f"Interactive Lesotho Electrical Network - {len(network.buses)} Buses<br><sub>Loaded from Excel Data (Lat/Lon) - Hover for details</sub>",
            x=0.5,
            font=dict(size=16)
        ),
        xaxis=dict(
            title="Longitude (°E)",
            showgrid=True,
            gridcolor='lightgray'
        ),
        yaxis=dict(
            title="Latitude (°S)", 
            showgrid=True,
            gridcolor='lightgray',
            scaleanchor='x',
            scaleratio=1
        ),
        hovermode='closest',
        plot_bgcolor='white',
        paper_bgcolor='white',
        width=1200,
        height=900,
        legend=dict(
            x=0.02,
            y=0.98,
            bgcolor="rgba(255,255,255,0.9)",
            bordercolor="black",
            borderwidth=1
        )
    )
    
    print("✓ Interactive network plot created successfully!")
    print("  (Run this code in Jupyter/Python to see interactive Plotly plot)")
    
    return fig

# Create visualizations
print(f"\nCreating Network Visualizations...")
static_fig = create_static_network_plot(network)
interactive_fig = create_interactive_network_plot(network)

print(f"\n" + "="*70)
print("Lesotho Electrical Network Creation Complete!")
print("✓ Static plot displays above (visible in Claude)")
print("✓ Interactive plot ready (run in Jupyter/Python for hover features)")
print(f"✓ Network loaded from Excel data with {len(network.buses)} buses")
print("✓ Using Latitude and Longitude coordinates directly from Excel")
print("✓ Automatic voltage level classification (≥66kV = Transmission, <66kV = Distribution)")
print("✓ Coordinate validation for Lesotho region (-32° to -28°S, 26° to 31°E)")
print("✓ No transmission lines - buses only")
print("\nTo use your Excel file:")
print("1. Change 'excel_file_path' variable to point to your file")
print("2. Ensure Excel has columns for: Bus Name, Voltage, Latitude, Longitude")
print("3. Latitude should be in decimal degrees (negative for South)")
print("4. Longitude should be in decimal degrees (positive for East)")
print("="*70)