import duckdb, os
con = duckdb.connect()
con.sql(f"""CREATE SECRET r2 (TYPE r2, KEY_ID '{os.environ["R2_KEY_ID"]}',
  SECRET '{os.environ["R2_SECRET"]}', ACCOUNT_ID '{os.environ["CF_ACCOUNT_ID"]}')""")
M = "'r2://firms-data/raw/modis/*.parquet'"
V = "'r2://firms-data/raw/viirs_noaa20/*.parquet'"

print("VIIRS columns:")
con.sql(f"DESCRIBE SELECT * FROM {V}").show()

print("Totals per sensor:")
con.sql(f"""SELECT 'MODIS' AS sensor, count(*) AS detections, min(acq_date) AS first, max(acq_date) AS last FROM {M}
            UNION ALL
            SELECT 'VIIRS', count(*), min(acq_date), max(acq_date) FROM {V}""").show()

print("Argentina: MODIS vs VIIRS detections per year")
con.sql(f"""WITH m AS (SELECT year(acq_date) AS yr, count(*) AS modis FROM {M} WHERE country = 'Argentina' GROUP BY 1),
                 v AS (SELECT year(acq_date) AS yr, count(*) AS viirs FROM {V} WHERE country = 'Argentina' GROUP BY 1)
            SELECT yr, modis, viirs, round(viirs / modis, 2) AS viirs_per_modis
            FROM m LEFT JOIN v USING (yr) ORDER BY yr""").show(max_rows=40)