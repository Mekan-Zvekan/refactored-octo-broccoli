"""Komandna linija: python -m mapa [opcije]

Preuzima OSM podlogu i biračka mesta, opciono geokodira zvanični spisak (CSV)
i crta poster "Biračka mesta u Beogradu".
"""

import argparse
import sys
from pathlib import Path

from . import overpass, stations
from .config import MapSettings
from .render import map_extent, render

ROOT = Path(__file__).resolve().parent.parent


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m mapa", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--csv", type=Path,
                        help="zvanični spisak biračkih mesta (kolone: opstina, broj, naziv, adresa, [lat, lon])")
    parser.add_argument("--izvor", choices=["auto", "osm", "csv", "oba"], default="auto",
                        help="odakle se uzimaju biračka mesta (auto = CSV ako je zadat, inače OSM)")
    parser.add_argument("--centar", type=float, nargs=2, metavar=("LAT", "LON"),
                        help="centar mape (podrazumevano 44.800 20.455)")
    parser.add_argument("--sirina-km", type=float, help="širina prikaza u km (podrazumevano 24)")
    parser.add_argument("--datum", help='tekst datuma u podnožju, npr. "21. OKTOBAR 2026."')
    parser.add_argument("--izlaz", type=Path, default=ROOT / "output" / "biracka_mesta_beograd",
                        help="putanja izlaza bez ekstenzije (pravi se .png i .pdf)")
    parser.add_argument("--dpi", type=int, default=200)
    parser.add_argument("--kes", type=Path, default=ROOT / "data" / "cache", help="direktorijum keša")
    parser.add_argument("--osvezi", action="store_true", help="ponovo preuzmi podatke (ignoriši keš)")
    parser.add_argument("--bez-geokodiranja", action="store_true",
                        help="ne geokodiraj adrese iz CSV-a kojima nedostaju koordinate")
    args = parser.parse_args(argv)

    settings = MapSettings(date=args.datum)
    if args.centar:
        settings.center_lat, settings.center_lon = args.centar
    if args.sirina_km:
        settings.width_km = args.sirina_km

    source = args.izvor
    if source == "auto":
        source = "csv" if args.csv else "osm"
    if source in ("csv", "oba") and not args.csv:
        parser.error("--izvor csv/oba zahteva --csv")

    _, (south, west, north, east) = map_extent(settings)
    bbox = overpass.bbox_string(south, west, north, east)
    print(f"Obuhvat mape (j, z, s, i): {bbox}")

    print("Preuzimanje podloge iz OpenStreetMap-a:")
    layers = {name: overpass.fetch_layer(name, bbox, args.kes, args.osvezi)
              for name in ("green", "water", "roads", "municipalities")}
    shapes = stations.municipality_shapes(layers["municipalities"])

    sources = []
    osm_points, csv_points = [], []
    if source in ("osm", "oba"):
        data = overpass.fetch_layer("polling_stations", bbox, args.kes, args.osvezi)
        osm_points = stations.from_osm(data)
        sources.append("OpenStreetMap (amenity=polling_station)")
        print(f"  OSM: {len(osm_points)} biračkih mesta")
    if source in ("csv", "oba"):
        geocoder = None
        if not args.bez_geokodiranja:
            geocoder = stations.Geocoder(args.kes / "geocode.json", (west, south, east, north))
        csv_points = stations.from_csv(args.csv, geocoder)
        sources.insert(0, "RIK — rešenja o određivanju biračkih mesta")
        if geocoder:
            sources.append("geokodiranje: Nominatim")
        print(f"  CSV: {len(csv_points)} biračkih mesta sa koordinatama")

    points = stations.merge(csv_points, osm_points) if csv_points else osm_points
    stations.assign_municipalities(points, shapes)
    if not points:
        print("Upozorenje: nema nijednog biračkog mesta za prikaz.", file=sys.stderr)

    settings.sources = sources
    outputs = [args.izlaz.with_suffix(".png"), args.izlaz.with_suffix(".pdf")]
    count = render(layers, points, shapes, settings, outputs, dpi=args.dpi)
    print(f"Gotovo: {count} biračkih mesta na mapi.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
