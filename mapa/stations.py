"""Biračka mesta: iz OpenStreetMap-a i/ili iz zvaničnog spiska (CSV) uz geokodiranje."""

import csv
import json
import math
import time
from dataclasses import dataclass
from pathlib import Path

import requests
from shapely.geometry import Point
from shapely.strtree import STRtree

from .config import MUNICIPALITY_COLORS
from .geometry import element_geometry, element_point, polygons_of
from .overpass import USER_AGENT
from .translit import canonical_municipality, to_latin

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
KNOWN_MUNICIPALITIES = list(MUNICIPALITY_COLORS) + [
    "Barajevo", "Lazarevac", "Mladenovac", "Obrenovac", "Sopot",
]


@dataclass
class Station:
    lon: float
    lat: float
    name: str = ""
    address: str = ""
    number: str = ""
    municipality: str | None = None
    source: str = "osm"


def from_osm(data: dict) -> list[Station]:
    stations = []
    for element in data.get("elements", []):
        point = element_point(element)
        if point is None:
            continue
        tags = element.get("tags", {})
        street = " ".join(filter(None, [tags.get("addr:street"), tags.get("addr:housenumber")]))
        stations.append(Station(
            lon=point[0],
            lat=point[1],
            name=to_latin(tags.get("name:sr-Latn") or tags.get("name") or ""),
            address=to_latin(street),
            number=tags.get("ref", ""),
            source="osm",
        ))
    return stations


def read_csv(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8-sig")
    dialect = csv.Sniffer().sniff(text.splitlines()[0], delimiters=",;\t")
    rows = csv.DictReader(text.splitlines(), dialect=dialect)
    return [{(k or "").strip().lower(): (v or "").strip() for k, v in row.items()} for row in rows]


def _parse_float(value: str) -> float | None:
    try:
        return float(value.replace(",", "."))
    except (AttributeError, ValueError):
        return None


class Geocoder:
    """Nominatim geokoder sa keširanjem (poštuje limit od 1 zahteva u sekundi)."""

    def __init__(self, cache_path: Path, viewbox: tuple[float, float, float, float]):
        self.cache_path = cache_path
        self.viewbox = viewbox  # west, south, east, north
        self.cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}
        self._last = 0.0

    def save(self) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_path.write_text(json.dumps(self.cache, ensure_ascii=False, indent=1), encoding="utf-8")

    def lookup(self, query: str) -> tuple[float, float] | None:
        if query in self.cache:
            hit = self.cache[query]
            return tuple(hit) if hit else None
        wait = 1.1 - (time.monotonic() - self._last)
        if wait > 0:
            time.sleep(wait)
        west, south, east, north = self.viewbox
        params = {
            "q": query, "format": "jsonv2", "limit": 1, "countrycodes": "rs",
            "viewbox": f"{west},{north},{east},{south}", "bounded": 1,
        }
        try:
            response = requests.get(NOMINATIM_URL, params=params,
                                    headers={"User-Agent": USER_AGENT}, timeout=30)
            response.raise_for_status()
            results = response.json()
        except requests.RequestException as exc:
            print(f"  geokodiranje nije uspelo za '{query}': {exc}")
            return None
        finally:
            self._last = time.monotonic()
        hit = (float(results[0]["lon"]), float(results[0]["lat"])) if results else None
        self.cache[query] = hit
        return hit


def from_csv(path: Path, geocoder: Geocoder | None) -> list[Station]:
    """Čita spisak biračkih mesta. Kolone: opstina, broj, naziv, adresa, [lat, lon]."""
    stations, missing = [], 0
    for row in read_csv(path):
        municipality = row.get("opstina") or row.get("opština") or ""
        address = row.get("adresa", "")
        lat, lon = _parse_float(row.get("lat", "")), _parse_float(row.get("lon", ""))
        if (lat is None or lon is None) and geocoder and address:
            hit = geocoder.lookup(f"{address}, {municipality}, Beograd, Srbija") \
                or geocoder.lookup(f"{address}, Beograd, Srbija")
            if hit:
                lon, lat = hit
        if lat is None or lon is None:
            missing += 1
            continue
        stations.append(Station(
            lon=lon, lat=lat,
            name=row.get("naziv", ""), address=address, number=row.get("broj", ""),
            municipality=canonical_municipality(municipality, KNOWN_MUNICIPALITIES) or municipality or None,
            source="csv",
        ))
    if geocoder:
        geocoder.save()
    if missing:
        print(f"  upozorenje: {missing} biračkih mesta iz CSV-a nema koordinate (preskočeno)")
    return stations


def municipality_shapes(data: dict) -> dict:
    """Naziv opštine -> poligon, za poznate beogradske opštine iz OSM granica."""
    shapes = {}
    for element in data.get("elements", []):
        tags = element.get("tags", {})
        name = canonical_municipality(tags.get("name:sr-Latn") or tags.get("name"), KNOWN_MUNICIPALITIES)
        if not name or name in shapes:
            continue
        geometry = element_geometry(element)
        if polygons_of(geometry):
            shapes[name] = geometry
    return shapes


def assign_municipalities(stations: list[Station], shapes: dict) -> None:
    if not shapes:
        return
    names = list(shapes)
    tree = STRtree([shapes[n] for n in names])
    for station in stations:
        if station.municipality:
            continue
        point = Point(station.lon, station.lat)
        for index in tree.query(point, predicate="within"):
            station.municipality = names[int(index)]
            break


def _distance_m(a: Station, b: Station) -> float:
    dy = (a.lat - b.lat) * 111_320
    dx = (a.lon - b.lon) * 111_320 * math.cos(math.radians(a.lat))
    return math.hypot(dx, dy)


def merge(primary: list[Station], extra: list[Station], radius_m: float = 30) -> list[Station]:
    """Dodaje stanice iz `extra` koje nisu na manje od `radius_m` od neke iz `primary`."""
    result = list(primary)
    for candidate in extra:
        if all(_distance_m(candidate, s) > radius_m for s in primary):
            result.append(candidate)
    return result
