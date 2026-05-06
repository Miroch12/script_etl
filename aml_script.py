import pandas as pd
from sqlalchemy import create_engine, text
from playwright.sync_api import sync_playwright

# ======================
# 0. DB CONNECTION
# ======================
engine = create_engine(
    "postgresql+psycopg2://hp:hp@127.0.0.1:5432/aml_pg"
)

# ======================
# 1. RESET DATABASE
# ======================
with engine.begin() as conn:
    conn.execute(text("DROP VIEW IF EXISTS vw_fatf_dashboard"))
    conn.execute(text("DROP TABLE IF EXISTS fact_fatf"))
    conn.execute(text("DROP TABLE IF EXISTS dim_metric"))
    conn.execute(text("DROP TABLE IF EXISTS dim_country"))

print("✔ DB RESET DONE")

# ======================
# 2. SCRAPING + DOWNLOAD
# ======================
url = "https://www.fatf-gafi.org/content/fatf-gafi/en/publications/Mutualevaluations/Assessment-ratings.html"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()

    page.goto(url, timeout=60000)
    page.wait_for_timeout(5000)

    print("✔ page ouverte")

    download_link = page.locator("a.cmp-download__action").first

    with page.expect_download() as download_info:
        download_link.click()

    download = download_info.value
    path = download.path()

    df = pd.read_excel(path, engine="openpyxl", skiprows=4)

    browser.close()

print("✔ Excel chargé")

# ======================
# 3. CLEANING
# ======================
df.columns = (
    df.columns.str.strip()
    .str.lower()
    .str.replace("\n", " ", regex=True)
    .str.replace("  ", " ", regex=True)
)

df = df.dropna(how="all")
df = df.dropna(subset=[df.columns[0]])
df = df.reset_index(drop=True)

df.rename(columns={df.columns[0]: "country"}, inplace=True)
df["country"] = df["country"].astype(str).str.strip().str.lower()

# ======================
# 4. REPORT DATE FIX (ROBUST)
# ======================
report_col = None
for c in df.columns:
    if "report date" in c:
        report_col = c
        break

# nettoyage texte
df[report_col] = df[report_col].astype(str).str.strip()

# parsing multi-format
df["report_date"] = pd.to_datetime(
    df[report_col],
    format="mixed",   # accepte plusieurs formats
    errors="coerce"
)

# supprimer dates invalides
df = df[df["report_date"].notna()]

print("✔ report_date fixed (valid dates only)")

# ======================
# 5. CONTINENT JOIN
# ======================
df_continent = pd.read_excel("pays_continent.xlsx")

df_continent.columns = df_continent.columns.str.strip().str.lower()

df_continent.rename(columns={
    "pays": "country",
    "continent": "continent"
}, inplace=True)

df_continent["country"] = df_continent["country"].astype(str).str.strip().str.lower()

df = df.merge(df_continent, on="country", how="left")

print("✔ continent ajouté")

# ======================
# 6. SCORE MAPPING
# ======================
fatf_mapping = {"C": 4, "LC": 3, "PC": 2, "NC": 1}
io_mapping = {"HE": 4, "SE": 3, "ME": 2, "LE": 1}

r_cols = [c for c in df.columns if c.startswith("r.")]
io_cols = [c for c in df.columns if c.startswith("io")]

for col in r_cols:
    df[col] = df[col].astype(str).str.upper().str.strip().map(fatf_mapping)

for col in io_cols:
    df[col] = df[col].astype(str).str.upper().str.strip().map(io_mapping)

df[r_cols] = df[r_cols].fillna(0)
df[io_cols] = df[io_cols].fillna(0)

# ======================
# 7. DIM COUNTRY
# ======================
dim_country = df[["country", "continent"]].drop_duplicates().reset_index(drop=True)
dim_country["country_id"] = pd.factorize(dim_country["country"])[0] + 1

# ======================
# 8. FACT BUILD
# ======================
fact_temp = []

for col in r_cols:
    temp = df[["country", "continent", "report_date", col]].copy()
    temp.columns = ["country", "continent", "report_date", "score_numeric"]
    temp["metric_code"] = col.upper()
    temp["type"] = "TC"
    fact_temp.append(temp)

for col in io_cols:
    temp = df[["country", "continent", "report_date", col]].copy()
    temp.columns = ["country", "continent", "report_date", "score_numeric"]
    temp["metric_code"] = col.upper()
    temp["type"] = "EFF"
    fact_temp.append(temp)

fact_df = pd.concat(fact_temp, ignore_index=True)

fact_df = fact_df.dropna(subset=["score_numeric"])
fact_df = fact_df[fact_df["score_numeric"] > 0]

# sécurité date
fact_df["report_date"] = pd.to_datetime(fact_df["report_date"], errors="coerce")

# ======================
# 9. DIM METRIC
# ======================
dim_metric = fact_df[["metric_code", "type"]].drop_duplicates().reset_index(drop=True)
dim_metric["metric_id"] = dim_metric.index + 1

# ======================
# 10. LINK FACT
# ======================
fact_df = fact_df.merge(dim_country, on=["country", "continent"], how="left")
fact_df = fact_df.merge(dim_metric, on=["metric_code", "type"], how="left")

fact_df = fact_df[[
    "country_id",
    "metric_id",
    "report_date",
    "score_numeric"
]]

# ======================
# 11. LOAD DATABASE
# ======================
dim_country.to_sql("dim_country", engine, if_exists="replace", index=False)
dim_metric.to_sql("dim_metric", engine, if_exists="replace", index=False)
fact_df.to_sql("fact_fatf", engine, if_exists="replace", index=False, chunksize=500)

print("✔ STAR SCHEMA LOADED")

# ======================
# 12. VIEW
# ======================
with engine.begin() as conn:
    conn.execute(text("""
    CREATE OR REPLACE VIEW vw_fatf_dashboard AS
    SELECT
        f.country_id,
        c.country,
        c.continent,
        f.report_date,
        m.metric_code,
        m.type,
        f.score_numeric
    FROM fact_fatf f
    JOIN dim_country c ON f.country_id = c.country_id
    JOIN dim_metric m ON f.metric_id = m.metric_id
    """))

print("✔ VIEW READY FOR SUPERSET")