import pandas as pd
from pathlib import Path
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

# -------------------------------------------------
# SETTINGS
# -------------------------------------------------
YEARS   = [2025, 2026, 2027, 2028, 2029, 2030, 2035, 2040, 2045, 2050]
DEMANDS = ["BAU", "M300"]     # demand scenarios to process
OPTION  = "B"                 # planned generation expansion (Option B)

# Combined BAU vs M300 comparison goes here
COMPARE_DIR = Path(f"results/cost_analysis_{OPTION}")
COMPARE_DIR.mkdir(parents=True, exist_ok=True)

# -------------------------------------------------
# STYLES
# -------------------------------------------------
HEADER_FILL  = PatternFill("solid", start_color="1F4E79", end_color="1F4E79")
SUBHEAD_FILL = PatternFill("solid", start_color="2E75B6", end_color="2E75B6")
GEN_FILL     = PatternFill("solid", start_color="DEEAF1", end_color="DEEAF1")
STO_FILL     = PatternFill("solid", start_color="E2EFDA", end_color="E2EFDA")
TOTAL_FILL   = PatternFill("solid", start_color="FFF2CC", end_color="FFF2CC")
SYS_FILL     = PatternFill("solid", start_color="375623", end_color="375623")
ALT_FILL     = PatternFill("solid", start_color="F5F9FF", end_color="F5F9FF")
EXP_FILL     = PatternFill("solid", start_color="FCE4D6", end_color="FCE4D6")  # light orange - export

WHITE_BOLD = Font(name="Arial", bold=True, color="FFFFFF", size=11)
SUBH_FONT  = Font(name="Arial", bold=True, color="FFFFFF", size=10)
NORMAL     = Font(name="Arial", size=10)
TOTAL_FONT = Font(name="Arial", bold=True, size=10, color="7F6000")

THIN = Side(style="thin",   color="B8CCE4")
MED  = Side(style="medium", color="2E75B6")
BDR  = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)

CENTER = Alignment(horizontal="center", vertical="center")
LEFT   = Alignment(horizontal="left",   vertical="center", indent=1)
RIGHT  = Alignment(horizontal="right",  vertical="center")

USD_FMT = '#,##0.00'
MW_FMT  = '#,##0.00'


def sc(cell, value=None, font=None, fill=None, align=None, border=None, fmt=None):
    if value is not None:
        cell.value = value
    if font:   cell.font = font
    if fill:   cell.fill = fill
    if align:  cell.alignment = align
    if border: cell.border = border
    if fmt:    cell.number_format = fmt


# -------------------------------------------------
# EXTRACT DATA PER YEAR
# -------------------------------------------------
def extract_year(results_dir, year):
    gen = pd.read_csv(results_dir / f"summary_{year}_gen_detail.csv")
    sys = pd.read_csv(results_dir / f"summary_{year}_system.csv")
    obj = pd.read_csv(results_dir / f"summary_{year}_objective.csv")
    top = pd.read_csv(results_dir / f"summary_{year}.csv")

    # solve_option_B.py only writes storage_detail when the network has storage
    sto_file = results_dir / f"summary_{year}_storage_detail.csv"
    sto = pd.read_csv(sto_file) if sto_file.exists() else pd.DataFrame()

    # ---- GENERATORS (from gen_detail) ----
    gen_rows = []
    for _, r in gen.iterrows():
        gen_rows.append({
            "Asset":                    r["Generator"],
            "Type":                     "Generator",
            "Carrier":                  r.get("carrier", ""),
            "p_nom (MW)":               r.get("p_nom", 0),
            "p_nom_opt (MW)":           r.get("p_nom_opt", 0),
            "delta_MW":                 r.get("delta_MW", 0),
            "Capital Cost (USD/MW)":    r.get("capital_cost", 0),
            "Marginal Cost (USD/MWh)":  r.get("marginal_cost", 0),
            "Total Fleet Cost (USD)":   r.get("total_fleet_cost", 0),
            "New Build Cost (USD)":     r.get("new_build_cost", 0),
            "Build Year":               r.get("build_year", ""),
            "Lifetime (yrs)":           r.get("lifetime", ""),
        })

    # ---- STORAGE (from storage_detail) ----
    sto_rows = []
    for _, r in sto.iterrows():
        sto_rows.append({
            "Asset":                    r["StorageUnit"],
            "Type":                     "Storage",
            "Carrier":                  r.get("carrier", ""),
            "p_nom (MW)":               r.get("p_nom", 0),
            "p_nom_opt (MW)":           r.get("p_nom_opt", 0),
            "delta_MW":                 r.get("delta_MW", 0),
            "Capital Cost (USD/MW)":    r.get("capital_cost", 0),
            "Marginal Cost (USD/MWh)":  r.get("marginal_cost", 0),
            "Total Fleet Cost (USD)":   r.get("total_fleet_cost", 0),
            "New Build Cost (USD)":     r.get("new_build_cost", 0),
            "Build Year":               r.get("build_year", ""),
            "Lifetime (yrs)":           r.get("lifetime", ""),
        })

    # ---- SYSTEM TOTALS (from system CSV) ----
    s = sys.iloc[0]
    system = {
        "gen_total_fleet_cost":           s.get("gen_total_fleet_cost", 0),
        "gen_new_build_cost":             s.get("gen_new_build_cost", 0),
        "storage_total_fleet_cost":       s.get("storage_total_fleet_cost", 0),
        "storage_new_build_cost":         s.get("storage_new_build_cost", 0),
        "transmission_total_cost":        s.get("transmission_total_cost", 0),
        "transmission_reinforcement_cost":s.get("transmission_reinforcement_cost", 0),
        "opex_total":                     s.get("opex_total", 0),
    }
    system["total_capex"] = (
        system["gen_new_build_cost"] +
        system["storage_new_build_cost"] +
        system["transmission_reinforcement_cost"]
    )
    objective = obj["objective_cost"].iloc[0] if "objective_cost" in obj.columns else None

    # ---- EXPORT REVENUE (from top-level summary CSV) ----
    export_rows = top[top["carrier"] == "export"] if "carrier" in top.columns else pd.DataFrame()
    if not export_rows.empty and "operating_cost" in export_rows.columns:
        # operating_cost for export is negative (revenue), flip sign to get positive revenue
        export_details = []
        for _, er in export_rows.iterrows():
            export_details.append({
                "carrier":        er.get("carrier", "export"),
                "energy_GWh":     er.get("energy_GWh", 0),
                "operating_cost": er.get("operating_cost", 0),
                "revenue":        -er.get("operating_cost", 0),
            })
        export_df = pd.DataFrame(export_details)
        export_revenue_total = export_df["revenue"].sum()
    else:
        export_df = pd.DataFrame()
        export_revenue_total = 0

    system["export_revenue"] = export_revenue_total

    # opex_total in solve_option_B.py = sum(dispatch x marginal_cost) over ALL generators,
    # including Export_Mabote (negative dispatch x 80 USD/MWh), so it is already NET of exports.
    system["opex_net"]   = system["opex_total"]
    system["opex_gross"] = system["opex_total"] + export_revenue_total   # before export revenue

    system["gross_cost"] = system["total_capex"] + system["opex_gross"]  # CAPEX + OPEX, no exports
    system["net_cost"]   = system["total_capex"] + system["opex_net"]    # after export revenue

    return pd.DataFrame(gen_rows), pd.DataFrame(sto_rows), system, objective, export_df


def build_tracker(demand):
    results_dir = Path(f"results/{demand}/{OPTION}")
    out_dir = results_dir / "cost_analysis"
    out_dir.mkdir(parents=True, exist_ok=True)

    if not results_dir.exists():
        print(f"{demand}: folder not found, skipped ({results_dir})")
        return []

    print(f"\n=== {demand} | Option {OPTION} ===")

    # -------------------------------------------------
    # BUILD WORKBOOK
    # -------------------------------------------------
    wb = Workbook()
    wb.remove(wb.active)

    summary_records = []

    COLUMNS = [
        "Asset", "Type", "Carrier",
        "p_nom (MW)", "p_nom_opt (MW)", "delta_MW",
        "Capital Cost (USD/MW)", "Marginal Cost (USD/MWh)",
        "Total Fleet Cost (USD)", "New Build Cost (USD)",
        "Build Year", "Lifetime (yrs)"
    ]
    COL_WIDTHS = [34, 12, 14, 16, 18, 12, 22, 22, 24, 22, 12, 14]
    # columns (0-indexed) that receive number formatting
    NUM_COLS = {3, 4, 5, 6, 7, 8, 9}

    for year in YEARS:
        print(f"Building sheet for {year}...")

        try:
            gen_df, sto_df, system, objective, export_df = extract_year(results_dir, year)
        except FileNotFoundError as e:
            print(f"  Skipping {year}: {e}")
            continue

        ws = wb.create_sheet(title=str(year))
        n = len(COLUMNS)
        last_col = get_column_letter(n)

        for i, w in enumerate(COL_WIDTHS):
            ws.column_dimensions[get_column_letter(i + 1)].width = w

        # ---- TITLE ----
        ws.merge_cells(f"A1:{last_col}1")
        sc(ws["A1"], value=f"Technology Cost and Capacity Breakdown: {demand} demand, Option {OPTION}, {year}",
           font=WHITE_BOLD, fill=HEADER_FILL, align=CENTER)
        ws.row_dimensions[1].height = 26

        # ---- COLUMN HEADERS ----
        for ci, col_name in enumerate(COLUMNS, start=1):
            sc(ws.cell(row=2, column=ci), value=col_name,
               font=SUBH_FONT, fill=SUBHEAD_FILL,
               align=Alignment(horizontal="center", vertical="center", wrap_text=True),
               border=BDR)
        ws.row_dimensions[2].height = 34

        row_num = 3

        def write_section(df, section_label, row_fill, header_color, row_num):
            # section header
            ws.merge_cells(f"A{row_num}:{last_col}{row_num}")
            sc(ws[f"A{row_num}"], value=section_label,
               font=Font(name="Arial", bold=True, color="FFFFFF", size=10),
               fill=PatternFill("solid", start_color=header_color, end_color=header_color),
               align=CENTER)
            ws.row_dimensions[row_num].height = 16
            row_num += 1

            if df.empty:
                ws.merge_cells(f"A{row_num}:{last_col}{row_num}")
                sc(ws[f"A{row_num}"], value="None in this year",
                   font=NORMAL, fill=row_fill, align=LEFT, border=BDR)
                return row_num + 2

            section_start = row_num
            for i, (_, r) in enumerate(df.iterrows()):
                fill = row_fill if i % 2 == 0 else ALT_FILL
                ws.row_dimensions[row_num].height = 16
                for ci, col_name in enumerate(COLUMNS, start=1):
                    val = r.get(col_name, "")
                    fmt = USD_FMT if (ci - 1) in NUM_COLS else None
                    if ci == 1:
                        aln = LEFT
                    elif ci in (2, 3, 11, 12):
                        aln = CENTER
                    else:
                        aln = RIGHT
                    sc(ws.cell(row=row_num, column=ci), value=val,
                       font=NORMAL, fill=fill, align=aln, border=BDR, fmt=fmt)
                row_num += 1
            section_end = row_num - 1

            # subtotal row
            ws.merge_cells(f"A{row_num}:H{row_num}")
            sc(ws[f"A{row_num}"], value=f"{section_label}: Subtotal",
               font=TOTAL_FONT, fill=TOTAL_FILL, align=LEFT, border=BDR)
            for ci, col_name in enumerate(["Total Fleet Cost (USD)", "New Build Cost (USD)"],
                                           start=9):
                col_letter = get_column_letter(ci)
                sc(ws.cell(row=row_num, column=ci),
                   value=f"=SUM({col_letter}{section_start}:{col_letter}{section_end})",
                   font=TOTAL_FONT, fill=TOTAL_FILL, align=RIGHT, border=BDR, fmt=USD_FMT)
            for ci in range(11, n + 1):
                ws.cell(row=row_num, column=ci).border = BDR
                ws.cell(row=row_num, column=ci).fill = TOTAL_FILL
            ws.row_dimensions[row_num].height = 18
            row_num += 2
            return row_num

        row_num = write_section(gen_df, "GENERATORS",    GEN_FILL, "2E75B6", row_num)
        row_num = write_section(sto_df, "STORAGE UNITS", STO_FILL, "375623", row_num)

        # ---- EXPORT REVENUE SECTION ----
        if not export_df.empty:
            ws.merge_cells(f"A{row_num}:{last_col}{row_num}")
            sc(ws[f"A{row_num}"], value=f"EXPORT REVENUE (from summary_{year}.csv)",
               font=Font(name="Arial", bold=True, color="FFFFFF", size=10),
               fill=PatternFill("solid", start_color="843C0C", end_color="843C0C"),
               align=CENTER)
            ws.row_dimensions[row_num].height = 16
            row_num += 1

            exp_headers = ["Carrier", "Energy (GWh)", "Operating Cost (USD)", "Revenue (USD)"]
            exp_col_map = ["carrier", "energy_GWh", "operating_cost", "revenue"]
            for ci, h in enumerate(exp_headers, start=1):
                sc(ws.cell(row=row_num, column=ci), value=h,
                   font=SUBH_FONT, fill=SUBHEAD_FILL,
                   align=Alignment(horizontal="center", vertical="center", wrap_text=True),
                   border=BDR)
            # blank remaining cols
            for ci in range(len(exp_headers)+1, n+1):
                ws.cell(row=row_num, column=ci).border = BDR
                ws.cell(row=row_num, column=ci).fill = SUBHEAD_FILL
            ws.row_dimensions[row_num].height = 18
            row_num += 1

            exp_start = row_num
            for i, (_, er) in enumerate(export_df.iterrows()):
                fill = EXP_FILL if i % 2 == 0 else ALT_FILL
                ws.row_dimensions[row_num].height = 16
                vals = [er.get(c, 0) for c in exp_col_map]
                for ci, val in enumerate(vals, start=1):
                    fmt = USD_FMT if ci >= 3 else ('#,##0.00' if ci == 2 else None)
                    sc(ws.cell(row=row_num, column=ci), value=val,
                       font=NORMAL, fill=fill,
                       align=LEFT if ci == 1 else RIGHT,
                       border=BDR, fmt=fmt)
                for ci in range(len(exp_headers)+1, n+1):
                    ws.cell(row=row_num, column=ci).border = BDR
                    ws.cell(row=row_num, column=ci).fill = fill
                row_num += 1
            exp_end = row_num - 1

            # export subtotal
            ws.merge_cells(f"A{row_num}:B{row_num}")
            sc(ws[f"A{row_num}"], value="Total Export Revenue",
               font=TOTAL_FONT, fill=TOTAL_FILL, align=LEFT, border=BDR)
            ws.cell(row=row_num, column=2).border = BDR
            ws.cell(row=row_num, column=2).fill = TOTAL_FILL
            ws.merge_cells(f"C{row_num}:D{row_num}")
            sc(ws.cell(row=row_num, column=3),
               value=f"=SUM(D{exp_start}:D{exp_end})",
               font=TOTAL_FONT, fill=TOTAL_FILL, align=RIGHT, border=BDR, fmt=USD_FMT)
            for ci in range(5, n+1):
                ws.cell(row=row_num, column=ci).border = BDR
                ws.cell(row=row_num, column=ci).fill = TOTAL_FILL
            ws.row_dimensions[row_num].height = 18
            row_num += 2

        # ---- SYSTEM SUMMARY BLOCK ----
        ws.merge_cells(f"A{row_num}:{last_col}{row_num}")
        sc(ws[f"A{row_num}"],
           value=f"System-Level Summary  (summary_{year}_system.csv  &  summary_{year}_objective.csv)",
           font=Font(name="Arial", bold=True, color="FFFFFF", size=10),
           fill=SYS_FILL, align=CENTER)
        ws.row_dimensions[row_num].height = 18
        row_num += 1

        sys_rows = [
            ("Gen Total Fleet Cost (USD)",              system["gen_total_fleet_cost"],              GEN_FILL),
            ("Gen New Build Cost / CAPEX (USD)",         system["gen_new_build_cost"],               GEN_FILL),
            ("Storage Total Fleet Cost (USD)",           system["storage_total_fleet_cost"],         STO_FILL),
            ("Storage New Build Cost / CAPEX (USD)",     system["storage_new_build_cost"],           STO_FILL),
            ("Transmission Total Cost (USD)",            system["transmission_total_cost"],          ALT_FILL),
            ("Transmission Reinforcement CAPEX (USD)",   system["transmission_reinforcement_cost"],  ALT_FILL),
            ("Total CAPEX  [Gen + Storage + Trans] (USD)", system["total_capex"],                    TOTAL_FILL),
            ("Gross OPEX  [before export revenue] (USD)", system["opex_gross"],                      ALT_FILL),
            ("Export Revenue (USD)",                     system["export_revenue"],                   EXP_FILL),
            ("Net OPEX  [after export revenue] (USD)",   system["opex_net"],                         ALT_FILL),
            ("Gross System Cost  [CAPEX + Gross OPEX] (USD)", system["gross_cost"],                  TOTAL_FILL),
            ("Net System Cost  [CAPEX + Net OPEX] (USD)", system["net_cost"],                        TOTAL_FILL),
        ]
        if objective is not None:
            sys_rows.append(("Objective Cost (USD)", objective, TOTAL_FILL))

        label_end = get_column_letter(n - 2)   # spans most columns
        val_start  = get_column_letter(n - 1)
        val_end    = last_col

        for label, val, fill in sys_rows:
            ws.merge_cells(f"A{row_num}:{label_end}{row_num}")
            sc(ws[f"A{row_num}"], value=label,
               font=Font(name="Arial", bold=True, size=10),
               fill=fill, align=LEFT, border=BDR)
            ws.merge_cells(f"{val_start}{row_num}:{val_end}{row_num}")
            sc(ws[f"{val_start}{row_num}"], value=val,
               font=Font(name="Arial", size=10),
               fill=fill, align=RIGHT, border=BDR, fmt=USD_FMT)
            ws.row_dimensions[row_num].height = 16
            row_num += 1

        summary_records.append({
            "Year":                                   year,
            "Gen New Build CAPEX (USD)":              system["gen_new_build_cost"],
            "Storage New Build CAPEX (USD)":          system["storage_new_build_cost"],
            "Trans Reinforcement CAPEX (USD)":        system["transmission_reinforcement_cost"],
            "Total CAPEX (USD)":                      system["total_capex"],
            "Gross OPEX [before exports] (USD)":      system["opex_gross"],
            "Export Revenue (USD)":                   system["export_revenue"],
            "Net OPEX [after exports] (USD)":         system["opex_net"],
            "Gross Cost [CAPEX + Gross OPEX] (USD)":  system["gross_cost"],
            "Net Cost [CAPEX + Net OPEX] (USD)":      system["net_cost"],
            "Objective Cost (USD)":                   objective if objective is not None else "",
        })

    # -------------------------------------------------
    # SUMMARY SHEET
    # -------------------------------------------------
    if summary_records:
        ws_s = wb.create_sheet(title="Summary", index=0)
        sum_df = pd.DataFrame(summary_records)
        n_cols = len(sum_df.columns)
        last_col_s = get_column_letter(n_cols)

        ws_s.column_dimensions["A"].width = 8
        for ci in range(2, n_cols + 1):
            ws_s.column_dimensions[get_column_letter(ci)].width = 28

        ws_s.merge_cells(f"A1:{last_col_s}1")
        sc(ws_s["A1"], value=f"System Cost Summary: {demand} demand, Option {OPTION}, all years",
           font=WHITE_BOLD, fill=HEADER_FILL, align=CENTER)
        ws_s.row_dimensions[1].height = 26

        for ci, col_name in enumerate(sum_df.columns, start=1):
            sc(ws_s.cell(row=2, column=ci), value=col_name,
               font=SUBH_FONT, fill=SUBHEAD_FILL,
               align=Alignment(horizontal="center", vertical="center", wrap_text=True),
               border=BDR)
        ws_s.row_dimensions[2].height = 34

        for i, (_, row) in enumerate(sum_df.iterrows()):
            r = 3 + i
            fill = ALT_FILL if i % 2 == 0 else PatternFill()
            ws_s.row_dimensions[r].height = 17
            for ci, val in enumerate(row, start=1):
                fmt = None if ci == 1 else USD_FMT
                aln = CENTER if ci == 1 else RIGHT
                sc(ws_s.cell(row=r, column=ci), value=val,
                   font=NORMAL, fill=fill, align=aln, border=BDR, fmt=fmt)

    out_path = out_dir / f"technology_cost_tracker_{demand}_{OPTION}.xlsx"
    wb.save(out_path)
    print(f"\nDone. Saved to: {out_path}")
    return summary_records


# -------------------------------------------------
# RUN FOR BOTH DEMAND SCENARIOS
# -------------------------------------------------
all_records = []
for demand in DEMANDS:
    for rec in build_tracker(demand):
        all_records.append({"Demand": demand, **rec})

if all_records:
    comp = pd.DataFrame(all_records)
    comp.to_csv(COMPARE_DIR / "cost_summary_BAU_vs_M300.csv", index=False)

    # side-by-side: one row per year, BAU and M300 columns next to each other
    wide = comp.pivot(index="Year", columns="Demand")
    wide.columns = [f"{c} | {d}" for c, d in wide.columns]
    wide = wide[[f"{c} | {d}" for c in comp.columns if c not in ("Demand", "Year")
                 for d in DEMANDS if f"{c} | {d}" in wide.columns]]
    with pd.ExcelWriter(COMPARE_DIR / "cost_summary_BAU_vs_M300.xlsx") as xw:
        comp.to_excel(xw, sheet_name="Long", index=False)
        wide.to_excel(xw, sheet_name="Side_by_side")

    print(f"\nComparison saved to: {COMPARE_DIR}")