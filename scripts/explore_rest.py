import duckdb

con = duckdb.connect("analysis.duckdb", read_only=True)

def show(title, sql, rows=60):
    print(f"\n=== {title} ===", flush=True)
    con.sql(sql).show(max_rows=rows, max_width=250)

def share(title, cols, part="sensor"):
    show(title, f"""
    SELECT {cols}, n, round(100 * n / sum(n) OVER (PARTITION BY {part}), 2) AS pct
    FROM (SELECT {cols}, sum(n) AS n FROM agg GROUP BY {cols})
    ORDER BY {cols}""")

share("Detection type (0=vegetation fire, 1=volcano, 2=static/industrial, 3=offshore)", "sensor, type")
share("Confidence mix", "sensor, conf")
share("Day vs night by satellite", "sensor, sat, daynight", part="sensor, sat")

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
FROM agg WHERE yr BETWEEN 2019 AND 2025 AND type = 0 GROUP BY sensor, sat ORDER BY sensor, sat""")

show("2024 vs 2025 by month (is 2025 complete?)", """
SELECT mo,
       sum(n) FILTER (yr = 2024 AND sat = 'Aqua')      AS aqua_2024,
       sum(n) FILTER (yr = 2025 AND sat = 'Aqua')      AS aqua_2025,
       sum(n) FILTER (yr = 2024 AND sensor = 'VIIRS')  AS viirs_2024,
       sum(n) FILTER (yr = 2025 AND sensor = 'VIIRS')  AS viirs_2025
FROM agg GROUP BY mo ORDER BY mo""")

show("Argentina burning calendar: MODIS vegetation-fire detections (year x month)", """
PIVOT (SELECT yr, mo, n FROM agg WHERE sensor = 'MODIS' AND country = 'Argentina' AND type = 0)
ON mo USING sum(n) GROUP BY yr ORDER BY yr""")

show("Days with any data per year (gaps = satellite outages)", """
SELECT year(acq_date) AS yr,
       count(*) FILTER (sat = 'Terra') AS terra_days,
       count(*) FILTER (sat = 'Aqua')  AS aqua_days,
       count(*) FILTER (sensor = 'VIIRS') AS viirs_days
FROM daily GROUP BY yr ORDER BY yr""")