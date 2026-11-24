"""
Cross-scenario summary table (Table 7), built from model results.

Columns:
  Status Quo                    : status_quo_balance.py (central network hourly balance, 180 MW import cap)
  Mission 300 Supply            : Option A (fixed planned capacity, dispatch only)
  Planned Generation Expansion  : Option B (capacity expansion)
each for BAU and M300 demand.

Option A and B values are read from:
  networks/{demand}/{option}/solved_{year}.nc
  results/{demand}/B/cost_analysis/cost_summary_clean_{demand}.csv   (from cost_summary_plots.py)

Run from the project root after:  snakemake -j 8 all  (or all_A + all_B)  and  cost_summary_plots.py
"""

from pathlib import Path
import pandas as pd
import pypsa
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

# =========================================================
# SETTINGS
# =========================================================
YEAR    = 2050
DEMANDS = ["BAU", "M300"]

# Supply case -> model option.  Change here if your mapping differs.
CASES = [
    ("Status Quo",                   None),   # status_quo_balance.py results (SQ_DIR)
    ("Mission 300 Supply",           "A"),
    ("Planned Generation Expansion", "B"),
]

MORNING_HOURS = range(6, 10)     # 06:00 to 09:59
EVENING_HOURS = range(18, 22)    # 18:00 to 21:59 (same window as the peak import cap)

RE_CARRIERS     = ["solar", "wind", "hydro", "hydro_peaking"]
NON_CAP_CARRIERS = ["imports", "export", "load_shedding"]   # not counted as installed capacity

OUT_FILE = Path("results/cross_scenario_summary.xlsx")

# Status Quo results written by status_quo_balance.py
SQ_DIR = Path("results/status_quo")      # -> results/status_quo/{demand}/status_quo_summary_{demand}.csv
IMPORT_CAP_SQ = 180.0   # Status Quo import cap (Maseru bulk), as in status_quo_balance.py

# Key limitation is a judgement, so it stays as text you write.
KEY_LIMITATION = {
    ("Status Quo", "BAU"):                   ("Import cap binding;\nno new capacity", "bad"),
    ("Status Quo", "M300"):                  ("Supply deficit;\nunmet demand grows", "bad"),
    ("Mission 300 Supply", "BAU"):           ("Fixed capacity, cannot\nadapt to demand growth", "warn"),
    ("Mission 300 Supply", "M300"):          ("Still import-reliant\nunder high demand", "warn"),
    ("Planned Generation Expansion", "BAU"): ("Transmission costs exclude\ntransformer upgrades", "warn"),
    ("Planned Generation Expansion", "M300"):("Costs rise with\nhigher demand", "warn"),
}

METRICS = [
    "Total demand", "Installed capacity", "Renewable share", "Imports", "Exports",
    "Morning peak unmet", "Evening peak unmet", "Unmet energy", "Battery storage",
    "Net system cost", "Most favourable year",
]
METRIC_LABELS = {
    "Total demand":         f"Total demand by {YEAR}",
    "Installed capacity":   f"Installed generation capacity by {YEAR}",
    "Renewable share":      f"Renewable share of demand by {YEAR}",
    "Imports":              f"Imports by {YEAR}",
    "Exports":              f"Exports by {YEAR}",
    "Morning peak unmet":   f"Morning peak unmet demand by {YEAR}",
    "Evening peak unmet":   f"Evening peak unmet demand by {YEAR}",
    "Unmet energy":         f"% unmet energy by {YEAR}",
    "Battery storage":      f"Battery storage capacity by {YEAR}",
    "Net system cost":      f"Net system cost in {YEAR} (USD)",
    "Most favourable year": "Lowest net cost year",
}


# =========================================================
# METRICS FROM A SOLVED NETWORK
# =========================================================
def energy_GWh(df, w):
    """Sum of MW time series x snapshot weighting, in GWh, per column."""
    return df.mul(w, axis=0).sum() / 1e3


def network_metrics(n):
    w = n.snapshot_weightings.generators
    gens = n.generators
    p = n.generators_t.p
    hours = p.index.hour

    def carrier_cols(carriers):
        return gens.index[gens.carrier.isin(carriers)].intersection(p.columns)

    # demand
    load = n.loads_t.p_set.sum(axis=1)
    demand_GWh = float((load * w).sum() / 1e3)

    # generation by carrier
    gen_GWh = energy_GWh(p, w).groupby(gens.carrier).sum()

    re_GWh     = float(gen_GWh.reindex(RE_CARRIERS).fillna(0).sum())
    imp_GWh    = float(gen_GWh.get("imports", 0.0))
    exp_GWh    = float(-gen_GWh.get("export", 0.0))
    ls_GWh     = float(gen_GWh.get("load_shedding", 0.0))

    # installed capacity (p_nom_opt after solve; p_nom if not extendable)
    cap = gens.p_nom_opt.where(gens.p_nom_opt.notna(), gens.p_nom)
    cap_by_carrier = cap[~gens.carrier.isin(NON_CAP_CARRIERS)].groupby(gens.carrier).sum()
    installed_MW = float(cap_by_carrier.sum())

    # unmet demand in peak windows (max hourly load shedding)
    ls = p[carrier_cols(["load_shedding"])].sum(axis=1)
    imp = p[carrier_cols(["imports"])].sum(axis=1)

    def window(hrs):
        mask = pd.Index(hours).isin(list(hrs))
        return {
            "unmet_MW":   float(ls[mask].max()) if mask.any() else 0.0,
            "peak_MW":    float(load[mask].max()) if mask.any() else 0.0,
            "imports_MW": float(imp[mask].max()) if mask.any() else 0.0,
        }

    morning = window(MORNING_HOURS)
    evening = window(EVENING_HOURS)

    # storage
    su = n.storage_units
    if not su.empty:
        su_cap = su.p_nom_opt.where(su.p_nom_opt.notna(), su.p_nom)
        bess_MW = float(su_cap.sum())
        bess_MWh = float((su_cap * su.max_hours).sum())
        su_p = n.storage_units_t.p.sum(axis=1)
        eve_mask = pd.Index(su_p.index.hour).isin(list(EVENING_HOURS))
        bess_eve_MW = float(su_p[eve_mask].clip(lower=0).max()) if eve_mask.any() else 0.0
    else:
        bess_MW = bess_MWh = bess_eve_MW = 0.0

    return {
        "demand_GWh": demand_GWh,
        "installed_MW": installed_MW,
        "cap_by_carrier": cap_by_carrier,
        "re_GWh": re_GWh,
        "re_share": re_GWh / demand_GWh if demand_GWh else 0.0,
        "gen_GWh": gen_GWh,
        "imp_GWh": imp_GWh,
        "exp_GWh": exp_GWh,
        "ls_GWh": ls_GWh,
        "unmet_share": ls_GWh / demand_GWh if demand_GWh else 0.0,
        "morning": morning,
        "evening": evening,
        "bess_MW": bess_MW,
        "bess_MWh": bess_MWh,
        "bess_eve_MW": bess_eve_MW,
    }


# =========================================================
# TURN METRICS INTO TABLE CELLS  (value, subtext, rating)
# =========================================================
def fmt_gwh(x):
    return f"{x:,.0f} GWh"


def fmt_musd(x):
    sign = "-" if x < 0 else ""
    return f"{sign}USD {abs(x) / 1e6:,.1f} M"


def cells_from_metrics(m, option, cost_df):
    c = {}
    c["Total demand"] = (fmt_gwh(m["demand_GWh"]), "", "warn")

    mix = ", ".join(f"{k} {v:,.0f}" for k, v in m["cap_by_carrier"].items() if v > 0.5)
    c["Installed capacity"] = (
        f"{m['installed_MW']:,.0f} MW",
        ("Fixed planned" if option == "A" else "Optimised") + (f"\n{mix}" if mix else ""),
        "warn" if option == "A" else "good",
    )

    rs = m["re_share"]
    c["Renewable share"] = (f"{rs:.0%}", f"RE {m['re_GWh']:,.0f} GWh",
                            "good" if rs >= 0.8 else "warn" if rs >= 0.5 else "bad")

    ish = m["imp_GWh"] / m["demand_GWh"] if m["demand_GWh"] else 0
    c["Imports"] = (fmt_gwh(m["imp_GWh"]), f"{ish:.0%} of demand",
                    "good" if ish < 0.2 else "warn" if ish < 0.4 else "bad")

    c["Exports"] = ((fmt_gwh(m["exp_GWh"]), "", "good") if m["exp_GWh"] > 0.5
                    else ("None", "No surplus exported", "warn"))

    for key, w in [("Morning peak unmet", m["morning"]), ("Evening peak unmet", m["evening"])]:
        u = w["unmet_MW"]
        if u < 0.5:
            c[key] = ("0 MW", f"Peak imports {w['imports_MW']:,.0f} MW", "good")
        else:
            share = u / w["peak_MW"] if w["peak_MW"] else 0
            c[key] = (f"{u:,.1f} MW", f"~{share:.0%} of window peak", "bad")

    us = m["unmet_share"]
    c["Unmet energy"] = (f"{us:.1%}", f"{m['ls_GWh']:,.1f} GWh" if us > 0 else "",
                         "good" if us < 0.0005 else "bad")

    if m["bess_MW"] > 0.5:
        c["Battery storage"] = (f"{m['bess_MW']:,.0f} MW / {m['bess_MWh']:,.0f} MWh",
                                f"{m['bess_eve_MW']:,.0f} MW max discharge at eve. peak",
                                "good" if option == "B" else "warn")
    else:
        c["Battery storage"] = ("None", "", "bad")

    # costs: Option B only (Option A is dispatch only, no investment decision)
    if option == "B" and cost_df is not None and not cost_df.empty:
        row = cost_df[cost_df["year"] == YEAR]
        if not row.empty:
            r = row.iloc[0]
            c["Net system cost"] = (fmt_musd(r["net_cost"]),
                                    f"Export revenue {fmt_musd(r['export_revenue'])}", "warn")
        else:
            c["Net system cost"] = ("No data", f"{YEAR} missing in cost summary", "warn")
        best = cost_df.loc[cost_df["net_cost"].idxmin()]
        c["Most favourable year"] = (f"{int(best['year'])}: {fmt_musd(best['net_cost'])}",
                                     "Export revenue exceeds costs" if best["net_cost"] < 0
                                     else "Lowest net cost", "good")
    else:
        c["Net system cost"] = ("N/A", "Dispatch only, not cost-optimised", "warn")
        c["Most favourable year"] = ("N/A", "", "warn")

    return c


def status_quo_cells(r, sq):
    """Cells from status_quo_balance.py (central network only)."""
    c = {}
    c["Total demand"] = (fmt_gwh(r["load_central_GWh"]),
                         f"Central network (national {r['load_total_GWh']:,.0f} GWh)", "warn")
    c["Installed capacity"] = ("Existing only", "Ramarothole + Muela, no expansion", "bad")
    rs = r["re_share"]
    c["Renewable share"] = (f"{rs:.0%}", "Hydro + solar only",
                            "good" if rs >= 0.8 else "warn" if rs >= 0.5 else "bad")
    c["Imports"] = (fmt_gwh(r["imports_GWh"]),
                    f"{r['imports_share']:.0%} of central demand"
                    + (", 180 MW cap binding" if r["max_imports_MW"] >= IMPORT_CAP_SQ - 0.5 else ""),
                    "good" if r["imports_share"] < 0.2 else "warn" if r["imports_share"] < 0.4 else "bad")
    c["Exports"] = ("None", "", "bad")
    for key, u, pk in [("Morning peak unmet", r["morning_unmet_MW"], r["morning_peak_MW"]),
                       ("Evening peak unmet", r["evening_unmet_MW"], r["evening_peak_MW"])]:
        c[key] = (("0 MW", "Zero deficit", "good") if u < 0.5 else
                  (f"{u:,.1f} MW", f"~{u / pk:.0%} of window peak" if pk else "", "bad"))
    us = r["unmet_share"]
    first = sq[sq["unmet_share"] > 0.0005]["year"]
    c["Unmet energy"] = (f"{us:.1%}",
                         (f"{r['unmet_GWh']:,.1f} GWh, deficit from {int(first.min())}" if not first.empty else ""),
                         "good" if us < 0.0005 else "bad")
    c["Battery storage"] = ("None", "", "bad")
    c["Net system cost"] = ("N/A", "Not cost-optimised", "warn")
    c["Most favourable year"] = ("N/A", "", "warn")
    return c


def missing_cells(msg):
    return {k: ("Not run", msg, None) for k in METRICS}


# =========================================================
# COLLECT ALL COLUMNS
# =========================================================
columns = []      # list of (case_name, demand, cells_dict)
check_rows = []   # raw numbers for checking

for case_name, option in CASES:
    for demand in DEMANDS:
        if option is None:
            sq_file = SQ_DIR / demand / f"status_quo_summary_{demand}.csv"
            if not sq_file.exists():
                print(f"{case_name} | {demand}: {sq_file} not found, run status_quo_balance.py first")
                columns.append((case_name, demand, missing_cells(str(sq_file))))
                continue
            sq = pd.read_csv(sq_file)
            row = sq[sq["year"] == YEAR]
            if row.empty:
                print(f"{case_name} | {demand}: no {YEAR} row in {sq_file}")
                columns.append((case_name, demand, missing_cells(f"No {YEAR} in {sq_file.name}")))
                continue
            print(f"Reading {sq_file}")
            columns.append((case_name, demand, status_quo_cells(row.iloc[0], sq)))
            continue

        nc = Path(f"networks/{demand}/{option}/solved_{YEAR}.nc")
        if not nc.exists():
            print(f"{case_name} | {demand}: {nc} not found")
            columns.append((case_name, demand, missing_cells(str(nc))))
            continue

        print(f"Reading {nc}")
        n = pypsa.Network(str(nc))
        m = network_metrics(n)

        cost_df = None
        if option == "B":
            cf = Path(f"results/{demand}/B/cost_analysis/cost_summary_clean_{demand}.csv")
            if cf.exists():
                cost_df = pd.read_csv(cf)
            else:
                print(f"  {cf} not found, run cost_summary_plots.py first")

        columns.append((case_name, demand, cells_from_metrics(m, option, cost_df)))

        check_rows.append({
            "case": case_name, "option": option, "demand": demand, "year": YEAR,
            "demand_GWh": m["demand_GWh"], "installed_MW": m["installed_MW"],
            "re_GWh": m["re_GWh"], "re_share": m["re_share"],
            "imports_GWh": m["imp_GWh"], "exports_GWh": m["exp_GWh"],
            "unmet_GWh": m["ls_GWh"], "unmet_share": m["unmet_share"],
            "morning_unmet_MW": m["morning"]["unmet_MW"], "evening_unmet_MW": m["evening"]["unmet_MW"],
            "morning_peak_MW": m["morning"]["peak_MW"], "evening_peak_MW": m["evening"]["peak_MW"],
            "bess_MW": m["bess_MW"], "bess_MWh": m["bess_MWh"], "bess_eve_MW": m["bess_eve_MW"],
            **{f"cap_{k}_MW": v for k, v in m["cap_by_carrier"].items()},
            **{f"gen_{k}_GWh": v for k, v in m["gen_GWh"].items()},
        })


# =========================================================
# WRITE WORKBOOK
# =========================================================
HDR_DARK  = "1F4E79"
HDR_MID   = "2E75B6"
METRIC_BG = "EBF3FB"
GREY_BG   = "EDEDED"; GREY_TXT = "7F7F7F"
GOOD_BG   = "E2EFDA"; GOOD_TXT = "375623"
WARN_BG   = "FFF2CC"; WARN_TXT = "7F6000"
BAD_BG    = "FCE4D6"; BAD_TXT  = "843C0C"
WHITE     = "FFFFFF"

thin = Side(style="thin", color="AAAAAA")
bdr  = Border(left=thin, right=thin, top=thin, bottom=thin)


def style(cell, value=None, bold=False, size=10, color="000000",
          bg=None, align="left", wrap=False, italic=False):
    if value is not None:
        cell.value = value
    cell.font      = Font(name="Arial", bold=bold, size=size, color=color, italic=italic)
    cell.alignment = Alignment(horizontal=align, vertical="center", wrap_text=wrap)
    cell.border    = bdr
    if bg:
        cell.fill = PatternFill("solid", start_color=bg, end_color=bg)


def hdr(cell, text, bg=HDR_DARK, size=10):
    style(cell, text, bold=True, size=size, color=WHITE, bg=bg, align="center", wrap=True)


def outcome(cell, value_text, sub_text, rating):
    bgs  = {"good": GOOD_BG, "warn": WARN_BG, "bad": BAD_BG}
    txts = {"good": GOOD_TXT, "warn": WARN_TXT, "bad": BAD_TXT}
    combined = value_text + ("\n" + sub_text if sub_text else "")
    style(cell, combined, bold=True, size=9,
          color=txts.get(rating, GREY_TXT), bg=bgs.get(rating, GREY_BG), wrap=True)


wb = Workbook()
ws = wb.active
ws.title = "Scenario Summary"

n_cols = len(columns)
last_col = 1 + n_cols
from openpyxl.utils import get_column_letter as L

ws.column_dimensions["A"].width = 30
for ci in range(2, last_col + 1):
    ws.column_dimensions[L(ci)].width = 24

ws.merge_cells(f"A1:{L(last_col)}1")
style(ws["A1"], f"Table 7.  Cross-scenario summary: key results by {YEAR}",
      bold=True, size=12, color=WHITE, bg=HDR_DARK, align="center")
ws.row_dimensions[1].height = 24

ws.merge_cells("A2:A3")
hdr(ws["A2"], "Metric")
col = 2
for case_name, _ in CASES:
    span = len(DEMANDS)
    ws.merge_cells(f"{L(col)}2:{L(col + span - 1)}2")
    hdr(ws[f"{L(col)}2"], case_name)
    for i, d in enumerate(DEMANDS):
        hdr(ws[f"{L(col + i)}3"], f"{d} demand", bg=HDR_MID, size=9)
    col += span
ws.row_dimensions[2].height = 20
ws.row_dimensions[3].height = 18

START_ROW = 4
all_metrics = METRICS + ["Key limitation"]
for r_idx, key in enumerate(all_metrics):
    row = START_ROW + r_idx
    ws.row_dimensions[row].height = 42
    style(ws.cell(row=row, column=1), METRIC_LABELS.get(key, key),
          bold=True, color=HDR_DARK, bg=METRIC_BG, wrap=True)
    for c_idx, (case_name, demand, cells) in enumerate(columns):
        if key == "Key limitation":
            txt, rating = KEY_LIMITATION.get((case_name, demand), ("", None))
            outcome(ws.cell(row=row, column=2 + c_idx), txt, "", rating)
        else:
            val, sub, rating = cells.get(key, ("", "", None))
            outcome(ws.cell(row=row, column=2 + c_idx), val, sub, rating)

legend_row = START_ROW + len(all_metrics) + 1
ws.merge_cells(f"A{legend_row}:{L(last_col)}{legend_row}")
style(ws[f"A{legend_row}"],
      "Colour key: Green = favourable, Amber = moderate or constrained, Red = adverse, Grey = not run.  "
      f"Notes: Mission 300 Supply = Option A, Planned Generation Expansion = Option B, values for {YEAR} "
      "from the solved networks.  Status Quo = central network only (excludes areas fed by Clarens and Letloepe), "
      "hourly balance of existing solar + hydro with imports capped at 180 MW.  "
      f"Morning window {MORNING_HOURS.start:02d}:00 to {MORNING_HOURS.stop - 1:02d}:59, "
      f"evening window {EVENING_HOURS.start:02d}:00 to {EVENING_HOURS.stop - 1:02d}:59.  "
      "Renewable share = solar + wind + hydro generation / demand (can exceed 100% with exports).  "
      "Net cost = new-build CAPEX + OPEX after export revenue, Option B only.  "
      "Transmission costs exclude transformer upgrades, so capital costs are a lower bound.",
      size=8, color="555555", italic=True, wrap=True)
ws.row_dimensions[legend_row].height = 48
ws.freeze_panes = "B4"

# raw numbers for checking the table
if check_rows:
    ws2 = wb.create_sheet("Raw values")
    raw = pd.DataFrame(check_rows)
    for ci, name in enumerate(raw.columns, start=1):
        hdr(ws2.cell(row=1, column=ci), name, size=9)
        ws2.column_dimensions[L(ci)].width = 16
    for ri, rec in enumerate(raw.itertuples(index=False), start=2):
        for ci, v in enumerate(rec, start=1):
            cell = ws2.cell(row=ri, column=ci, value=None if pd.isna(v) else v)
            if isinstance(v, float):
                cell.number_format = "0.0%" if "share" in raw.columns[ci - 1] else "#,##0.0"

OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
wb.save(OUT_FILE)
print(f"Saved: {OUT_FILE}")