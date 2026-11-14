import duckdb, os, time

con = duckdb.connect("analysis.duckdb")
con.sql(f"""CREATE OR REPLACE SECRET r2 (TYPE r2, KEY_ID '{os.environ["R2_KEY_ID"]}',
  SECRET '{os.environ["R2_SECRET"]}', ACCOUNT_ID '{os.environ["CF_ACCOUNT_ID"]}')""")
M = "'r2://firms-data/raw/modis/*.parquet'"
V = "'r2://firms-data/raw/viirs_noaa20/*.parquet'"
SAT = "CASE WHEN satellite IN ('T','Terra') THEN 'Terra' WHEN satellite IN ('A','Aqua') THEN 'Aqua' ELSE satellite END"
MCONF = "TRY_CAST(confidence AS INTEGER)"

def show(title, sql, rows=60):
    print(f"\n=== {title} ===")
    con.sql(sql).show(max_rows=rows, max_width=250)

t0 = time.time()
con.sql(f"""CREATE OR REPLACE TABLE agg AS
SELECT 'MODIS' AS sensor, {SAT} AS sat, country, year(acq_date) AS yr, month(acq_date) AS mo, type, daynight,
       CASE WHEN {MCONF} IS NULL THEN 'other' WHEN {MCONF} < 30 THEN 'low'
            WHEN {MCONF} < 80 THEN 'nominal' ELSE 'high' END AS conf,
       count(*) AS n, sum(frp) AS frp_sum
FROM {M} GROUP BY ALL
UNION ALL
SELECT 'VIIRS', satellite, country, year(acq_date), month(acq_date), type, daynight,
       CASE lower(CAST(confidence AS VARCHAR)) WHEN 'l' THEN 'low' WHEN 'n' THEN 'nominal'
            WHEN 'h' THEN 'high' ELSE 'other' END,
       count(*), sum(frp)
FROM {V} GROUP BY ALL""")
con.sql(f"""CREATE OR REPLACE TABLE daily AS
SELECT 'MODIS' AS sensor, {SAT} AS sat, acq_date, count(*) AS n FROM {M} GROUP BY ALL
UNION ALL
SELECT 'VIIRS', satellite, acq_date, count(*) FROM {V} GROUP BY ALL""")
con.sql("COPY agg TO 'r2://firms-data/analysis/agg_monthly.parquet' (FORMAT parquet)")
print(f"Aggregated in {time.time() - t0:.0f}s")

show("Satellite labels", "SELECT sensor, sat, sum(n) AS n FROM agg GROUP BY ALL ORDER BY ALL")

show("Detections per year by satellite", """
SELECT yr,
       sum(n) FILTER (sat = 'Terra') AS terra,
       sum(n) FILTER (sat = 'Aqua')  AS aqua,
       sum(n) FILTER (sensor = 'VIIRS') AS viirs_noaa20
FROM agg GROUP BY yr ORDER BY yr""")

show("Detection type (0=vegetation fire, 1=volcano, 2=static/industrial, 3=offshore)", """
SELECT sensor, type, sum(n) AS n,
       round(100 * sum(n) / sum(sum(n)) OVER (PARTITION BY sensor), 2) AS pct
FROM agg GROUP BY ALL ORDER BY sensor, type""")

show("Confidence mix", """
SELECT sensor, conf, sum(n) AS n,
       round(100 * sum(n) / sum(sum(n)) OVER (PARTITION BY sensor), 1) AS pct
FROM agg GROUP BY ALL ORDER BY sensor, conf""")

show("Day vs night by satellite", """
SELECT sensor, sat, daynight, sum(n) AS n,
       round(100 * sum(n) / sum(sum(n)) OVER (PARTITION BY sensor, sat), 1) AS pct
FROM agg GROUP BY ALL ORDER BY sensor, sat, daynight""")

OVERLAP = "yr BETWEEN 2019 AND 2025 AND type = 0 AND conf <> 'low'"

show("VIIRS per MODIS-Aqua detection, by calendar month (global, 2019-2025)", f"""
SELECT mo,
       sum(n) FILTER (sensor = 'VIIRS') AS viirs,
       sum(n) FILTER (sat = 'Aqua')     AS aqua,
       round(sum(n) FILTER (sensor = 'VIIRS') / sum(n) FILTER (sat = 'Aqua'), 2) AS viirs_per_aqua
FROM agg WHERE {OVERLAP} GROUP BY mo ORDER BY mo""")

show("VIIRS per MODIS-Aqua detection, top 15 countries (2019-2025)", f"""
SELECT country,
       sum(n) FILTER (sensor = 'VIIRS') AS viirs,
       sum(n) FILTER (sat = 'Aqua')     AS aqua,
       round(sum(n) FILTER (sensor = 'VIIRS') / sum(n) FILTER (sat = 'Aqua'), 2) AS viirs_per_aqua
FROM agg WHERE {OVERLAP} GROUP BY country ORDER BY aqua DESC LIMIT 15""")

show("Average fire intensity (FRP, MW) per detection, 2019-2025 vegetation fires", """
SELECT sensor, sat, round(sum(frp_sum) / sum(n), 1) AS avg_frp_mw
FROM agg WHERE yr BETWEEN 2019 AND 2025 AND type = 0 GROUP BY ALL ORDER BY ALL""")

show("Argentina burning calendar: MODIS vegetation-fire detections (year x month)", """
PIVOT (SELECT yr, mo, n FROM agg WHERE sensor = 'MODIS' AND country = 'Argentina' AND type = 0)
ON mo USING sum(n) GROUP BY yr ORDER BY yr""")

show("Days with any data per year (gaps = satellite outages)", """
SELECT year(acq_date) AS yr,
       count(*) FILTER (sat = 'Terra') AS terra_days,
       count(*) FILTER (sat = 'Aqua')  AS aqua_days,
       count(*) FILTER (sensor = 'VIIRS') AS viirs_days
FROM daily GROUP BY yr ORDER BY yr""")