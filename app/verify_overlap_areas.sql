-- Kontrola dwoch naprawianych warstw: 3 siatki, tylko odczyt.
-- Oczekiwany wynik po udanej naprawie: 0 w kolumnach przekroczen.
WITH powiat AS (
    SELECT ST_UnaryUnion(ST_Collect(ST_MakeValid(geom))) AS geom
    FROM public.powiat
),
komorki AS (
    SELECT 'h3_r6'::text AS siatka, h3_id, geom,
           ot_adja_a_area_m2 AS adja_m2,
           ot_adms_a_area_m2 AS adms_m2
    FROM grid.h3_r6
    UNION ALL
    SELECT 'h3_r7', h3_id, geom,
           ot_adja_a_area_m2, ot_adms_a_area_m2
    FROM grid.h3_r7
    UNION ALL
    SELECT 'h3_r8', h3_id, geom,
           ot_adja_a_area_m2, ot_adms_a_area_m2
    FROM grid.h3_r8
),
pola AS (
    SELECT k.siatka, k.h3_id, k.adja_m2, k.adms_m2,
           ST_Area(ST_CollectionExtract(
               ST_Intersection(k.geom, p.geom), 3
           )) AS limit_m2
    FROM komorki k CROSS JOIN powiat p
)
SELECT siatka,
       count(*) AS liczba_heksagonow,
       count(*) FILTER (
           WHERE adja_m2 IS NULL
              OR adja_m2 < -0.01
              OR adja_m2 > limit_m2 + 0.01
       ) AS bledne_adja,
       count(*) FILTER (
           WHERE adms_m2 IS NULL
              OR adms_m2 < -0.01
              OR adms_m2 > limit_m2 + 0.01
       ) AS bledne_adms,
       round(max(adja_m2 / NULLIF(limit_m2, 0))::numeric, 6)
           AS max_udzial_adja,
       round(max(adms_m2 / NULLIF(limit_m2, 0))::numeric, 6)
           AS max_udzial_adms
FROM pola
GROUP BY siatka
ORDER BY siatka;
