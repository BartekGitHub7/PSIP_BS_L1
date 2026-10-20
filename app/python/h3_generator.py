import json
from pathlib import Path

import h3
from osgeo import ogr, osr

ogr.UseExceptions()

SOURCE = Path("/data/powiat.shp")
OUTPUT = Path("/output")
RESOLUTIONS = (6, 7, 8)


def read_shapes():
    if not SOURCE.exists():
        raise FileNotFoundError(f"Brak pliku: {SOURCE}")

    dataset = ogr.Open(str(SOURCE))
    if dataset is None:
        raise RuntimeError("Nie można otworzyć powiat.shp")

    layer = dataset.GetLayer()
    source_crs = layer.GetSpatialRef()

    if source_crs is None:
        raise RuntimeError("Brak układu współrzędnych. Sprawdź plik powiat.prj")

    source_crs = source_crs.Clone()
    source_crs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)

    target_crs = osr.SpatialReference()
    target_crs.ImportFromEPSG(4326)
    target_crs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)

    transform = osr.CoordinateTransformation(source_crs, target_crs)
    shapes = []

    for feature in layer:
        geometry = feature.GetGeometryRef()
        if geometry is None or geometry.IsEmpty():
            continue

        geometry = geometry.Clone()
        geometry.Transform(transform)
        geometry.FlattenTo2D()

        if not geometry.IsValid():
            raise RuntimeError("Niepoprawna geometria granicy powiatu")

        geojson = json.loads(geometry.ExportToJson())
        shapes.append(h3.geo_to_h3shape(geojson))

    if not shapes:
        raise RuntimeError("Plik powiat.shp nie zawiera geometrii")

    return shapes


def main():
    shapes = read_shapes()
    OUTPUT.mkdir(parents=True, exist_ok=True)

    for resolution in RESOLUTIONS:
        cells = set()

        for shape in shapes:
            cells.update(
                h3.h3shape_to_cells_experimental(
                    shape,
                    resolution,
                    contain="overlap",
                )
            )

        features = []

        for cell in sorted(cells):
            # H3 zwraca (latitude, longitude).
            # GeoJSON wymaga [longitude, latitude].
            ring = [
                [longitude, latitude]
                for latitude, longitude in h3.cell_to_boundary(cell)
            ]
            ring.append(ring[0])

            features.append({
                "type": "Feature",
                "properties": {
                    "h3_id": cell,
                    "resolution": resolution,
                },
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [ring],
                },
            })

        destination = OUTPUT / f"h3_r{resolution}.geojson"
        destination.write_text(
            json.dumps({
                "type": "FeatureCollection",
                "features": features,
            }),
            encoding="utf-8",
        )

        print(
            f"Rozdzielczosc {resolution}: "
            f"{len(features)} komorek -> {destination}"
        )


if __name__ == "__main__":
    main()