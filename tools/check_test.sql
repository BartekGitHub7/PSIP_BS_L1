-- Tylko odczyt; nie importuje i nie modyfikuje danych.
\set ON_ERROR_STOP on
BEGIN READ ONLY;
SELECT version();
SELECT count(*) AS obiekty_granicy FROM public.powiat;
SELECT to_jsonb(p)-'geom' AS atrybuty_granicy FROM public.powiat p LIMIT 1;
SELECT count(*) AS warstwy_bdot FROM information_schema.tables
WHERE table_schema='bdot' AND table_type='BASE TABLE';
SELECT f_table_name,srid,type FROM public.geometry_columns
WHERE f_table_schema='grid' ORDER BY f_table_name;
SELECT table_name,count(*) AS kolumny_bdot FROM information_schema.columns
WHERE table_schema='grid' AND table_name IN ('h3_r6','h3_r7','h3_r8')
AND column_name LIKE 'ot_%' GROUP BY table_name ORDER BY table_name;
SELECT table_name,column_name,data_type FROM information_schema.columns
WHERE table_schema='grid' AND table_name IN ('h3_r6','h3_r7','h3_r8')
AND column_name='przejezdnosc' ORDER BY table_name;
SELECT schemaname,tablename,indexname,indexdef FROM pg_indexes
WHERE schemaname IN ('grid','bdot','public') AND indexdef ILIKE '%USING gist%'
ORDER BY schemaname,tablename;
SELECT 'r6' AS siatka,count(*) AS komorki FROM grid.h3_r6
UNION ALL SELECT 'r7',count(*) FROM grid.h3_r7
UNION ALL SELECT 'r8',count(*) FROM grid.h3_r8;
COMMIT;
