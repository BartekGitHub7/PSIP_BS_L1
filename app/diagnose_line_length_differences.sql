-- Odczyn diagnostyczny 9 roznic dlugosci wykrytych w audycie 68 kolumn.
-- Tylko odczyt tabel grid/bdot/public. Wyniki zapisuje do tabel tymczasowych.
-- Dla kazdego problematycznego obiektu porownuje dlugosc w powiecie
-- z suma dlugosci fragmentow we WSZYSTKICH komorkach danej siatki.
-- Zero wierszy w szczegolach wskazuje, ze nie stwierdzono roznic > 0.001 m
-- na poziomie pojedynczego obiektu (nawet jesli suma roznic jest niezerowa).

CREATE TEMP TABLE audit_line_object_diffs (
    siatka text NOT NULL,
    warstwa text NOT NULL,
    ogc_fid bigint NOT NULL,
    dlugosc_z_bdot_m double precision,
    dlugosc_z_komorek_m double precision,
    roznica_m double precision
);

DO $$
DECLARE
    grid_name text;
    lyr record;
    inserted_rows bigint;
BEGIN
    FOREACH grid_name IN ARRAY ARRAY['h3_r6', 'h3_r7', 'h3_r8']
    LOOP
        DROP TABLE IF EXISTS pg_temp.audit_line_clipped_cells;
        EXECUTE format(
            'CREATE TEMP TABLE audit_line_clipped_cells AS
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
        CREATE INDEX ON audit_line_clipped_cells USING gist (geom);
        ANALYZE audit_line_clipped_cells;

        FOR lyr IN
            SELECT warstwa
            FROM (VALUES
                ('h3_r6', 'ot_oipr_l'),
                ('h3_r6', 'ot_skrp_l'),
                ('h3_r6', 'ot_swrm_l'),
                ('h3_r7', 'ot_oipr_l'),
                ('h3_r7', 'ot_skrp_l'),
                ('h3_r7', 'ot_swrm_l'),
                ('h3_r8', 'ot_skdr_l'),
                ('h3_r8', 'ot_skjz_l'),
                ('h3_r8', 'ot_swrm_l')
            ) AS x(siatka, warstwa)
            WHERE siatka = grid_name
        LOOP
            RAISE NOTICE 'Sprawdzam grid.% / bdot.%', grid_name, lyr.warstwa;

            EXECUTE format(
                'INSERT INTO audit_line_object_diffs (
                    siatka, warstwa, ogc_fid,
                    dlugosc_z_bdot_m, dlugosc_z_komorek_m, roznica_m
                 )
                 SELECT %L, %L, b.ogc_fid,
                        source_part.source_m, cell_parts.cells_m,
                        cell_parts.cells_m - source_part.source_m
                 FROM bdot.%I b
                 CROSS JOIN (
                     SELECT ST_UnaryUnion(
                         ST_Collect(ST_MakeValid(geom))
                     ) AS geom
                     FROM public.powiat
                 ) p
                 CROSS JOIN LATERAL (
                     SELECT ST_Length(ST_CollectionExtract(
                         ST_Intersection(b.geom, p.geom), 2
                     )) AS source_m
                 ) source_part
                 CROSS JOIN LATERAL (
                     SELECT COALESCE(SUM(
                         ST_Length(ST_CollectionExtract(
                             ST_Intersection(c.geom, b.geom), 2
                         ))
                     ), 0) AS cells_m
                     FROM audit_line_clipped_cells c
                     WHERE ST_Intersects(c.geom, b.geom)
                 ) cell_parts
                 WHERE ST_Intersects(b.geom, p.geom)
                   AND abs(cell_parts.cells_m - source_part.source_m) > 0.001',
                grid_name, lyr.warstwa, lyr.warstwa
            );
            GET DIAGNOSTICS inserted_rows = ROW_COUNT;
            RAISE NOTICE 'Rozbieznosci obiektow > 1 mm: %', inserted_rows;
        END LOOP;
    END LOOP;
END
$$;

-- PODSUMOWANIE: 9 kombinacji siatka-warstwa.
SELECT x.siatka, x.warstwa,
       count(d.ogc_fid) AS obiekty_z_roznica,
       round(COALESCE(sum(d.roznica_m),0)::numeric,3) AS suma_roznic_m,
       round(COALESCE(max(abs(d.roznica_m)),0)::numeric,3) AS max_roznica_na_obiekt_m
FROM (VALUES
    ('h3_r6','ot_oipr_l'), ('h3_r6','ot_skrp_l'), ('h3_r6','ot_swrm_l'),
    ('h3_r7','ot_oipr_l'), ('h3_r7','ot_skrp_l'), ('h3_r7','ot_swrm_l'),
    ('h3_r8','ot_skdr_l'), ('h3_r8','ot_skjz_l'), ('h3_r8','ot_swrm_l')
) AS x(siatka,warstwa)
LEFT JOIN audit_line_object_diffs d
  ON d.siatka = x.siatka AND d.warstwa = x.warstwa
GROUP BY x.siatka, x.warstwa
ORDER BY x.siatka, x.warstwa;

-- Najwieksze roznice wraz z identyfikatorem oryginalnego obiektu BDOT.
SELECT siatka, warstwa, ogc_fid,
       round(dlugosc_z_bdot_m::numeric,3) AS dlugosc_bdot_m,
       round(dlugosc_z_komorek_m::numeric,3) AS dlugosc_w_heksagonach_m,
       round(roznica_m::numeric,3) AS roznica_m
FROM audit_line_object_diffs
ORDER BY abs(roznica_m) DESC
LIMIT 30;
