"""Build the three cleaned CSVs and the .xlsx workbook (pivot table is added manually in Excel)."""
import pandas as pd
from openpyxl import load_workbook
from openpyxl.workbook.defined_name import DefinedName
from openpyxl.formatting.rule import FormulaRule
from openpyxl.styles import PatternFill

D, COUNTRIES = "data", ["US", "GB", "IN"]

def read(p):
    try:
        return pd.read_csv(p)
    except UnicodeDecodeError:
        return pd.read_csv(p, encoding="latin-1")

df = pd.concat([read(f"{D}/{c}videos.csv").assign(country=c) for c in COUNTRIES], ignore_index=True)
df["trending_date"] = pd.to_datetime(df["trending_date"], format="%y.%d.%m", errors="coerce")
df["publish_time"] = pd.to_datetime(df["publish_time"], errors="coerce", utc=True).dt.tz_localize(None)
for c in ["views", "likes", "dislikes", "comment_count"]:
    df[c] = pd.to_numeric(df[c], errors="coerce")
df = df.dropna(subset=["views", "likes", "dislikes", "comment_count", "trending_date", "publish_time"])
df = df.drop_duplicates(subset=["video_id", "trending_date", "country"])

cats = pd.read_csv(f"{D}/categories.csv")[["category_id", "category_name"]].drop_duplicates()
videos = (df.sort_values("trending_date").drop_duplicates("video_id", keep="last")
            [["video_id", "title", "channel_title", "category_id", "publish_time"]])
videos["title"] = videos["title"].str.slice(0, 250)
# keep FK valid: category_id must exist in categories
videos = videos[videos["category_id"].isin(cats["category_id"])]
rec = df[df["video_id"].isin(videos["video_id"])][
    ["video_id", "country", "trending_date", "views", "likes", "dislikes", "comment_count"]].copy()
rec.insert(0, "record_id", range(1, len(rec) + 1))
rec["trending_date"] = rec["trending_date"].dt.strftime("%Y-%m-%d")
videos["publish_time"] = videos["publish_time"].dt.strftime("%Y-%m-%d %H:%M:%S")

cats.to_csv(f"{D}/categories_clean.csv", index=False)
videos.to_csv(f"{D}/videos_clean.csv", index=False)
rec.to_csv(f"{D}/trending_records_clean.csv", index=False)
print(len(cats), len(videos), len(rec))

# ---- Workbook ----
full = rec.merge(videos[["video_id", "title", "category_id"]], on="video_id")
with pd.ExcelWriter("trendpulse.xlsx", engine="openpyxl") as xw:
    full.to_excel(xw, "Records", index=False)
    cats.to_excel(xw, "Categories", index=False)
wb = load_workbook("trendpulse.xlsx")
ws, n = wb["Records"], len(full) + 1
hdr = [c.value for c in ws[1]]
col = {h: chr(65 + i) for i, h in enumerate(hdr)}          # A.. (fine for <26 cols)
ws.cell(1, len(hdr) + 1, "category_name")
for r in range(2, n + 1):                                  # (b) lookup formula
    ws.cell(r, len(hdr) + 1,
            f"=VLOOKUP({col['category_id']}{r},Categories!$A:$B,2,FALSE)")
ws.auto_filter.ref = ws.dimensions                         # (d) filters
views_rng = f"{col['views']}2:{col['views']}{n}"
wb.defined_names["ViewsRange"] = DefinedName("ViewsRange", attr_text=f"Records!${col['views']}$2:${col['views']}${n}")  # (f)
ws.conditional_formatting.add(                             # (e) top 10% of views
    views_rng, FormulaRule(formula=[f"{col['views']}2>=PERCENTILE(ViewsRange,0.9)"],
                           fill=PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")))
sm = wb.create_sheet("Summary")                            # (c) headline formulas
sm["A1"], sm["B1"] = "Metric", "Value"
for i, c in enumerate(COUNTRIES, start=2):
    sm[f"A{i}"] = f"Records {c}"
    sm[f"B{i}"] = f'=COUNTIF(Records!{col["country"]}:{col["country"]},"{c}")'
sm["A6"], sm["B6"] = "Total views", "=SUM(ViewsRange)"
sm["A7"], sm["B7"] = "Average views", "=AVERAGE(ViewsRange)"
wb.save("trendpulse.xlsx")
# (a) Pivot: in Excel -> Insert > PivotTable on Records; Rows=category_name, Columns=country, Values=Average of views.
# Sorting (d): sort Records by views descending via Data > Sort.
