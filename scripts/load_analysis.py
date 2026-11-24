import pandas as pd
import matplotlib.pyplot as plt

# ======================================================
# LOAD 2024 LOAD TIMESERIES
# ======================================================
load_file = "data/load_timeseries_2022_2024.xlsx"

df = pd.read_excel(load_file, sheet_name="Sheet2")
df["Date"] = pd.to_datetime(df["Date"], errors="coerce").dt.round("h")
df = df.dropna(subset=["Date"])
df["year"] = df["Date"].dt.year

# Filter for 2024 only
df_2024 = df[df["year"] == 2024].copy()
df_2024 = df_2024.sort_values("Date").set_index("Date")

# Identify all "_p" columns for active power
p_cols = [c for c in df_2024.columns if c.endswith("_p")]

# Compute total system load per hour
total_load_2024 = df_2024[p_cols].sum(axis=1)

# Peak load
peak_load_value = total_load_2024.max()
peak_load_time = total_load_2024.idxmax()

print("Peak Load:", round(peak_load_value, 2), "MW")
print("Peak Load Time:", peak_load_time)

# ======================================================
# BAR PLOT OF PEAK LOAD
# ======================================================

plt.figure(figsize=(8, 6))

bars = plt.bar(
    ["Peak Load"],
    [peak_load_value],
    color="grey",
    width=0.5
)

# Add value + timestamp above bar
plt.text(
    0,
    peak_load_value,
    f"{peak_load_value:.1f} MW",
    ha="center",
    va="bottom",
    fontsize=12
)

plt.title("Maximum System Load in 2024 (Central Network)\n 2024-07-08 10:00:00", fontsize=12)
plt.ylabel("MW", fontsize=12)
plt.grid(axis="y", alpha=0.3)

plt.tight_layout()
plt.show()
