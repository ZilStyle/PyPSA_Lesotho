import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Circle
import seaborn as sns

# Set style for better looking plots
plt.style.use('seaborn-v0_8')
sns.set_palette("husl")

# Create figure with multiple subplots
fig = plt.figure(figsize=(20, 24))

# Define colors for different voltage levels
voltage_colors = {
    132.0: '#FF6B6B',  # Red for 132kV
    88.0: '#4ECDC4',   # Teal for 88kV  
    66.0: '#45B7D1',   # Blue for 66kV
    33.0: '#96CEB4',   # Green for 33kV
    22.0: '#FFEAA7'    # Yellow for 22kV
}

# Sample data based on your output (you'll replace this with actual Excel data loading)
# Transmission buses data
transmission_buses = {
    'BusName': ['Ramarothole', 'Mohale Dam', 'Mohale Intake', 'Mabote Trans', 'Mazenod Trans',
                'Maputose Trans', 'Lejone', 'Pitseng', 'Litsoeneng', 'Katse Intake',
                'Matsoku Diversion', 'Katse Dam', 'Mohale Outlet', 'Hlotse Adit',
                'Khukhune', 'Mahlasela', 'Letseng'],
    'Voltage': [132.0, 132.0, 132.0, 132.0, 132.0, 132.0, 132.0, 132.0, 132.0,
                66.0, 66.0, 66.0, 66.0, 66.0, 88.0, 88.0, 88.0],
    'Latitude': [-29.8076, -29.3267, -29.4653, -29.2841, -29.4061, -28.9140,
                 -29.1086, -28.9946, -30.1606, -29.1649, -29.2399, -29.3415,
                 -29.3267, -28.9269, -28.7333, -28.8152, -28.9977],
    'Longitude': [27.3352, 28.4099, 28.0931, 27.5382, 27.5628, 27.9150,
                  28.4922, 28.1984, 27.4368, 28.4806, 28.5534, 28.4968,
                  28.4099, 28.0935, 28.4036, 28.7193, 28.8501]
}

# Distribution buses data (sample - add all 28)
distribution_buses = {
    'BusName': ['Mabote Distr', 'Mazenod Distr', 'Botsabelo', 'LEC-Boarder', 'LEC HQ',
                'Pioneer', 'Thetsane', 'Highway', 'Roma', 'Molimo-Nthuse',
                'Thaba-Tseka', 'St. Agnes', 'Maputsoe Distr', 'Ngoajane', 'Botha-Bothe',
                'Muela', 'Hololo', 'Morija', 'Mafeteng', 'Mohale\'s Hoek',
                'Leloaleng', 'Qhacha\'s Nek', 'Tikoe', 'Tsosane', 'Metolong',
                'Maseru Central', 'Ha Mpiti', 'Hlotse'],
    'Voltage': [33.0, 33.0, 33.0, 33.0, 33.0, 33.0, 33.0, 33.0, 33.0, 33.0,
                33.0, 33.0, 33.0, 33.0, 33.0, 33.0, 33.0, 33.0, 33.0, 33.0,
                33.0, 22.0, 33.0, 33.0, 33.0, 33.0, 33.0, 33.0],
    'Latitude': [-29.2841, -29.4087, -29.3447, -29.2961, -29.3001, -29.3195,
                 -29.3456, -29.3123, -29.4491, -29.4244, -29.5195, -29.1491,
                 -28.9140, -28.6804, -28.7576, -28.7766, -28.7393, -29.6164,
                 -29.8095, -30.1486, -30.4040, -30.1293, -29.3772, -29.3110,
                 -29.3328, -29.3102, -30.0713, -28.8516],
    'Longitude': [27.5382, 27.5612, 27.5172, 27.4650, 27.4684, 27.4742,
                  27.4567, 27.5095, 27.7182, 27.8996, 28.6090, 27.7206,
                  27.9150, 28.4578, 28.2580, 28.4500, 28.4557, 27.4979,
                  27.2355, 27.4743, 27.6827, 28.6866, 27.4869, 27.5393,
                  27.7696, 27.4858, 28.6217, 28.0615]
}

# Convert to DataFrames
df_transmission = pd.DataFrame(transmission_buses)
df_distribution = pd.DataFrame(distribution_buses)
df_all = pd.concat([df_transmission, df_distribution], ignore_index=True)

# 1. Main Network Map
ax1 = plt.subplot(3, 3, (1, 2))
for voltage, color in voltage_colors.items():
    mask = df_all['Voltage'] == voltage
    if mask.any():
        size = 150 if voltage >= 66 else 80
        alpha = 0.8 if voltage >= 66 else 0.6
        plt.scatter(df_all[mask]['Longitude'], df_all[mask]['Latitude'], 
                   c=color, s=size, alpha=alpha, 
                   label=f'{voltage}kV ({mask.sum()} buses)', edgecolors='black', linewidth=0.5)

# Add transmission line
plt.plot([27.5382, 27.9150], [-29.2841, -28.9140], 'r-', linewidth=3, alpha=0.7, label='Transmission Line')

plt.xlabel('Longitude (°E)', fontsize=12)
plt.ylabel('Latitude (°S)', fontsize=12)
plt.title('Lesotho Electrical Network Overview\n45 Buses Total', fontsize=14, fontweight='bold')
plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
plt.grid(True, alpha=0.3)

'''# 2. Voltage Level Distribution
ax2 = plt.subplot(3, 3, 3)
voltage_counts = df_all['Voltage'].value_counts().sort_index(ascending=False)
colors = [voltage_colors[v] for v in voltage_counts.index]
bars = plt.bar(range(len(voltage_counts)), voltage_counts.values, color=colors, alpha=0.8, edgecolor='black')
plt.xlabel('Voltage Level (kV)', fontsize=12)
plt.ylabel('Number of Buses', fontsize=12)
plt.title('Bus Count by Voltage Level', fontsize=12, fontweight='bold')
plt.xticks(range(len(voltage_counts)), [f'{int(v)}kV' for v in voltage_counts.index])

# Add value labels on bars
for i, (bar, count) in enumerate(zip(bars, voltage_counts.values)):
    plt.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.5, 
             str(count), ha='center', va='bottom', fontweight='bold')

plt.grid(True, alpha=0.3, axis='y')

# 3. Transmission vs Distribution Pie Chart
ax3 = plt.subplot(3, 3, 4)
transmission_count = len(df_transmission)
distribution_count = len(df_distribution)
sizes = [transmission_count, distribution_count]
labels = [f'Transmission\n(≥66kV)\n{transmission_count} buses', f'Distribution\n(<66kV)\n{distribution_count} buses']
colors_pie = ['#FF6B6B', '#96CEB4']
explode = (0.05, 0.05)

wedges, texts, autotexts = plt.pie(sizes, explode=explode, labels=labels, colors=colors_pie,
                                  autopct='%1.1f%%', shadow=True, startangle=90)
plt.title('Network Classification', fontsize=12, fontweight='bold')

# 4. Geographic Distribution - Latitude
ax4 = plt.subplot(3, 3, 5)
plt.hist(df_transmission['Latitude'], bins=8, alpha=0.7, color='#FF6B6B', 
         label=f'Transmission ({len(df_transmission)})', edgecolor='black')
plt.hist(df_distribution['Latitude'], bins=8, alpha=0.7, color='#96CEB4', 
         label=f'Distribution ({len(df_distribution)})', edgecolor='black')
plt.xlabel('Latitude (°S)', fontsize=12)
plt.ylabel('Number of Buses', fontsize=12)
plt.title('Latitudinal Distribution', fontsize=12, fontweight='bold')
plt.legend()
plt.grid(True, alpha=0.3)

# 5. Geographic Distribution - Longitude
ax5 = plt.subplot(3, 3, 6)
plt.hist(df_transmission['Longitude'], bins=8, alpha=0.7, color='#FF6B6B', 
         label=f'Transmission ({len(df_transmission)})', edgecolor='black')
plt.hist(df_distribution['Longitude'], bins=8, alpha=0.7, color='#96CEB4', 
         label=f'Distribution ({len(df_distribution)})', edgecolor='black')
plt.xlabel('Longitude (°E)', fontsize=12)
plt.ylabel('Number of Buses', fontsize=12)
plt.title('Longitudinal Distribution', fontsize=12, fontweight='bold')
plt.legend()
plt.grid(True, alpha=0.3)'''
'''
# 6. Detailed Transmission Network
ax6 = plt.subplot(3, 3, 7)
for voltage in [132.0, 88.0, 66.0]:
    mask = df_transmission['Voltage'] == voltage
    if mask.any():
        size = 200 if voltage == 132.0 else 150 if voltage == 88.0 else 100
        plt.scatter(df_transmission[mask]['Longitude'], df_transmission[mask]['Latitude'], 
                   c=voltage_colors[voltage], s=size, alpha=0.8, 
                   label=f'{voltage}kV ({mask.sum()})', edgecolors='black', linewidth=1)

# Add transmission line
plt.plot([27.5382, 27.9150], [-29.2841, -28.9140], 'r-', linewidth=3, alpha=0.8)

# Add bus labels for transmission
for idx, row in df_transmission.iterrows():
    plt.annotate(row['BusName'], (row['Longitude'], row['Latitude']), 
                xytext=(5, 5), textcoords='offset points', fontsize=8, alpha=0.8)

plt.xlabel('Longitude (°E)', fontsize=12)
plt.ylabel('Latitude (°S)', fontsize=12)
plt.title('Transmission Network Detail\n(≥66kV)', fontsize=12, fontweight='bold')
plt.legend()
plt.grid(True, alpha=0.3)

# 7. Network Statistics Table
ax7 = plt.subplot(3, 3, 8)
ax7.axis('off')

# Create statistics
stats_data = [
    ['Total Buses', '45'],
    ['Transmission Buses (≥66kV)', '17'],
    ['Distribution Buses (<66kV)', '28'],
    ['132kV Buses', str(sum(df_all['Voltage'] == 132.0))],
    ['88kV Buses', str(sum(df_all['Voltage'] == 88.0))],
    ['66kV Buses', str(sum(df_all['Voltage'] == 66.0))],
    ['33kV Buses', str(sum(df_all['Voltage'] == 33.0))],
    ['22kV Buses', str(sum(df_all['Voltage'] == 22.0))],
    ['Transmission Lines', '1'],
    ['Lat Range', f'{df_all["Latitude"].min():.2f}° to {df_all["Latitude"].max():.2f}°S'],
    ['Lon Range', f'{df_all["Longitude"].min():.2f}° to {df_all["Longitude"].max():.2f}°E']
]

table = plt.table(cellText=stats_data, 
                 colLabels=['Parameter', 'Value'],
                 cellLoc='left',
                 loc='center',
                 colWidths=[0.6, 0.4])
table.auto_set_font_size(False)
table.set_fontsize(10)
table.scale(1, 2)

# Style the table
for i in range(len(stats_data) + 1):
    for j in range(2):
        cell = table[(i, j)]
        if i == 0:  # Header
            cell.set_facecolor('#4ECDC4')
            cell.set_text_props(weight='bold', color='white')
        else:
            cell.set_facecolor('#F8F9FA' if i % 2 == 0 else 'white')
        cell.set_edgecolor('gray')

plt.title('Network Statistics', fontsize=12, fontweight='bold', pad=20)

# 8. Bus Density Heatmap
ax8 = plt.subplot(3, 3, 9)

# Create a grid for density calculation
lat_bins = np.linspace(df_all['Latitude'].min(), df_all['Latitude'].max(), 10)
lon_bins = np.linspace(df_all['Longitude'].min(), df_all['Longitude'].max(), 10)

# Calculate 2D histogram
H, xedges, yedges = np.histogram2d(df_all['Longitude'], df_all['Latitude'], bins=[lon_bins, lat_bins])

# Create heatmap
im = plt.imshow(H.T, origin='lower', extent=[lon_bins[0], lon_bins[-1], lat_bins[0], lat_bins[-1]], 
                cmap='YlOrRd', alpha=0.7)
plt.colorbar(im, label='Bus Density')

# Overlay bus locations
plt.scatter(df_all['Longitude'], df_all['Latitude'], c='black', s=20, alpha=0.8)

plt.xlabel('Longitude (°E)', fontsize=12)
plt.ylabel('Latitude (°S)', fontsize=12)
plt.title('Bus Density Heatmap', fontsize=12, fontweight='bold')

plt.tight_layout()
plt.suptitle('Lesotho Electrical Network - Comprehensive Analysis', 
             fontsize=16, fontweight='bold', y=0.98)

plt.show()

# Additional detailed plots
fig2, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))

# Voltage level analysis by region
ax1.scatter(df_all['Longitude'], df_all['Voltage'], c=df_all['Latitude'], 
           cmap='viridis', s=100, alpha=0.7, edgecolors='black')
ax1.set_xlabel('Longitude (°E)')
ax1.set_ylabel('Voltage Level (kV)')
ax1.set_title('Voltage Levels vs Geographic Position')
ax1.grid(True, alpha=0.3)
cbar1 = plt.colorbar(ax1.collections[0], ax=ax1)
cbar1.set_label('Latitude (°S)')

# Bus names by voltage level
ax2.axis('off')
voltage_groups = df_all.groupby('Voltage')
y_pos = 0.9
for voltage, group in voltage_groups:
    ax2.text(0.05, y_pos, f'{voltage}kV Buses:', fontweight='bold', fontsize=12, 
             color=voltage_colors[voltage], transform=ax2.transAxes)
    y_pos -= 0.05
    for bus_name in group['BusName'][:5]:  # Show first 5 buses per voltage level
        ax2.text(0.1, y_pos, f'• {bus_name}', fontsize=10, transform=ax2.transAxes)
        y_pos -= 0.04
    if len(group) > 5:
        ax2.text(0.1, y_pos, f'... and {len(group)-5} more', fontsize=10, 
                style='italic', transform=ax2.transAxes)
    y_pos -= 0.06

ax2.set_title('Bus Listing by Voltage Level', fontsize=12, fontweight='bold')

# Distance analysis
ax3.hist(np.sqrt((df_all['Latitude'] - df_all['Latitude'].mean())**2 + 
                (df_all['Longitude'] - df_all['Longitude'].mean())**2), 
         bins=15, alpha=0.7, color='skyblue', edgecolor='black')
ax3.set_xlabel('Distance from Network Center (degrees)')
ax3.set_ylabel('Number of Buses')
ax3.set_title('Bus Distribution from Network Center')
ax3.grid(True, alpha=0.3)

# Voltage level pie chart with percentages
ax4.pie(voltage_counts.values, labels=[f'{int(v)}kV\n({count} buses)' for v, count in zip(voltage_counts.index, voltage_counts.values)],
        colors=[voltage_colors[v] for v in voltage_counts.index],
        autopct='%1.1f%%', startangle=90, explode=[0.05]*len(voltage_counts))
ax4.set_title('Detailed Voltage Level Distribution')
'''
plt.tight_layout()
plt.suptitle('Lesotho Electrical Network - Detailed Analysis', 
             fontsize=14, fontweight='bold', y=0.98)

plt.show()

print("="*70)
print("LESOTHO ELECTRICAL NETWORK - MATPLOTLIB VISUALIZATION COMPLETE")
print("="*70)
print(f"✓ Generated comprehensive visualizations for {len(df_all)} buses")
print(f"✓ Network includes {len(df_transmission)} transmission and {len(df_distribution)} distribution buses")
print(f"✓ Voltage levels: {sorted(df_all['Voltage'].unique(), reverse=True)} kV")
print(f"✓ Geographic coverage: {df_all['Latitude'].min():.2f}° to {df_all['Latitude'].max():.2f}°S")
print(f"✓                     {df_all['Longitude'].min():.2f}° to {df_all['Longitude'].max():.2f}°E")
print("✓ Multiple visualization types: Network map, statistics, distributions, heatmap")
print("="*70)