"""Preuzimanje OpenStreetMap podataka preko Overpass API-ja, sa keširanjem na disk."""

import hashlib
import json
import time
from pathlib import Path

import requests

OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]
USER_AGENT = "biracka-mesta-beograd/1.0 (+https://github.com/mekan-zvekan/refactored-octo-broccoli)"

ROAD_CLASSES = (
    "motorway|trunk|primary|secondary|tertiary|unclassified|residential|"
    "living_street|pedestrian"
)

QUERIES = {
    "roads": """
        [out:json][timeout:300];
        way["highway"~"^({roads})(_link)?$"]({bbox});
        out geom qt;
    """,
    "water": """
        [out:json][timeout:300];
        (
          way["natural"="water"]({bbox});
          rel["natural"="water"]({bbox});
          way["waterway"="riverbank"]({bbox});
          rel["waterway"="riverbank"]({bbox});
          way["waterway"~"^(river|canal)$"]({bbox});
        );
        out geom qt;
    """,
    "green": """
        [out:json][timeout:300];
        (
          way["leisure"~"^(park|garden|golf_course|nature_reserve)$"]({bbox});
          rel["leisure"~"^(park|garden|golf_course|nature_reserve)$"]({bbox});
          way["landuse"~"^(forest|grass|meadow|recreation_ground|cemetery|allotments|village_green|orchard)$"]({bbox});
          rel["landuse"~"^(forest|grass|meadow|recreation_ground|cemetery|allotments|village_green|orchard)$"]({bbox});
          way["natural"~"^(wood|scrub|grassland|heath|wetland)$"]({bbox});
          rel["natural"~"^(wood|scrub|grassland|heath|wetland)$"]({bbox});
        );
        out geom qt;
    """,
    "municipalities": """
        [out:json][timeout:300];
        rel["boundary"="administrative"]["admin_level"~"^(7|8|9)$"]({bbox});
        out geom qt;
    """,
    "polling_stations": """
        [out:json][timeout:120];
        (
          nwr["amenity"="polling_station"]({bbox});
          nwr["polling_station"]["polling_station"!="no"]({bbox});
        );
        out center tags qt;
    """,
}


def bbox_string(south: float, west: float, north: float, east: float) -> str:
    return f"{south:.5f},{west:.5f},{north:.5f},{east:.5f}"


def run_query(ql: str, retries: int = 4) -> dict:
    last_error = None
    for attempt in range(retries):
        url = OVERPASS_URLS[attempt % len(OVERPASS_URLS)]
        try:
            response = requests.post(
                url, data={"data": ql}, headers={"User-Agent": USER_AGENT}, timeout=360
            )
            if response.status_code == 200:
                return response.json()
            last_error = f"{url}: HTTP {response.status_code}"
        except requests.RequestException as exc:
            last_error = f"{url}: {exc}"
        time.sleep(2 ** (attempt + 1))
    raise RuntimeError(f"Overpass upit nije uspeo: {last_error}")


def fetch_layer(name: str, bbox: str, cache_dir: Path, refresh: bool = False) -> dict:
    """Vraća Overpass odgovor za sloj `name`; čita iz keša ako postoji."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha1(bbox.encode()).hexdigest()[:8]
    path = cache_dir / f"{name}_{digest}.json"
    if path.exists() and not refresh:
        return json.loads(path.read_text(encoding="utf-8"))
    ql = QUERIES[name].format(bbox=bbox, roads=ROAD_CLASSES)
    print(f"  preuzimam sloj '{name}' …", flush=True)
    data = run_query(ql)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return data
