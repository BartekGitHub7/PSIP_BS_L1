import os
import re
import subprocess
from pathlib import Path

from osgeo import ogr

ogr.UseExceptions()

SOURCE = Path("/data/bdot")

# Import BDOT tylko do środowiska testowego.
CONNECTION = (
    "PG:host=host.docker.internal "
    "port=5444 dbname=psip user=psip"
)


def main():
    if not os.environ.get("PGPASSWORD"):
        raise RuntimeError("Brak hasla w PGPASSWORD")

    shapefiles = sorted(SOURCE.rglob("*.shp"))
    if not shapefiles:
        raise FileNotFoundError("Brak plikow SHP w /data/bdot")

    tables = set()
    sources = []

    for source in shapefiles:
        match = re.search(r"__(OT_[A-Z0-9]+_[ALP])$", source.stem)
        if not match:
            raise RuntimeError(f"Nieznana nazwa pliku: {source.name}")

        table = match.group(1).lower()

        if table in tables:
            raise RuntimeError(f"Powtorzona warstwa: {table}")

        tables.add(table)
        sources.append((source, table))

    db = ogr.Open(CONNECTION, 1)
    if db is None:
        raise RuntimeError("Nie mozna polaczyc sie z env-test")

    db.ExecuteSQL("CREATE SCHEMA IF NOT EXISTS bdot")
    db = None

    for index, (source, table) in enumerate(sources, start=1):
        print(
            f"[{index}/{len(sources)}] Import bdot.{table}",
            flush=True,
        )

        subprocess.run(
            [
                "ogr2ogr",
                "-f", "PostgreSQL",
                CONNECTION,
                str(source),
                "-nln", f"bdot.{table}",
                "-t_srs", "EPSG:2180",
                "-dim", "XY",
                "-nlt", "PROMOTE_TO_MULTI",
                "-makevalid",
                "-lco", "GEOMETRY_NAME=geom",
                "-lco", "SPATIAL_INDEX=GIST",
                "-overwrite",
            ],
            check=True,
        )

    print(f"Gotowe. Zaimportowano {len(sources)} warstw BDOT.")


if __name__ == "__main__":
    main()