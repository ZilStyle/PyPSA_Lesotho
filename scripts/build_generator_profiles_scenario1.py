"""
Status Quo hourly balance for the CENTRAL network only.

Central network = substations electrically connected to Maseru bulk (and Muela / Ramarothole).
Substations fed separately by the Clarens and Letloepe imports are left out of the balance.

For each demand scenario and year:
  residual = central load - Ramarothole solar - Muela hydro
  imports  = residual clipped to [0, 180 MW]   (Maseru bulk)
  unmet    = central load - solar - hydro - imports   (>= 0)

Outputs (results/status_quo/{demand}/):
  unmet_demand_hourly_{year}.csv     hourly load, solar, hydro, imports, unmet (central network)
  generator_profiles_{year}_updated_imports.xlsx   profile with new Maseru bulk column
  status_quo_summary_{demand}.csv    annual totals per year (read by cross_scenario_summary.py)
  central_substations.csv            which load columns were counted as central
"""

import os
from pathlib import Path
import pandas as pd
import numpy as np

# -----------------------------
# SETTINGS
# -----------------------------
DEMANDS = {
    # demand: (generator profile folder, supply-end load folder)
    "BAU":  ("data/generator_profiles_scenario1",      "data/article/load_BAU_supply_end"),
    "M300": ("data/generator_profiles_scenario1_m300", "data/article/load_M300_supply_end"),
}

YEARS = [2025, 2026, 2027, 2028, 2029, 2030, 2035, 2040, 2045, 2050]

BUSES_FILE = "data/planned/m300/buses.xlsx"
LINES_FILE = "data/planned/m300/lines.xlsx"

# Status Quo = existing lines only. Set to None to use every line in lines.xlsx.
EXISTING_LINE_STATUS = ["existing"]

CENTRAL_ROOT = "Maseru bulk"      # bus that defines the central network
# Buses NOT in the central network (fed by separate imports). Used to check the
# topology result, and as the fallback if lines.xlsx connects everything together.
NON_CENTRAL_ROOTS = ["Clarens", "Letloepe"]
# Extra load columns (without "_p") to force out of / into the central network, if needed
FORCE_EXCLUDE = []
FORCE_INCLUDE = []

IMPORT_GEN    = "Maseru bulk"
IMPORT_CAP_MW = 180.0
SOLAR_GEN     = "Ramarothole"
HYDRO_GEN     = "Muela"

PROFILE_SHEET = "Sheet2"
LOAD_SHEET    = "Sheet1"

MORNING_HOURS = range(6, 10)     # 06:00 to 09:59
EVENING_HOURS = range(18, 22)    # 18:00 to 21:59

OUT_ROOT = Path("results/status_quo")

# Set True to also overwrite the original profile files (old behaviour)
OVERWRITE_PROFILES = False


# -----------------------------
# HELPERS
# -----------------------------
def norm(s):
    return " ".join(str(s).strip().lower().split())


def canonical_index_from_year(year):
    return pd.date_range(f"{year}-01-01 00:00", f"{year}-12-31 23:00", freq="h")


def read_dated(path, sheet, year_index):
    df = pd.read_excel(path, sheet_name=sheet)
    if "Date" not in df.columns:
        raise ValueError(f"'Date' column missing in {path}")
    df.columns = [str(c).strip() for c in df.columns]
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce").dt.round("h")
    df = df.dropna(subset=["Date"]).drop_duplicates(subset=["Date"]).set_index("Date").sort_index()
    n_missing = len(year_index.difference(df.index))
    if n_missing:
        print(f"  WARNING: {Path(path).name} is missing {n_missing} hours, filled from previous hour")
    return df.reindex(year_index).ffill().fillna(0.0)


def central_buses():
    """Buses connected to CENTRAL_ROOT through existing lines (connected component)."""
    buses = pd.read_excel(BUSES_FILE)
    lines = pd.read_excel(LINES_FILE)

    if EXISTING_LINE_STATUS is not None and "line_status" in lines.columns:
        keep = lines["line_status"].astype(str).str.strip().str.lower().isin(
            [s.lower() for s in EXISTING_LINE_STATUS])
        print(f"Lines used: {keep.sum()} of {len(lines)} (status in {EXISTING_LINE_STATUS})")
        lines = lines[keep]

    adj = {norm(b): set() for b in buses["BusName"]}
    for _, r in lines.iterrows():
        a, b = norm(r["bus0"]), norm(r["bus1"])
        adj.setdefault(a, set()).add(b)
        adj.setdefault(b, set()).add(a)

    root = norm(CENTRAL_ROOT)
    if root not in adj:
        raise ValueError(f"Central root bus '{CENTRAL_ROOT}' not found in {BUSES_FILE}")

    seen, stack = {root}, [root]
    while stack:
        for nb in adj.get(stack.pop(), ()):
            if nb not in seen:
                seen.add(nb)
                stack.append(nb)

    joined = [r for r in NON_CENTRAL_ROOTS if norm(r) in seen]
    if joined:
        print(f"WARNING: {joined} are connected to {CENTRAL_ROOT} through existing lines.")
        print("         Removing their own connected areas using the non-central roots instead.")
        # fall back: drop everything reachable from the non-central roots without passing the root
        for r in joined:
            sub, stack = {norm(r)}, [norm(r)]
            while stack:
                for nb in adj.get(stack.pop(), ()):
                    if nb not in sub and nb != root:
                        sub.add(nb)
                        stack.append(nb)
            # only remove if this does not swallow the root area
            seen -= sub
    return seen


def split_load_columns(load_df, central):
    p_cols = [c for c in load_df.columns if c.lower().endswith("_p")]
    if not p_cols:
        raise ValueError("No '*_p' columns found in load file")
    inc, exc = [], []
    for c in p_cols:
        name = norm(c[:-2])
        if name in {norm(x) for x in FORCE_EXCLUDE}:
            exc.append(c)
        elif name in {norm(x) for x in FORCE_INCLUDE} or name in central:
            inc.append(c)
        else:
            exc.append(c)
    return inc, exc


def window_stats(series, load, hrs):
    mask = series.index.hour.isin(list(hrs))
    return float(series[mask].max()), float(load[mask].max())


# -----------------------------
# MAIN
# -----------------------------
central = central_buses()
print(f"Central network: {len(central)} buses")

for demand, (profile_dir, load_dir) in DEMANDS.items():
    print(f"\n================ {demand} ================")
    out_dir = OUT_ROOT / demand
    out_dir.mkdir(parents=True, exist_ok=True)
    summary = []

    for year in YEARS:
        year_index = canonical_index_from_year(year)

        prof_path = Path(profile_dir) / f"generator_profiles_scenario1_{year}.xlsx"
        load_path = Path(load_dir) / f"load_timeseries_{year}_supply_end.xlsx"
        if not prof_path.exists() or not load_path.exists():
            print(f"{year}: missing {prof_path if not prof_path.exists() else load_path}, skipped")
            continue

        prof = read_dated(prof_path, PROFILE_SHEET, year_index)
        for col in [SOLAR_GEN, HYDRO_GEN, IMPORT_GEN]:
            if col not in prof.columns:
                raise ValueError(f"Missing column '{col}' in {prof_path}. Columns: {list(prof.columns)}")

        ld = read_dated(load_path, LOAD_SHEET, year_index)
        inc, exc = split_load_columns(ld, central)

        if year == YEARS[0]:
            pd.DataFrame({
                "load_column": inc + exc,
                "central": [True] * len(inc) + [False] * len(exc),
            }).to_csv(out_dir / "central_substations.csv", index=False)
            print(f"Central load columns ({len(inc)}): {', '.join(c[:-2] for c in inc)}")
            print(f"Excluded load columns ({len(exc)}): {', '.join(c[:-2] for c in exc) or 'none'}")

        load_all     = ld[inc + exc].sum(axis=1).astype(float)
        load_central = ld[inc].sum(axis=1).astype(float)

        solar = prof[SOLAR_GEN].astype(float)
        hydro = prof[HYDRO_GEN].astype(float)

        residual = load_central - solar - hydro
        imports  = residual.clip(lower=0.0, upper=IMPORT_CAP_MW)
        unmet    = (load_central - solar - hydro - imports).clip(lower=0.0)
        spill    = (-residual).clip(lower=0.0)     # solar + hydro above central load

        # hourly results
        pd.DataFrame({
            "Date": year_index,
            "load_central": load_central.values,
            "solar": solar.values,
            "hydro": hydro.values,
            "imports": imports.values,
            "unmet": unmet.values,
            "surplus": spill.values,
        }).to_csv(out_dir / f"unmet_demand_hourly_{year}.csv", index=False)

        # updated profile (new imports column)
        prof_out = prof.copy()
        prof_out[IMPORT_GEN] = imports.values
        prof_out.insert(0, "Date", prof_out.index)
        prof_out.to_excel(out_dir / f"generator_profiles_{year}_updated_imports.xlsx",
                          sheet_name=PROFILE_SHEET, index=False)
        if OVERWRITE_PROFILES:
            prof_out.to_excel(prof_path, sheet_name=PROFILE_SHEET, index=False)

        m_unmet, m_peak = window_stats(unmet, load_central, MORNING_HOURS)
        e_unmet, e_peak = window_stats(unmet, load_central, EVENING_HOURS)

        rec = {
            "year": year,
            "load_total_GWh":   load_all.sum() / 1e3,
            "load_central_GWh": load_central.sum() / 1e3,
            "solar_GWh":        solar.sum() / 1e3,
            "hydro_GWh":        hydro.sum() / 1e3,
            "imports_GWh":      imports.sum() / 1e3,
            "unmet_GWh":        unmet.sum() / 1e3,
            "surplus_GWh":      spill.sum() / 1e3,
            "unmet_share":      unmet.sum() / load_central.sum() if load_central.sum() else 0.0,
            "re_share":         (solar.sum() + hydro.sum() - spill.sum()) / load_central.sum()
                                if load_central.sum() else 0.0,
            "imports_share":    imports.sum() / load_central.sum() if load_central.sum() else 0.0,
            "peak_central_MW":  load_central.max(),
            "max_imports_MW":   imports.max(),
            "max_unmet_MW":     unmet.max(),
            "unmet_hours":      int((unmet > 1e-6).sum()),
            "morning_unmet_MW": m_unmet, "morning_peak_MW": m_peak,
            "evening_unmet_MW": e_unmet, "evening_peak_MW": e_peak,
        }
        summary.append(rec)

        print(f"{year}: central load {rec['load_central_GWh']:,.1f} GWh "
              f"(total {rec['load_total_GWh']:,.1f}) | imports {rec['imports_GWh']:,.1f} | "
              f"unmet {rec['unmet_GWh']:,.2f} GWh ({rec['unmet_share']:.2%}) | "
              f"max unmet {rec['max_unmet_MW']:,.1f} MW")

    if summary:
        pd.DataFrame(summary).to_csv(out_dir / f"status_quo_summary_{demand}.csv", index=False)
        print(f"Saved to {out_dir}")

print("\nDone.")