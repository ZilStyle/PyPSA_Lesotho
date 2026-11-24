import pypsa
import pandas as pd
import matplotlib.pyplot as plt

# Create the network
network = pypsa.Network()

# Add a snapshot (time step)
network.set_snapshots(pd.date_range("2025-01-01", periods=1, freq="h"))

# Add two buses
network.add("Bus", "Bus1")
network.add("Bus", "Bus2")

# Add coordinates for plotting (arbitrary positions)
network.buses.at["Bus1", "x"] = 0
network.buses.at["Bus1", "y"] = 0
network.buses.at["Bus2", "x"] = 1
network.buses.at["Bus2", "y"] = 0

# Add a load to Bus2
network.add("Load", "Load2",
            bus="Bus2",
            p_set=100)  # Load of 100 MW

# Add a wind generator at Bus1
network.add("Generator",
            name =  "Solar ☀️ Generator",
            bus="Bus1",
            p_nom_extendable=True,
            capital_cost=500,     # €/MW
            marginal_cost=0,      # €/MWh
            p_max_pu=[0.6],      # 60% capacity factor
            carrier="solar")

# Add a gas generator at Bus2
network.add("Generator", "Gas",
            bus="Bus2",
            p_nom_extendable=True,
            capital_cost=1000,    # €/MW
            marginal_cost=50,     # €/MWh
            p_max_pu=[1.0])       # always available

# Add a custom symbol column
network.generators.loc["Solar ☀️ Generator", "symbol"] = "☀️"

# Add an extendable transmission line between Bus1 and Bus2
network.add("Line", "Line1",
            bus0="Bus1",
            bus1="Bus2",
            x=0.1,                     # reactance
            s_nom_extendable=True,
            capital_cost=200)         # €/MW

# Solve the linear optimal power flow

#network.optimize()

# Print results
#print("Wind capacity built: {:.2f} MW".format(network.generators.at["Wind", "p_nom_opt"]))
#print("Gas capacity built: {:.2f} MW".format(network.generators.at["Gas", "p_nom_opt"]))
#print("Transmission capacity built: {:.2f} MW".format(network.lines.at["Line1", "s_nom_opt"]))

network.plot(title="Simple 2-Bus PyPSA Network")
plt.show()