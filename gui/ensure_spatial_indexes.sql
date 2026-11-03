-- Uruchom na bazie TEST. Dodaje brakujące GiST na bazowych tabelach.
-- Nie zmienia danych, nazw tabel ani widoków. Może chwilowo blokować zapis.
\set ON_ERROR_STOP on
DO $$
DECLARE r record;
BEGIN
    FOR r IN
        SELECT c.oid, n.nspname, c.relname, a.attname, a.attnum
        FROM pg_class c
        JOIN pg_namespace n ON n.oid=c.relnamespace
        JOIN pg_attribute a ON a.attrelid=c.oid
        JOIN pg_type t ON t.oid=a.atttypid
        WHERE n.nspname IN ('grid','bdot','public')
          AND c.relkind IN ('r','m')
          AND a.attname='geom' AND NOT a.attisdropped
          AND t.typname='geometry'
    LOOP
        IF NOT EXISTS (
            SELECT 1 FROM pg_index i
            JOIN pg_class ix ON ix.oid=i.indexrelid
            JOIN pg_am am ON am.oid=ix.relam
            WHERE i.indrelid=r.oid AND i.indisvalid AND i.indisready
              AND am.amname='gist' AND i.indpred IS NULL
              AND r.attnum=ANY(i.indkey::smallint[])
        ) THEN
            EXECUTE format('CREATE INDEX %I ON %I.%I USING gist (%I)',
                'psip_mvt_geom_' || r.oid, r.nspname,r.relname,r.attname);
            RAISE NOTICE 'Dodano indeks: %.%',r.nspname,r.relname;
        END IF;
        EXECUTE format('ANALYZE %I.%I',r.nspname,r.relname);
    END LOOP;
END $$;
SELECT schemaname,tablename,indexname,indexdef
FROM pg_indexes WHERE schemaname IN ('grid','bdot','public')
AND indexdef ILIKE '%USING gist%' ORDER BY schemaname,tablename;
