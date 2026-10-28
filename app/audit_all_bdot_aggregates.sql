-- Audyt WSZYSTKICH 68 agregatow z BDOT10k na 3 siatkach H3.
-- Niczego nie zmienia w tabelach grid/bdot: tworzy tylko tabele tymczasowe.
-- Kontroluje: suma H3 vs niezalezne obliczenie z BDOT10k, NULL,
-- wartosci ujemne/niefinitywne, ulamkowe liczniki i pola > powierzchnia komorki.
-- UWAGA: moze obciazyc lokalny PostGIS (odczyt geometrii 68 warstw).

CREATE TEMP TABLE audit_h3_cell_limits AS
WITH powiat AS (
    SELECT ST_UnaryUnion(ST_Collect(ST_MakeValid(geom))) AS geom
    FROM public.powiat
)
SELECT 'h3_r6'::text AS siatka, g.h3_id::text AS h3_id,
       ST_Area(ST_CollectionExtract(ST_Intersection(g.geom,p.geom),3)) AS limit_m2
FROM grid.h3_r6 g CROSS JOIN powiat p
UNION ALL
SELECT 'h3_r7', g.h3_id::text,
       ST_Area(ST_CollectionExtract(ST_Intersection(g.geom,p.geom),3))
FROM grid.h3_r7 g CROSS JOIN powiat p
UNION ALL
SELECT 'h3_r8', g.h3_id::text,
       ST_Area(ST_CollectionExtract(ST_Intersection(g.geom,p.geom),3))
FROM grid.h3_r8 g CROSS JOIN powiat p;

CREATE INDEX ON audit_h3_cell_limits (siatka, h3_id);
ANALYZE audit_h3_cell_limits;

CREATE TEMP TABLE audit_h3_metric_results (
    siatka text,
    kolumna text,
    typ text,
    suma_h3 double precision,
    wartosc_bdot double precision,
    roznica double precision,
    tolerancja double precision,
    brakujace bigint,
    ujemne_lub_niefinitywne bigint,
    ulamkowe_liczniki bigint,
    przekroczenia_pola bigint,
    wynik text
);

DO $$
DECLARE
    source_layer record;
    grid_name text;
    target_col text;
    metric_type text;
    powiat_geom geometry;
    ref_value double precision;
    grid_value double precision;
    tol double precision;
    empty_rows bigint;
    invalid_rows bigint;
    fractional_rows bigint;
    too_large_rows bigint;
    result_status text;
BEGIN
    SELECT ST_UnaryUnion(ST_Collect(ST_MakeValid(geom)))
    INTO powiat_geom
    FROM public.powiat;

    IF powiat_geom IS NULL OR ST_IsEmpty(powiat_geom) THEN
        RAISE EXCEPTION 'Nieprawidlowa lub pusta geometria public.powiat';
    END IF;

    FOR source_layer IN
        SELECT f_table_name AS table_name
        FROM public.geometry_columns
        WHERE f_table_schema = 'bdot'
          AND f_geometry_column = 'geom'
          AND f_table_name ~ '^ot_[a-z0-9]+_[alp]$'
        ORDER BY f_table_name
    LOOP
        IF right(source_layer.table_name,2) = '_a' THEN
            target_col := source_layer.table_name || '_area_m2';
            metric_type := 'powierzchnia';

            IF source_layer.table_name IN ('ot_adja_a','ot_adms_a') THEN
                -- To powierzchnia unii poligonow, zgodnie z naprawiona agregacja.
                EXECUTE format(
                    'SELECT COALESCE(ST_Area(ST_UnaryUnion(ST_Collect(
                        ST_CollectionExtract(ST_Intersection(b.geom,$1),3)
                     ))),0)
                     FROM bdot.%I b
                     WHERE ST_Intersects(b.geom,$1)',
                    source_layer.table_name
                ) INTO ref_value USING powiat_geom;
            ELSE
                -- Pozostale warstwy: suma pol obiektow (jak w dotychczasowym kodzie).
                EXECUTE format(
                    'SELECT COALESCE(SUM(ST_Area(ST_CollectionExtract(
                         ST_Intersection(b.geom,$1),3
                     ))),0)
                     FROM bdot.%I b
                     WHERE ST_Intersects(b.geom,$1)',
                    source_layer.table_name
                ) INTO ref_value USING powiat_geom;
            END IF;

        ELSIF right(source_layer.table_name,2) = '_l' THEN
            target_col := source_layer.table_name || '_length_m';
            metric_type := 'dlugosc';
            -- Dla linii w calosci zawartych w powiecie uzywamy
            -- oryginalnej dlugosci. Na 8 poprawnych geometriach
            -- ST_Within = TRUE, ale ST_Intersection zwracal EMPTY,
            -- sztucznie zanizajac wartosc kontrolna.
            EXECUTE format(
                'SELECT COALESCE(SUM(
                     CASE WHEN ST_Covers($1,b.geom)
                          THEN ST_Length(b.geom)
                          ELSE ST_Length(ST_CollectionExtract(
                              ST_Intersection(b.geom,$1),2
                          ))
                     END
                 ),0)
                 FROM bdot.%I b
                 WHERE ST_Intersects(b.geom,$1)',
                source_layer.table_name
            ) INTO ref_value USING powiat_geom;

        ELSE
            target_col := source_layer.table_name || '_count';
            metric_type := 'liczba';
            EXECUTE format(
                'SELECT count(*)::double precision
                 FROM bdot.%I b WHERE ST_Intersects(b.geom,$1)',
                source_layer.table_name
            ) INTO ref_value USING powiat_geom;
        END IF;

        FOREACH grid_name IN ARRAY ARRAY['h3_r6','h3_r7','h3_r8']
        LOOP
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns AS c
                WHERE c.table_schema = 'grid'
                  AND c.table_name = grid_name
                  AND c.column_name = target_col
            ) THEN
                RAISE EXCEPTION 'Brak kolumny grid.%.%',grid_name,target_col;
            END IF;

            EXECUTE format(
                'SELECT COALESCE(SUM(g.%1$I),0),
                        count(*) FILTER (WHERE g.%1$I IS NULL),
                        count(*) FILTER (WHERE g.%1$I < 0 OR
                          g.%1$I::text IN (''NaN'',''Infinity'',''-Infinity'')),
                        count(*) FILTER (WHERE g.%1$I <> round(g.%1$I))
                 FROM grid.%2$I g',
                target_col,grid_name
            ) INTO grid_value,empty_rows,invalid_rows,fractional_rows;

            IF metric_type = 'powierzchnia' THEN
                EXECUTE format(
                    'SELECT count(*)
                     FROM grid.%I g
                     JOIN audit_h3_cell_limits l
                       ON l.siatka=%L AND l.h3_id=g.h3_id::text
                     WHERE g.%I > l.limit_m2 + 0.01',
                    grid_name,grid_name,target_col
                ) INTO too_large_rows;
            ELSE
                too_large_rows := 0;
            END IF;

            IF metric_type = 'liczba' THEN
                tol := 0.000001;
            ELSE
                tol := greatest(0.1,abs(ref_value) * 0.00000001);
                fractional_rows := 0;
            END IF;

            result_status :=
                CASE WHEN empty_rows>0 OR invalid_rows>0
                    OR fractional_rows>0 OR too_large_rows>0
                    OR abs(grid_value-ref_value)>tol
                  THEN 'DO_SPRAWDZENIA' ELSE 'OK' END;

            INSERT INTO audit_h3_metric_results
                (siatka,kolumna,typ,suma_h3,wartosc_bdot,roznica,
                 tolerancja,brakujace,ujemne_lub_niefinitywne,
                 ulamkowe_liczniki,przekroczenia_pola,wynik)
            VALUES
                (grid_name,target_col,metric_type,grid_value,ref_value,
                 grid_value-ref_value,tol,empty_rows,invalid_rows,
                 fractional_rows,too_large_rows,result_status);
        END LOOP;
    END LOOP;
END
$$;

-- PODSUMOWANIE: dla 68 warstw powinno byc po 68 wierszy i 0 problemow.
SELECT siatka,
       count(*) AS sprawdzone_kolumny,
       count(*) FILTER (WHERE wynik='OK') AS poprawne,
       count(*) FILTER (WHERE wynik<>'OK') AS do_sprawdzenia,
       sum(przekroczenia_pola) AS przekroczenia_pola,
       sum(brakujace) AS puste,
       sum(ujemne_lub_niefinitywne) AS wartosci_nieprawidlowe,
       sum(ulamkowe_liczniki) AS liczniki_niecalkowite
FROM audit_h3_metric_results
GROUP BY siatka ORDER BY siatka;

-- SZCZEGOLY: tylko warstwy wymagajace uwagi. Pusta tabela = brak wykrytych problemow.
SELECT siatka,kolumna,typ,
       round(suma_h3::numeric,3) AS suma_h3,
       round(wartosc_bdot::numeric,3) AS suma_z_bdot,
       round(roznica::numeric,3) AS roznica,
       round(tolerancja::numeric,3) AS tolerancja,
       brakujace,ujemne_lub_niefinitywne,ulamkowe_liczniki,
       przekroczenia_pola,wynik
FROM audit_h3_metric_results
WHERE wynik<>'OK'
ORDER BY siatka,kolumna;
