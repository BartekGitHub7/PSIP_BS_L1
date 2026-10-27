-- Naprawa 5 warstw liniowych z zachowaniem poprzednich wartosci.
-- Jedna transakcja, rollback przy niezgodnosci sum (0.1 m).
-- Wylacznie env-test. Nie importuje ponownie siatek ani danych BDOT.
BEGIN;
CREATE SCHEMA IF NOT EXISTS audit;
CREATE TABLE IF NOT EXISTS audit.bdot_line_lengths_backup (
    grid_name text NOT NULL, h3_id text NOT NULL,
    ot_oipr_l_length_m double precision,
    ot_skdr_l_length_m double precision,
    ot_skjz_l_length_m double precision,
    ot_skrp_l_length_m double precision,
    ot_swrm_l_length_m double precision,
    backed_up_at timestamptz DEFAULT now() NOT NULL,
    PRIMARY KEY (grid_name,h3_id)
);

DO $$
DECLARE
    grid_name text;
    source_name text;
    target_col text;
    powiat_geom geometry;
    expected_total double precision;
    observed_total double precision;
    diff double precision;
BEGIN
    SELECT ST_UnaryUnion(ST_Collect(ST_MakeValid(geom)))
    INTO powiat_geom
    FROM public.powiat;
    IF powiat_geom IS NULL OR ST_IsEmpty(powiat_geom) THEN
        RAISE EXCEPTION 'Brak geometrii powiatu';
    END IF;

    FOREACH grid_name IN ARRAY ARRAY['h3_r6','h3_r7','h3_r8']
    LOOP
        EXECUTE format(
            'INSERT INTO audit.bdot_line_lengths_backup
              (grid_name,h3_id,ot_oipr_l_length_m,ot_skdr_l_length_m,
               ot_skjz_l_length_m,ot_skrp_l_length_m,ot_swrm_l_length_m)
             SELECT %L,h3_id::text,ot_oipr_l_length_m,ot_skdr_l_length_m,
                    ot_skjz_l_length_m,ot_skrp_l_length_m,ot_swrm_l_length_m
             FROM grid.%I
             ON CONFLICT (grid_name,h3_id) DO NOTHING',
            grid_name,grid_name
        );

        DROP TABLE IF EXISTS pg_temp.repair_line_cells;
        EXECUTE format(
            'CREATE TEMP TABLE repair_line_cells ON COMMIT DROP AS
             SELECT g.h3_id,ST_CollectionExtract(
                ST_Intersection(g.geom,p.geom),3
             ) AS geom
             FROM grid.%I g
             CROSS JOIN (
                SELECT ST_UnaryUnion(ST_Collect(ST_MakeValid(geom))) AS geom
                FROM public.powiat
             ) p',
            grid_name
        );
        CREATE INDEX ON repair_line_cells USING gist(geom);
        CREATE INDEX ON repair_line_cells(h3_id);
        ANALYZE repair_line_cells;

        FOREACH source_name IN ARRAY ARRAY[
          'ot_oipr_l','ot_skdr_l','ot_skjz_l','ot_skrp_l','ot_swrm_l'
        ]
        LOOP
            target_col := source_name || '_length_m';

            EXECUTE format(
                'UPDATE grid.%I g
                 SET %I=COALESCE((
                    SELECT SUM(CASE WHEN ST_Covers(c.geom,b.geom)
                      THEN ST_Length(b.geom)
                      ELSE ST_Length(ST_CollectionExtract(
                        ST_Intersection(c.geom,b.geom),2
                      )) END)
                    FROM repair_line_cells c JOIN bdot.%I b
                      ON ST_Intersects(c.geom,b.geom)
                    WHERE c.h3_id=g.h3_id
                 ),0)',
                 grid_name,target_col,source_name
            );

            -- Niezalezna kontrola wzgledem geometrii zrodlowych.
            EXECUTE format(
                'SELECT COALESCE(SUM(CASE
                    WHEN ST_Covers($1,b.geom)
                      THEN ST_Length(b.geom)
                    ELSE ST_Length(ST_CollectionExtract(
                      ST_Intersection(b.geom,$1),2
                    ))
                 END),0)
                 FROM bdot.%I b WHERE ST_Intersects(b.geom,$1)',
                 source_name
            ) INTO expected_total USING powiat_geom;

            EXECUTE format('SELECT COALESCE(SUM(%I),0) FROM grid.%I',
                           target_col,grid_name)
            INTO observed_total;

            diff := observed_total - expected_total;
            RAISE NOTICE 'grid.%, %: H3=%, BDOT=%, roznica=% m',
                grid_name,target_col,observed_total,expected_total,diff;

            IF NOT isfinite(diff) OR abs(diff)>0.1 THEN
                RAISE EXCEPTION
                  'Walidacja nieudana: grid.%, %, roznica % m. ROLLBACK.',
                  grid_name,target_col,diff;
            END IF;
        END LOOP;
    END LOOP;
END
$$;
COMMIT;
