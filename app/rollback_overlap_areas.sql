-- Opcjonalne odtworzenie dwoch kolumn z audytowego backupu.
-- Uruchamiaj wylacznie, jesli konieczne jest cofniecie naprawy.
BEGIN;

DO $$
DECLARE
    grid_name text;
    changed bigint;
BEGIN
    IF to_regclass('audit.bdot_overlap_area_backup') IS NULL THEN
        RAISE EXCEPTION 'Nie znaleziono tabeli audit.bdot_overlap_area_backup';
    END IF;

    FOREACH grid_name IN ARRAY ARRAY['h3_r6', 'h3_r7', 'h3_r8']
    LOOP
        EXECUTE format(
            'UPDATE grid.%I g
             SET ot_adja_a_area_m2 = b.ot_adja_a_area_m2,
                 ot_adms_a_area_m2 = b.ot_adms_a_area_m2
             FROM audit.bdot_overlap_area_backup b
             WHERE b.grid_name = %L
               AND g.h3_id::text = b.h3_id',
            grid_name, grid_name
        );
        GET DIAGNOSTICS changed = ROW_COUNT;
        RAISE NOTICE 'Przywrocono % wierszy w grid.%', changed, grid_name;
    END LOOP;
END
$$;

COMMIT;
