import pypsa
import numpy as np
import pandas as pd

# Read your Excel
df = pd.read_excel("C:/Users/Mothala/Documents/BusData.xlsx", sheet_name="load_data")

        # Ensure the first column is datetime
df.iloc[:,0] = pd.to_datetime(df.iloc[:,0], format="%Y-%m-%d %H:%M")
load_data = df.set_index(df.columns[0])
                
        # Read the Excel sheet
             # Read the Excel sheet (no automatic date parsing yet)
        
print(f"Load data shape: {df.shape}")
print(f"Date range: {df.index.min()} to {df.index.max()}")
        
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
    
print(load_data)

