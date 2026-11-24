import pandas as pd
import numpy as np

# =====================================
# FILE PATH
# =====================================
file = "data/planned/wind data.xlsx"

# =====================================
# LOAD DATA
# =====================================
wind_df = pd.read_excel(file, sheet_name=0)
curve_df = pd.read_excel(file, sheet_name=1)

wind_df.columns = ["time", "wind_speed"]
curve_df.columns = ["wind_speed", "power_kw"]

curve_df = curve_df.dropna()

# =====================================
# CONVERT POWER CURVE TO MW
# =====================================
curve_df["power_MW"] = curve_df["power_kw"] / 1000

curve_v = curve_df["wind_speed"].values
curve_p = curve_df["power_MW"].values

# =====================================
# INTERPOLATE POWER FROM WIND SPEED
# =====================================
v = wind_df["wind_speed"].values

turbine_power = np.interp(v, curve_v, curve_p)

wind_df["turbine_power_MW"] = turbine_power

# =====================================
# CAPACITY FACTOR
# =====================================
rated_power = curve_p.max()   # should be ~3 MW

wind_df["capacity_factor"] = wind_df["turbine_power_MW"] / rated_power

# =====================================
# WIND FARM GENERATION
# =====================================
turbine_rating = 3
farm_capacity = 60

n_turbines = farm_capacity / turbine_rating

wind_df["farm_generation_MW"] = wind_df["turbine_power_MW"] * n_turbines

# =====================================
# ENERGY CALCULATIONS
# =====================================
annual_energy_MWh = wind_df["farm_generation_MW"].sum()
annual_energy_GWh = annual_energy_MWh / 1000

avg_cf = wind_df["capacity_factor"].mean()

print("Turbines:", n_turbines)
print("Rated turbine power:", rated_power, "MW")
print("Average CF:", round(avg_cf,3))
print("Annual Energy:", round(annual_energy_GWh,2), "GWh")

""""# =====================================
# SAVE RESULTS
# =====================================
output = "data/planned/wind_generation_results.csv"
wind_df.to_csv(output, index=False)

print("Saved:", output)"""