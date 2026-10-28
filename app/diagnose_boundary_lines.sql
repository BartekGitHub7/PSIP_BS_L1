-- Diagnostyka 8 rekordow powodujacych 9 rozbieznosci dlugosci.
-- Tylko odczyt BDOT, granicy powiatu i geometrii; bez UPDATE.
-- Porownujemy przeciecie z powiatem, granice oraz bufor 10 cm.
-- Dlugosci i odleglosci w metrach (EPSG:2180).

WITH p AS MATERIALIZED (
    SELECT ST_UnaryUnion(
        ST_Collect(ST_MakeValid(geom))
    ) AS geom
    FROM public.powiat
),
b AS MATERIALIZED (
    SELECT 'ot_swrm_l'::text AS warstwa, ogc_fid, geom
    FROM bdot.ot_swrm_l WHERE ogc_fid IN (5043, 3180, 2512)
    UNION ALL
    SELECT 'ot_oipr_l', ogc_fid, geom
    FROM bdot.ot_oipr_l WHERE ogc_fid IN (2933, 3826)
    UNION ALL
    SELECT 'ot_skrp_l', ogc_fid, geom
    FROM bdot.ot_skrp_l WHERE ogc_fid = 322
    UNION ALL
    SELECT 'ot_skjz_l', ogc_fid, geom
    FROM bdot.ot_skjz_l WHERE ogc_fid = 5374
    UNION ALL
    SELECT 'ot_skdr_l', ogc_fid, geom
    FROM bdot.ot_skdr_l WHERE ogc_fid = 485
),
calc AS (
    SELECT
        b.warstwa, b.ogc_fid,
        ST_GeometryType(b.geom) AS typ_geometrii,
        ST_IsValid(b.geom) AS poprawna_geometria,
        ST_SRID(b.geom) AS srid,
        ST_Length(b.geom) AS dlugosc_oryg_m,
        ST_Distance(b.geom, p.geom) AS odleglosc_powiat_m,
        ST_Distance(b.geom, ST_Boundary(p.geom)) AS odleglosc_granica_m,
        ST_Length(ST_CollectionExtract(
            ST_Intersection(b.geom, p.geom), 2
        )) AS dlugosc_w_powiecie_m,
        ST_Length(ST_CollectionExtract(
            ST_Intersection(b.geom, ST_Boundary(p.geom)), 2
        )) AS dlugosc_na_granicy_m,
        ST_Length(ST_CollectionExtract(
            ST_Intersection(b.geom, ST_Buffer(p.geom, 0.1)), 2
        )) AS dlugosc_w_buforze_10cm_m,
        ST_Intersects(b.geom, p.geom) AS przecina_powiat,
        ST_Intersects(b.geom, ST_Boundary(p.geom)) AS dotyka_granicy
    FROM b CROSS JOIN p
)
SELECT warstwa, ogc_fid, typ_geometrii, poprawna_geometria, srid,
       round(dlugosc_oryg_m::numeric,3) AS dlugosc_oryg_m,
       round(dlugosc_w_powiecie_m::numeric,3) AS dlugosc_w_powiecie_m,
       round(odleglosc_powiat_m::numeric,6) AS odleglosc_powiat_m,
       round(odleglosc_granica_m::numeric,6) AS odleglosc_granica_m,
       round(dlugosc_na_granicy_m::numeric,3) AS dlugosc_na_granicy_m,
       round(dlugosc_w_buforze_10cm_m::numeric,3) AS dlugosc_w_buforze_10cm_m,
       przecina_powiat, dotyka_granicy
FROM calc ORDER BY warstwa, ogc_fid;
