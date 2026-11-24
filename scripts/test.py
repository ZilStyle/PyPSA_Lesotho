import pypsa
import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import networkx as nx
import rasterio

# Create a new PyPSA network
network = pypsa.Network()

def analyze_network_islands(network):
    """
    Analyze network connectivity and identify disconnected islands
    """
    print("\n" + "="*80)
    print("NETWORK ISLAND ANALYSIS")
    print("="*80)
    
    # Create a graph representation
    G = nx.Graph()
    
    # Add all buses as nodes
    for bus in network.buses.index:
        G.add_node(bus)
    
    # Add all lines as edges
    for line_name in network.lines.index:
        line = network.lines.loc[line_name]
        bus0 = line['bus0']
        bus1 = line['bus1']
        
        # Only add edge if both buses exist
        if bus0 in network.buses.index and bus1 in network.buses.index:
            G.add_edge(bus0, bus1, line=line_name)
    
    # Find connected components (islands)
    islands = list(nx.connected_components(G))
    
    print(f"Number of disconnected islands: {len(islands)}")
    print()
    
    # Analyze each island
    for i, island in enumerate(islands, 1):
        island_buses = list(island)
        print(f"ISLAND {i} ({len(island_buses)} buses):")
        print("-" * 40)
        
        # List buses in this island
        print("Buses:")
        for bus in sorted(island_buses):
            voltage = network.buses.loc[bus, 'v_nom']
            print(f"  - {bus} ({voltage:.0f} kV)")
        
        # Check generators in this island
        island_gens = network.generators[network.generators['bus'].isin(island_buses)]
        if len(island_gens) > 0:
            print("\nGenerators:")
            total_gen_capacity = 0
            for gen_name, gen in island_gens.iterrows():
                print(f"  - {gen_name}: {gen['p_nom']:.0f}MW at {gen['bus']} ({gen['control']})")
                total_gen_capacity += gen['p_nom']
            print(f"  Total generation capacity: {total_gen_capacity:.0f}MW")
        else:
            print("\n❌ NO GENERATORS in this island!")
        
        # Check loads in this island
        island_loads = network.loads[network.loads['bus'].isin(island_buses)]
        if len(island_loads) > 0:
            print("\nLoads:")
            total_load = 0
            for load_name, load in island_loads.iterrows():
                bus_name = load['bus']
                p_set = load.get('p_set', 0)
                q_set = load.get('q_set', 0)
                print(f"  - {load_name}: P={p_set:.2f}MW, Q={q_set:.2f}MVar at {bus_name}")
                total_load += p_set
            print(f"  Total load: {total_load:.2f}MW")
        else:
            print("\nNo loads in this island")
        
        # Check lines in this island
        island_subgraph = G.subgraph(island_buses)
        island_lines = []
        for edge in island_subgraph.edges(data=True):
            if 'line' in edge[2]:
                island_lines.append(edge[2]['line'])
        
        print(f"\nLines in island: {len(island_lines)}")
        for line_name in sorted(island_lines):
            line = network.lines.loc[line_name]
            print(f"  - {line_name}: {line['bus0']} ↔ {line['bus1']}")
        
        print()
    
    return islands

def find_missing_connections(network, islands):
    """
    Suggest connections to link disconnected islands
    """
    print("\n" + "="*80)
    print("SUGGESTED CONNECTIONS TO LINK ISLANDS")
    print("="*80)
    
    if len(islands) <= 1:
        print("✓ Network is fully connected - no additional connections needed!")
        return
    
    # Find buses that could connect islands
    print("To connect the disconnected islands, you need transmission lines between:")
    print()
    
    # Look for buses that might logically connect
    island_buses = [list(island) for island in islands]
    
    for i in range(len(island_buses)):
        for j in range(i+1, len(island_buses)):
            island_i = island_buses[i]
            island_j = island_buses[j]
            
            print(f"CONNECTION NEEDED between Island {i+1} and Island {j+1}:")
            print(f"  Island {i+1} buses: {', '.join(sorted(island_i))}")
            print(f"  Island {j+1} buses: {', '.join(sorted(island_j))}")
            
            # Suggest high voltage buses for connection
            island_i_hv = [bus for bus in island_i if network.buses.loc[bus, 'v_nom'] >= 132]
            island_j_hv = [bus for bus in island_j if network.buses.loc[bus, 'v_nom'] >= 132]
            
            if island_i_hv and island_j_hv:
                print(f"  Suggested connection points:")
                print(f"    From Island {i+1}: {', '.join(island_i_hv)} (132+ kV)")
                print(f"    To Island {j+1}: {', '.join(island_j_hv)} (132+ kV)")
            print()

def check_generation_balance(network, islands):
    """
    Check if each island has sufficient generation
    """
    print("\n" + "="*80)
    print("GENERATION-LOAD BALANCE BY ISLAND")
    print("="*80)
    
    for i, island in enumerate(islands, 1):
        island_buses = list(island)
        
        # Calculate total generation in island
        island_gens = network.generators[network.generators['bus'].isin(island_buses)]
        total_gen = island_gens['p_nom'].sum()
        
        # Calculate total load in island
        island_loads = network.loads[network.loads['bus'].isin(island_buses)]
        # Get load from time series data (first snapshot)
        first_snapshot = network.snapshots[0]
        total_load = 0
        if not network.loads_t.p_set.empty:
            for load_name in island_loads.index:
                if load_name in network.loads_t.p_set.columns:
                    total_load += network.loads_t.p_set.loc[first_snapshot, load_name]
        
        print(f"ISLAND {i}:")
        print(f"  Generation capacity: {total_gen:.2f} MW")
        print(f"  Load demand: {total_load:.2f} MW")
        
        if total_gen == 0:
            print(f"  ❌ NO GENERATION - Island cannot be energized!")
        elif total_load > total_gen:
            print(f"  ❌ INSUFFICIENT GENERATION - Deficit: {total_load - total_gen:.2f} MW")
        elif total_load == 0:
            print(f"  ⚠️  NO LOAD - Island has generation but no demand")
        else:
            print(f"  ✓ Adequate generation - Surplus: {total_gen - total_load:.2f} MW")
        print()

def run_full_connectivity_analysis(network):
    """Run complete connectivity analysis"""
    
    # Analyze network islands
    islands = analyze_network_islands(network)
    
    # Find missing connections
    find_missing_connections(network, islands)
    
    # Check generation balance
    check_generation_balance(network, islands)
    
    return islands

def read_load_data_from_excel(file_path, sheet_name='load_data'):
    """
    Read load data from Excel file with bus_p, bus_q column format.
    """
    
    try:
        print(f"Reading load data from Excel file: {file_path}, sheet: {sheet_name}")
        
        # Read the Excel sheet (no automatic date parsing yet)
        df = pd.read_excel(file_path, sheet_name=sheet_name, index_col=0)
        
        # Force parse the index to datetime with strict format
        df.index = pd.to_datetime(df.index, format="%Y-%m-%d %H:%M", errors="coerce")
        
        print(f"Load data shape: {df.shape}")
        print(f"Date range: {df.index.min()} to {df.index.max()}")
        print(f"Sample timestamps from load data:")
        print(f"  First: {df.index[0]}")
        print(f"  Second: {df.index[1]}")
        print(f"  Last: {df.index[-1]}")
        
        # Separate active power (P) and reactive power (Q) columns
        p_columns = [col for col in df.columns if col.endswith('_p')]
        q_columns = [col for col in df.columns if col.endswith('_q')]
        
        print(f"Found {len(p_columns)} active power columns and {len(q_columns)} reactive power columns")
        
        # Extract active power data and clean column names
        loads_p = df[p_columns].copy()
        loads_p.columns = [col.replace('_p', '') for col in loads_p.columns]
        
        # Extract reactive power data and clean column names  
        loads_q = df[q_columns].copy()
        loads_q.columns = [col.replace('_q', '') for col in loads_q.columns]
        
        print(f"Processed bus names: {list(loads_p.columns)}")
        
        return loads_p, loads_q
        
    except FileNotFoundError:
        print(f"Error: Excel file '{file_path}' not found!")
        return None, None
    except Exception as e:
        print(f"Error reading load data from Excel: {str(e)}")
        return None, None

def load_bus_data_from_excel(file_path):
    """Load bus data from Excel file"""
    try:
        print(f"Loading bus data from Excel file: {file_path}")
        
        # Try to read the Excel file
        bus_data = pd.read_excel(file_path,sheet_name='station')
        
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
    """
    try:
        df = pd.read_excel(file_path,sheet_name='transmission')
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
        
        # Print line details
        circuit_type = "Double Circuit" if row['num_parallel'] == 2 else "Single Circuit"
        print(f"Line {row['Line_id']:2d}: {row['bus0']} → {row['bus1']}")
        print(f"         {circuit_type}, {row['v_nom']}kV, {row['length']}km")
        print(f"         Z = {row['r']:.3f} + j{row['x']:.3f} Ω/km")
        print(f"         S_nom = {row['s_nominal']} MVA\n")

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
       
    # Add Solar Generator at Ramarothole - NO CONTROL SET HERE
    print("\nAdding Solar Generator at Ramarothole...")
    network.add("Generator",
                name="Solar_Ramarothole",
                bus="Ramarothole",
                p_nom=30,  # 30 MW nominal capacity
                marginal_cost=0,  # Solar has zero marginal cost
                carrier="solar",
                efficiency=0.95)
    
    print("✓ Solar Generator Added:")
    print(f"  Location: Ramarothole (132 kV)")
    print(f"  Capacity: 30 MW")
    print(f"  Type: Solar PV")
    print(f"  Marginal Cost: $0/MWh")
    
    # Add Hydro Generator at Muela - NO CONTROL SET HERE
    print("\nAdding Hydro Generator at Muela...")
    network.add("Generator",
                name="Hydro_Muela", 
                bus="Muela",
                p_nom=72,  # 72 MW nominal capacity (typical for Muela)
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

def add_loads_to_network(network, loads_p, loads_q):
    """
    Add loads to the PyPSA network and assign time series data
    """
    
    if loads_p is None or loads_q is None:
        print("No load data to add to network")
        return False
    
    print(f"\nADDING LOADS TO NETWORK:")
    print("=" * 40)

    # Set network snapshots to match load data - THIS IS THE KEY FIX
    print(f"Setting network snapshots to match load data...")
    network.set_snapshots(loads_p.index)
    print(f"✓ Set network snapshots: {len(network.snapshots)} time steps")
    print(f"  First snapshot: {network.snapshots[0]}")
    print(f"  Last snapshot: {network.snapshots[-1]}")
    
    loads_added = 0
    
    # Add load components for each bus that has load data
    for bus_name in loads_p.columns:
        if bus_name in network.buses.index:
            # Add load component
            load_name = f"Load_{bus_name}"
            network.add("Load", 
                       name=load_name,
                       bus=bus_name,
                       p_set=loads_p[bus_name].iloc[0],  # Use first timestep as base
                       q_set=loads_q[bus_name].iloc[0])  # Use first timestep as base
            
            loads_added += 1
            print(f"✓ Added load at {bus_name}: P={loads_p[bus_name].iloc[0]:.3f}MW, Q={loads_q[bus_name].iloc[0]:.3f}MVar")
        else:
            print(f"Warning: Bus '{bus_name}' not found in network - skipping load data")
    
    # Assign time series data
    if loads_added > 0:
        print(f"\nAssigning time series load data...")
        
        # Filter load data to only include buses that exist in network
        valid_buses = [bus for bus in loads_p.columns if bus in network.buses.index]
        network_loads_p = loads_p[valid_buses]
        network_loads_q = loads_q[valid_buses]
        
        # Rename columns to match load component names
        network_loads_p.columns = [f"Load_{bus}" for bus in network_loads_p.columns]
        network_loads_q.columns = [f"Load_{bus}" for bus in network_loads_q.columns]
        
        # Assign to network
        network.loads_t.p_set = network_loads_p
        network.loads_t.q_set = network_loads_q
        
        print(f"✓ Time series data assigned for {len(valid_buses)} loads")
        print(f"  Time range: {network_loads_p.index.min()} to {network_loads_p.index.max()}")
        print(f"  Time steps: {len(network_loads_p)}")
        
        # Show load summary
        total_p_avg = network_loads_p.mean().sum()
        total_q_avg = network_loads_q.mean().sum()
                # network.loads_t.p or your DataFrame of loads indexed by snapshots with columns=buses
        total_p_peak = network_loads_p.sum(axis=1).max()
        total_q_peak = network_loads_q.sum(axis=1).max()

        total_p_total = network_loads_p.sum().sum()
        total_q_total = network_loads_q.sum().sum()

        
        print(f"\nLoad Summary:")
        print(f"  Average Total Load: {total_p_avg:.3f} MW, {total_q_avg:.3f} MVar")
        print(f"  Peak Total Load: {total_p_peak:.3f} MW, {total_q_peak:.3f} MVar")
        print(f"  Total Load: {total_p_total:.3f} MW, {total_q_total:.3f} MVar")
    
    return loads_added > 0

def define_carriers(network):
    """Define all carriers to remove warnings."""
    
    print("\nDEFINING CARRIERS:")
    print("=" * 40)
    
    # Define carrier types
    carriers = {
        'solar': {'color': 'yellow', 'nice_name': 'Solar Power'},
        'hydro': {'color': 'blue', 'nice_name': 'Hydro Power'}, 
        'external': {'color': 'grey', 'nice_name': 'External Grid'},
        'AC': {'color': 'red', 'nice_name': 'AC Transmission'}  # For lines
    }
    
    # Add carriers to network
    for carrier_name, carrier_attrs in carriers.items():
        if carrier_name not in network.carriers.index:
            network.add("Carrier", carrier_name, **carrier_attrs)
            print(f"Added carrier: {carrier_name}")
    
    # Assign carriers to components
    print("\nASSIGNING CARRIERS TO COMPONENTS:")
    
    # Assign line carriers
    for line_name in network.lines.index:
        network.lines.loc[line_name, 'carrier'] = 'AC'
    
    # Assign bus carriers (you might want to customize this)
    for bus_name in network.buses.index:
        if 'Trans' in bus_name:
            network.buses.loc[bus_name, 'carrier'] = 'AC'
        elif 'bulk' in bus_name:
            network.buses.loc[bus_name, 'carrier'] = 'AC'
        else:
            network.buses.loc[bus_name, 'carrier'] = 'AC'
    
    print("All carriers assigned successfully!")

def setup_power_flow(network, pvsyst_profiles_dir="C:/Users/Mothala/Documents"):
    """Set up the network for power flow analysis with PVsyst solar and hydro profiles from Excel.
       External Grid at Maseru bulk acts as Slack.
    """
    define_carriers(network)
    print(f"\nSETTING UP POWER FLOW:")
    print("=" * 40)
    
    if len(network.generators) == 0:
        print("ERROR: No generators found! Adding default generators...")
        add_generators(network)
    
    # Set all generators to PV control first
    network.generators.loc[:, "control"] = "PV"
    
    # --- External Grid at Maseru bulk as Slack ---
    if "External_Grid_Maseru" not in network.generators.index:
        network.add("Generator",
                    name="External_Grid_Maseru",
                    bus="Maseru bulk",
                    p_nom=200,        # large enough import capacity
                    marginal_cost=50.0,  # assumed import cost
                    p_max_pu=1.0,
                    control="Slack",
                    carrier="external")
        print("Added External Grid at Maseru bulk as Slack")
    else:
        network.generators.loc["External_Grid_Maseru", "control"] = "Slack"
        print("Set External Grid at Maseru bulk as Slack")
    
    slack_bus = "Maseru bulk"
    
    # Ensure Muela is not slack anymore
    if "Hydro_Muela" in network.generators.index:
        network.generators.loc["Hydro_Muela", "control"] = "PV"
    
    # Set voltage reference for slack bus
    if slack_bus in network.buses.index:
        network.buses.loc[slack_bus, 'v_mag_pu_set'] = 1.0
        print(f"Set voltage reference for slack bus {slack_bus}: 1.0 pu")
    
    # --- Generator profiles ---
    if hasattr(network, 'snapshots') and len(network.snapshots) > 0:
        print("Setting up generator time series profiles...")
        
        if network.generators_t.p_max_pu.empty:
            network.generators_t.p_max_pu = pd.DataFrame(
                index=network.snapshots,
                columns=network.generators.index,
                dtype=float
            )
        
        for gen_name in network.generators.index:
            gen = network.generators.loc[gen_name]
            
            profile_file = os.path.join(pvsyst_profiles_dir, f"{gen_name}.xlsx")
            
            # Solar profiles
            if gen['carrier'] == 'solar' and os.path.exists(profile_file):
                try:
                    pv_data = pd.read_excel(profile_file)
                    pv_data["Date"] = pd.to_datetime(pv_data["Date"])
                    pv_data = pv_data.set_index("Date")
                    
                    pv_profile = pv_data["Grid"] / 1000  # kW → MW
                    pv_profile = pv_profile.reindex(network.snapshots, method="nearest").fillna(0)
                    
                    network.generators_t.p_max_pu[gen_name] = pv_profile / gen['p_nom']
                    print(f"  Loaded PVsyst profile for {gen_name} from {profile_file}")
                except Exception as e:
                    print(f"  ERROR loading {gen_name} profile: {e}")
                    _fallback_solar(network, gen_name)
            
            # Hydro Muela profile
            elif gen_name == "Hydro_Muela" and os.path.exists(profile_file):
                try:
                    muela_data = pd.read_excel(profile_file)
                    muela_data["Date"] = pd.to_datetime(muela_data["Date"])
                    muela_data = muela_data.set_index("Date")
                    

                    muela_profile = muela_data["Grid"]
                    muela_profile = muela_profile.reindex(network.snapshots, method="nearest").fillna(0)
                    
                    network.generators_t.p_max_pu[gen_name] = muela_profile / gen['p_nom']
                    print(f"  Loaded generation profile for Hydro_Muela from {profile_file}")
                except Exception as e:
                    print(f"  ERROR loading Hydro_Muela profile: {e}")
                    network.generators_t.p_max_pu[gen_name] = 1.0
               
    print(f"\nNetwork Summary:")
    print(f"  Buses: {len(network.buses)}")
    print(f"  Lines: {len(network.lines)}")
    print(f"  Generators: {len(network.generators)}")
    print(f"  Loads: {len(network.loads)}")
    print(f"  Snapshots: {len(network.snapshots)}")
    
    print(pv_profile.head())
    print(muela_profile.head())
    print(network.snapshots[:5])

    print(f"\nGenerator Control Settings:")
    for gen_name in network.generators.index:
        control = network.generators.loc[gen_name, 'control']
        bus = network.generators.loc[gen_name, 'bus']
        print(f"  {gen_name} at {bus}: {control}")
    
    return True


def _fallback_solar(network, gen_name):
    hours = pd.to_datetime(network.snapshots).hour
    solar_profile = np.maximum(0, np.cos((hours - 12) * np.pi / 12))
    solar_profile = np.where((hours >= 6) & (hours <= 18), solar_profile, 0)
    network.generators_t.p_max_pu[gen_name] = solar_profile
    print(f"  Used fallback synthetic solar profile for {gen_name}")

# ========================================================================
# MAIN EXECUTION
# ========================================================================

# Try to load bus data from Excel file
excel_file_path = r"C:/Users/Mothala/Documents/BusData.xlsx"

bus_data = load_bus_data_from_excel(excel_file_path)
success = add_buses_from_dataframe(network, bus_data)

lines_df = read_lines_from_excel(excel_file_path)
add_lines_from_dataframe(network, lines_df)

if not success:
    print("NO BUS DATA LOADED...")

# Add generators to the network
add_generators(network)

# Read and add load data to the network - THIS SETS THE SNAPSHOTS
print(f"\nREADING LOAD DATA:")
print("=" * 40)
loads_p, loads_q = read_load_data_from_excel(excel_file_path, sheet_name='load_data')
add_loads_to_network(network, loads_p, loads_q)

# Display network summary
print(f"\nNETWORK SUMMARY:")
print("-" * 25)
print(f"Total Buses: {len(network.buses)}")
print(f"Total Lines: {len(network.lines)}")
print(f"Total Generators: {len(network.generators)}")
print(f"Total Loads: {len(network.loads)}")

# Setup power flow
setup_power_flow(network)

# Add temporary connections to fix network islands (FOR TESTING ONLY)
print(f"\nADDING TEMPORARY CONNECTIONS TO FIX NETWORK CONNECTIVITY:")
print("=" * 60)


#os.makedirs("network", exist_ok=True)  # creates folder if it does not exist
network.export_to_netcdf("Lesotho.nc")





