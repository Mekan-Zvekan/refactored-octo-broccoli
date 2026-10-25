from pathlib import Path

from mapa import stations
from mapa.config import MapSettings
from mapa.geometry import relation_polygon
from mapa.render import map_extent, render, serbian_date
from mapa.translit import canonical_municipality, to_latin


def _ring(lon0, lat0, lon1, lat1):
    return [{"lon": lon0, "lat": lat0}, {"lon": lon1, "lat": lat0},
            {"lon": lon1, "lat": lat1}, {"lon": lon0, "lat": lat1}, {"lon": lon0, "lat": lat0}]


def _square_relation(name, lon0, lat0, lon1, lat1, inner=None):
    ring = _ring(lon0, lat0, lon1, lat1)
    # Spoljni prsten podeljen na dva člana, kao što često biva u OSM-u.
    members = [{"type": "way", "role": "outer", "geometry": ring[:3]},
               {"type": "way", "role": "outer", "geometry": ring[2:]}]
    if inner:
        members.append({"type": "way", "role": "inner", "geometry": _ring(*inner)})
    return {"type": "relation", "tags": {"name": name}, "members": members}


def test_transliteration_and_municipality_names():
    assert to_latin("Чукарица") == "Čukarica"
    assert to_latin("Љиљана Њего") == "Ljiljana Njego"
    known = ["Savski venac", "Čukarica", "Novi Beograd"]
    assert canonical_municipality("Градска општина Савски венац", known) == "Savski venac"
    assert canonical_municipality("cukarica", known) == "Čukarica"
    assert canonical_municipality("Surčin", known) is None


def test_relation_with_split_outer_and_hole():
    rel = _square_relation("x", 0, 0, 2, 2, inner=(0.5, 0.5, 1.5, 1.5))
    shape = relation_polygon(rel)
    assert abs(shape.area - 3.0) < 1e-9


def test_csv_and_assignment(tmp_path):
    csv_path = tmp_path / "spisak.csv"
    csv_path.write_text(
        "opstina;broj;naziv;adresa;lat;lon\n"
        "Врачар;1;OŠ Test;Testna 1;44.798;20.478\n"
        ";2;Bez opštine;Testna 2;44.80;20.40\n"
        "Vračar;3;Bez koordinata;Testna 3;;\n",
        encoding="utf-8",
    )
    points = stations.from_csv(csv_path, geocoder=None)
    assert len(points) == 2
    assert points[0].municipality == "Vračar"
    shapes = stations.municipality_shapes({"elements": [
        _square_relation("Нови Београд", 20.35, 44.78, 20.43, 44.83)]})
    stations.assign_municipalities(points, shapes)
    assert points[1].municipality == "Novi Beograd"

    osm = [stations.Station(lon=20.47801, lat=44.79801), stations.Station(lon=20.50, lat=44.81)]
    assert len(stations.merge(points, osm)) == 3


def test_serbian_date():
    import datetime as dt
    assert serbian_date(dt.date(2026, 10, 21)) == "21. OKTOBAR 2026."


def test_render_smoke(tmp_path: Path):
    settings = MapSettings(date="1. JANUAR 2026.")
    _, (south, west, north, east) = map_extent(settings)
    assert south < 44.8 < north and west < 20.455 < east
    layers = {
        "green": {"elements": [_square_relation("park", 20.44, 44.82, 20.46, 44.83)]},
        "water": {"elements": [_square_relation("reka", 20.40, 44.82, 20.55, 44.84)]},
        "roads": {"elements": [
            {"type": "way", "tags": {"highway": "primary"},
             "geometry": [{"lon": 20.40, "lat": 44.79}, {"lon": 20.50, "lat": 44.80}]},
            {"type": "way", "tags": {"highway": "residential"},
             "geometry": [{"lon": 20.45, "lat": 44.76}, {"lon": 20.46, "lat": 44.81}]},
        ]},
    }
    shapes = stations.municipality_shapes({"elements": [
        _square_relation("Врачар", 20.46, 44.79, 20.49, 44.81)]})
    points = [stations.Station(lon=20.478, lat=44.798), stations.Station(lon=20.30, lat=44.60)]
    stations.assign_municipalities(points, shapes)
    out = tmp_path / "mapa.png"
    count = render(layers, points, shapes, settings, [out], dpi=40)
    assert count == 1
    assert out.stat().st_size > 0
