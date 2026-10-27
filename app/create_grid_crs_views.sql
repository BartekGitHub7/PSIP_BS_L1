BEGIN;

DO $$
DECLARE
    source_name text;
    attributes text;
BEGIN
    FOREACH source_name IN ARRAY ARRAY['h3_r6', 'h3_r7', 'h3_r8']
    LOOP
        -- Widok z oryginalna geometria w EPSG:2180.
        EXECUTE format(
            'CREATE OR REPLACE VIEW grid.%I AS
             SELECT * FROM grid.%I',
            source_name || '_2180',
            source_name
        );

        -- Lista wszystkich atrybutow poza geometria.
        SELECT string_agg(
            format('h.%I', column_name),
            ', ' ORDER BY ordinal_position
        )
        INTO attributes
        FROM information_schema.columns
        WHERE table_schema = 'grid'
          AND table_name = source_name
          AND column_name <> 'geom';

        -- Odtworzenie widoku, jesli powstal poprzednia komenda.
        EXECUTE format(
            'DROP VIEW IF EXISTS grid.%I',
            source_name || '_3857'
        );

        -- Atrybuty pozostaja, przeliczamy tylko geometrie.
        EXECUTE format(
            'CREATE VIEW grid.%I AS
             SELECT %s,
                    ST_Transform(h.geom, 3857)
                        ::geometry(MultiPolygon, 3857) AS geom
             FROM grid.%I h',
            source_name || '_3857',
            attributes,
            source_name
        );
    END LOOP;
END
$$;

COMMIT;