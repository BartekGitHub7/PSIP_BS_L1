-- Przejezdność 0–1; NULL = jeszcze nieobliczona. Bez wymyślania wyników.
\set ON_ERROR_STOP on
BEGIN;
DO $$
DECLARE t text;
BEGIN
    FOREACH t IN ARRAY ARRAY['h3_r6','h3_r7','h3_r8'] LOOP
        IF to_regclass(format('grid.%I',t)) IS NULL THEN
            RAISE EXCEPTION 'Brak tabeli grid.% — najpierw załaduj siatkę', t;
        END IF;
        EXECUTE format('ALTER TABLE grid.%I ADD COLUMN IF NOT EXISTS przejezdnosc double precision',t);
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint
            WHERE conrelid=to_regclass(format('grid.%I',t))
              AND conname='przejezdnosc_range_0_1'
        ) THEN
            EXECUTE format('ALTER TABLE grid.%I ADD CONSTRAINT przejezdnosc_range_0_1 '
                           'CHECK (przejezdnosc IS NULL OR przejezdnosc BETWEEN 0 AND 1)',t);
        END IF;
        EXECUTE format('COMMENT ON COLUMN grid.%I.przejezdnosc IS %L',t,
                       'Wskaźnik 0–1: 0 nieprzejezdne, 1 przejezdne. NULL = brak obliczeń.');
    END LOOP;
END $$;
COMMIT;
SELECT 'h3_r6' AS siatka,count(*) AS komorki,count(przejezdnosc) AS z_wynikiem FROM grid.h3_r6
UNION ALL SELECT 'h3_r7',count(*),count(przejezdnosc) FROM grid.h3_r7
UNION ALL SELECT 'h3_r8',count(*),count(przejezdnosc) FROM grid.h3_r8;
