-- Kontrola typu geometrii otrzymanej po przecieciu 8 linii z granica powiatu.
-- Nie zmienia danych, wykonuje tylko SELECT.
WITH p AS (
    SELECT ST_UnaryUnion(ST_Collect(ST_MakeValid(geom))) AS geom
    FROM public.powiat
),
b AS (
    SELECT 'ot_swrm_l'::text AS warstwa, ogc_fid, geom
    FROM bdot.ot_swrm_l WHERE ogc_fid IN (5043,3180,2512)
    UNION ALL
    SELECT 'ot_oipr_l', ogc_fid, geom
    FROM bdot.ot_oipr_l WHERE ogc_fid IN (2933,3826)
    UNION ALL
    SELECT 'ot_skrp_l', ogc_fid, geom
    FROM bdot.ot_skrp_l WHERE ogc_fid = 322
    UNION ALL
    SELECT 'ot_skjz_l', ogc_fid, geom
    FROM bdot.ot_skjz_l WHERE ogc_fid = 5374
    UNION ALL
    SELECT 'ot_skdr_l', ogc_fid, geom
    FROM bdot.ot_skdr_l WHERE ogc_fid = 485
)
SELECT b.warstwa, b.ogc_fid,
       round(ST_Length(b.geom)::numeric,3) AS dlugosc_oryg_m,
       ST_GeometryType(ST_Intersection(b.geom,p.geom)) AS typ_przeciecia,
       ST_Dimension(ST_Intersection(b.geom,p.geom)) AS wymiar,
       ST_IsEmpty(ST_Intersection(b.geom,p.geom)) AS puste_przeciecie,
       round(ST_Length(ST_Intersection(b.geom,p.geom))::numeric,3)
           AS dlugosc_bez_extract_m,
       round(ST_Length(ST_CollectionExtract(
            ST_Intersection(b.geom,p.geom),2))::numeric,3)
           AS dlugosc_po_extract_m,
       ST_Within(b.geom,p.geom) AS caly_w_powiecie,
       ST_Covers(p.geom,b.geom) AS caly_pokryty_powiatu,
       ST_GeometryType(p.geom) AS typ_powiatu
FROM b CROSS JOIN p
ORDER BY b.warstwa,b.ogc_fid;
