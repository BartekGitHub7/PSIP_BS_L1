-- Jednorazowa, bezpieczna korekta zagregowanych pol powierzchni.
-- Dotyczy TYLKO bdot.ot_adja_a i bdot.ot_adms_a dla h3_r6/r7/r8.
-- Nie modyfikuje danych zrodlowych ani pozostalych kolumn.
-- Calosc dziala w transakcji; nieudana walidacja oznacza ROLLBACK.

BEGIN;

CREATE SCHEMA IF NOT EXISTS audit;

CREATE TABLE IF NOT EXISTS audit.bdot_overlap_area_backup (
    grid_name text NOT NULL,
    h3_id text NOT NULL,
    ot_adja_a_area_m2 double precision,
    ot_adms_a_area_m2 double precision,
    backed_up_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (grid_name, h3_id)
);

DO $$
DECLARE
    grid_name text;
    source_name text;
    target_col text;
    powiat_geom geometry;
    rows_changed bigint;
    bad_rows bigint;
    backup_rows bigint;
BEGIN
    -- Wymagane tabele/kolumny: przerwij, zanim cokolwiek przeliczymy.
    FOREACH grid_name IN ARRAY ARRAY['h3_r6', 'h3_r7', 'h3_r8']
    LOOP
        IF to_regclass(format('grid.%I', grid_name)) IS NULL THEN
            RAISE EXCEPTION 'Brak tabeli grid.%', grid_name;
        END IF;

        FOREACH source_name IN ARRAY ARRAY['ot_adja_a', 'ot_adms_a']
        LOOP
            target_col := source_name || '_area_m2';
            IF to_regclass(format('bdot.%I', source_name)) IS NULL THEN
                RAISE EXCEPTION 'Brak tabeli bdot.%', source_name;
            END IF;
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns AS c
                WHERE table_schema = 'grid'
                  AND table_name = grid_name
                  AND c.column_name = target_col
            ) THEN
                RAISE EXCEPTION 'Brak kolumny grid.%.%', grid_name, target_col;
            END IF;
        END LOOP;
    END LOOP;

    SELECT ST_UnaryUnion(ST_Collect(ST_MakeValid(geom)))
    INTO powiat_geom
    FROM public.powiat;

    IF powiat_geom IS NULL OR ST_IsEmpty(powiat_geom) THEN
        RAISE EXCEPTION 'Brak prawidlowej geometrii powiatu';
    END IF;

    FOREACH grid_name IN ARRAY ARRAY['h3_r6', 'h3_r7', 'h3_r8']
    LOOP
        -- Migawka pierwotnych wynikow: ponowne uruchomienie jej nie nadpisze.
        EXECUTE format(
            'INSERT INTO audit.bdot_overlap_area_backup
                 (grid_name, h3_id, ot_adja_a_area_m2, ot_adms_a_area_m2)
             SELECT %L, h3_id::text,
                    ot_adja_a_area_m2, ot_adms_a_area_m2
             FROM grid.%I
             ON CONFLICT (grid_name, h3_id) DO NOTHING',
            grid_name, grid_name
        );
        GET DIAGNOSTICS backup_rows = ROW_COUNT;
        RAISE NOTICE 'grid.%: zapisano % pierwotnych wierszy do backupu',
            grid_name, backup_rows;

        DROP TABLE IF EXISTS pg_temp.clipped_cells;
        EXECUTE format(
            'CREATE TEMP TABLE clipped_cells ON COMMIT DROP AS
             SELECT g.h3_id,
                    ST_CollectionExtract(
                        ST_Intersection(g.geom, $1), 3
                    ) AS geom
             FROM grid.%I g',
            grid_name
        ) USING powiat_geom;

        CREATE INDEX ON clipped_cells USING gist (geom);
        CREATE INDEX ON clipped_cells (h3_id);
        ANALYZE clipped_cells;

        FOREACH source_name IN ARRAY ARRAY['ot_adja_a', 'ot_adms_a']
        LOOP
            target_col := source_name || '_area_m2';

            -- ST_Collect + ST_UnaryUnion usuwa wielokrotne pokrycie
            -- wewnatrz JEDNEJ warstwy. Nie laczymy roznych warstw BDOT.
            EXECUTE format(
                'UPDATE grid.%I g
                 SET %I = COALESCE((
                     SELECT ST_Area(ST_UnaryUnion(ST_Collect(
                         ST_CollectionExtract(
                             ST_Intersection(c.geom, b.geom), 3
                         )
                     )))
                     FROM clipped_cells c
                     JOIN bdot.%I b
                       ON ST_Intersects(c.geom, b.geom)
                     WHERE c.h3_id = g.h3_id
                 ), 0)',
                grid_name, target_col, source_name
            );
            GET DIAGNOSTICS rows_changed = ROW_COUNT;

            -- Kazda pojedyncza miara powierzchni powinna zmiescic sie
            -- w czesci heksagonu polozonej wewnatrz powiatu.
            EXECUTE format(
                'SELECT count(*)
                 FROM grid.%I g
                 WHERE g.%I IS NULL
                    OR g.%I < -0.01
                    OR g.%I > ST_Area(
                        ST_CollectionExtract(
                            ST_Intersection(g.geom, $1), 3
                        )
                    ) + 0.01',
                grid_name, target_col, target_col, target_col
            ) INTO bad_rows USING powiat_geom;

            IF bad_rows > 0 THEN
                RAISE EXCEPTION
                    'Walidacja NIEPOWODZENIE: grid.%, kolumna %, % blednych wierszy. Transakcja wycofana.',
                    grid_name, target_col, bad_rows;
            END IF;

            RAISE NOTICE 'OK: grid.%, %: % wierszy zaktualizowano, 0 przekroczen',
                grid_name, target_col, rows_changed;
        END LOOP;
    END LOOP;
END
$$;

COMMIT;
