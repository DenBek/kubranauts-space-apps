import duckdb, os, subprocess, shutil, sys, time, pathlib

BASE = "https://firms.modaps.eosdis.nasa.gov/data/country/zips"
JOBS = [("modis", f"modis_{y}_all_countries.zip", y) for y in range(2000, 2026)] + \
       [("viirs_noaa20", f"viirs-jpss1_{y}_all_countries.zip", y) for y in range(2018, 2026)]
if "test" in sys.argv:
    JOBS = JOBS[:1]  # just MODIS 2000 (~5 MB) to check everything works

COUNTRY = r"_\d{4}_([^/]+)\.csv$"  # pulls the country name out of each CSV's filename
con = duckdb.connect()
con.sql(f"""CREATE SECRET r2 (TYPE r2,
  KEY_ID '{os.environ["R2_KEY_ID"]}', SECRET '{os.environ["R2_SECRET"]}',
  ACCOUNT_ID '{os.environ["CF_ACCOUNT_ID"]}')""")

failed = []
for sensor, zname, year in JOBS:
    out = f"r2://firms-data/raw/{sensor}/{year}.parquet"
    try:  # skip years that are already in R2, so the script can be safely re-run
        con.sql(f"SELECT 1 FROM '{out}' LIMIT 1").fetchall()
        print(f"skip {sensor} {year} (already in R2)", flush=True)
        continue
    except Exception:
        pass
    t0 = time.time()
    tmp = pathlib.Path("tmp"); shutil.rmtree(tmp, ignore_errors=True); tmp.mkdir()
    try:
        subprocess.run(["curl", "-fsSL", "-o", str(tmp / zname), f"{BASE}/{zname}"], check=True)
        subprocess.run(["unzip", "-q", "-o", str(tmp / zname), "-d", str(tmp)], check=True)
        con.sql(f"""COPY (SELECT regexp_extract(filename, '{COUNTRY}', 1) AS country, * EXCLUDE (filename)
                         FROM read_csv('{tmp}/**/*.csv', union_by_name=true, filename=true)
                         ORDER BY country)
                    TO '{out}' (FORMAT parquet, COMPRESSION zstd)""")
        print(f"done {sensor} {year} in {time.time() - t0:.0f}s", flush=True)
    except Exception as e:
        failed.append((sensor, year))
        print(f"FAILED {sensor} {year}: {e}", flush=True)
shutil.rmtree("tmp", ignore_errors=True)

if "test" in sys.argv:
    con.sql("""SELECT country, count(*) AS detections FROM 'r2://firms-data/raw/modis/2000.parquet'
               GROUP BY 1 ORDER BY 2 DESC LIMIT 5""").show()
print("failed:", failed or "none")