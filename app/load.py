import argparse
import os
import subprocess
from pathlib import Path

from osgeo import ogr

ogr.UseExceptions()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", required=True, type=int)
    args = parser.parse_args()

    host = os.environ.get("PGHOST", "host.docker.internal")
    user = os.environ.get("PGUSER", "psip")
    database = os.environ.get("PGDATABASE", "psip")

    if not os.environ.get("PGPASSWORD"):
        raise RuntimeError("Nie ustawiono PGPASSWORD")

    connection = (
        f"PG:host={host} port={args.port} "
        f"dbname={database} user={user}"
    )

    sources = [
        (Path("/data/powiat.shp"), "public.powiat"),
        (Path("/output/h3_r6.geojson"), "grid.h3_r6"),
        (Path("/output/h3_r7.geojson"), "grid.h3_r7"),
        (Path("/output/h3_r8.geojson"), "grid.h3_r8"),
    ]

    for source, _ in sources:
        if not source.exists():
            raise FileNotFoundError(f"Brak pliku: {source}")

    db = ogr.Open(connection, 1)
    if db is None:
        raise RuntimeError("Nie można połączyć się z bazą")

    db.ExecuteSQL("CREATE SCHEMA IF NOT EXISTS grid")
    db = None

    for source, table in sources:
        subprocess.run(
            [
                "ogr2ogr",
                "-f", "PostgreSQL",
                connection,
                str(source),
                "-nln", table,
                "-t_srs", "EPSG:2180",
                "-nlt", "PROMOTE_TO_MULTI",
                "-lco", "GEOMETRY_NAME=geom",
                "-lco", "SPATIAL_INDEX=GIST",
                "-overwrite",
            ],
            check=True,
        )
        print(f"Zaladowano {source.name} -> {table}")

    print(f"Import zakonczony: {database}, port {args.port}")


if __name__ == "__main__":
    main()