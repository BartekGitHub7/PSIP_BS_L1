DO $$
DECLARE
    grid_name text;
    layer_record record;
    column_name text;
    measure_sql text;
    layer_count integer := 0;
BEGIN
    FOREACH grid_name IN ARRAY ARRAY['h3_r6', 'h3_r7', 'h3_r8']
    LOOP
        -- Przycinamy obszar obliczen do granicy powiatu.
        DROP TABLE IF EXISTS pg_temp.clipped_cells;

        EXECUTE format(
            'CREATE TEMP TABLE clipped_cells AS
             SELECT g.h3_id,
                    ST_CollectionExtract(
                        ST_Intersection(g.geom, p.geom), 3
                    ) AS geom
             FROM grid.%I g
             CROSS JOIN (
                 SELECT ST_UnaryUnion(
                     ST_Collect(ST_MakeValid(geom))
                 ) AS geom
                 FROM public.powiat
             ) p',
            grid_name
        );

        CREATE INDEX ON clipped_cells USING gist (geom);
        CREATE INDEX ON clipped_cells (h3_id);
        ANALYZE clipped_cells;

        FOR layer_record IN
            SELECT f_table_name AS table_name
            FROM public.geometry_columns
            WHERE f_table_schema = 'bdot'
              AND f_geometry_column = 'geom'
              AND f_table_name ~ '^ot_[a-z0-9]+_[alp]$'
            ORDER BY f_table_name
        LOOP
            IF right(layer_record.table_name, 2) = '_a' THEN
                column_name := layer_record.table_name || '_area_m2';
                -- W tych warstwach poligony moga nakladac sie na siebie.
                -- Ich zwykla suma przekracza powierzchnie pojedynczej komorki.
                IF layer_record.table_name IN ('ot_adja_a', 'ot_adms_a') THEN
                    measure_sql :=
                        'ST_Area(ST_UnaryUnion(ST_Collect(
                            ST_CollectionExtract(
                                ST_Intersection(c.geom, b.geom), 3
                            )
                        )))';
                ELSE
                    measure_sql :=
                        'SUM(ST_Area(ST_CollectionExtract(
                            ST_Intersection(c.geom, b.geom), 3)))';
                END IF;

            ELSIF right(layer_record.table_name, 2) = '_l' THEN
                column_name := layer_record.table_name || '_length_m';
                -- Intersect moze zwrocic EMPTY takze dla calej linii
                -- wewnatrz komorki. Wtedy bierzemy dlugosc oryginalu.
                measure_sql :=
                    'SUM(CASE
                        WHEN ST_Covers(c.geom, b.geom)
                            THEN ST_Length(b.geom)
                        ELSE ST_Length(ST_CollectionExtract(
                            ST_Intersection(c.geom, b.geom), 2
                        ))
                    END)';

            ELSE
                column_name := layer_record.table_name || '_count';
            END IF;

            EXECUTE format(
                'ALTER TABLE grid.%I
                 ADD COLUMN IF NOT EXISTS %I double precision',
                grid_name, column_name
            );

            RAISE NOTICE 'Obliczam grid.%: %',
                grid_name, column_name;

            IF right(layer_record.table_name, 2) = '_p' THEN
                -- Obiekt na granicy komorek liczymy tylko raz:
                -- przypisujemy go do najmniejszego h3_id.
                EXECUTE format(
                    'WITH assigned AS (
                         SELECT DISTINCT ON (b.ogc_fid)
                                b.ogc_fid, c.h3_id
                         FROM bdot.%I b
                         JOIN clipped_cells c
                           ON ST_Intersects(c.geom, b.geom)
                         ORDER BY b.ogc_fid, c.h3_id
                     ),
                     totals AS (
                         SELECT h3_id, count(*) AS value
                         FROM assigned
                         GROUP BY h3_id
                     )
                     UPDATE grid.%I g
                     SET %I = COALESCE(
                         (SELECT t.value FROM totals t
                          WHERE t.h3_id = g.h3_id), 0
                     )',
                    layer_record.table_name,
                    grid_name,
                    column_name
                );
            ELSE
                EXECUTE format(
                    'UPDATE grid.%I g
                     SET %I = COALESCE((
                         SELECT %s
                         FROM clipped_cells c
                         JOIN bdot.%I b
                           ON ST_Intersects(c.geom, b.geom)
                         WHERE c.h3_id = g.h3_id
                     ), 0)',
                    grid_name,
                    column_name,
                    measure_sql,
                    layer_record.table_name
                );
            END IF;

            layer_count := layer_count + 1;
        END LOOP;
    END LOOP;

    RAISE NOTICE 'Gotowe: obliczono % kolumn lacznie.', layer_count;
END
$$;