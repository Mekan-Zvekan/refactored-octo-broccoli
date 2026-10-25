"""Pretvaranje Overpass JSON elemenata u shapely geometrije."""

from shapely.geometry import LineString, MultiPolygon, Point, Polygon
from shapely.ops import linemerge, polygonize, unary_union


def _coords(geometry: list) -> list[tuple[float, float]]:
    return [(p["lon"], p["lat"]) for p in geometry if p]


def _rings(lines: list[LineString]):
    """Spaja delove prstenova (članove relacije) u poligone."""
    if not lines:
        return []
    merged = linemerge(lines)
    return [p for p in polygonize(merged) if p.is_valid and not p.is_empty]


def relation_polygon(element: dict):
    outers, inners = [], []
    for member in element.get("members", []):
        if member.get("type") != "way" or "geometry" not in member:
            continue
        coords = _coords(member["geometry"])
        if len(coords) < 2:
            continue
        line = LineString(coords)
        (inners if member.get("role") == "inner" else outers).append(line)
    outer = unary_union(_rings(outers))
    if outer.is_empty:
        return None
    inner = unary_union(_rings(inners))
    shape = outer.difference(inner) if not inner.is_empty else outer
    return shape if not shape.is_empty else None


def way_geometry(element: dict, area: bool):
    coords = _coords(element.get("geometry", []))
    if len(coords) < 2:
        return None
    closed = coords[0] == coords[-1] and len(coords) >= 4
    if area and closed:
        polygon = Polygon(coords)
        if not polygon.is_valid:
            polygon = polygon.buffer(0)
        return polygon if not polygon.is_empty else None
    return LineString(coords)


def element_geometry(element: dict, area: bool = True):
    kind = element.get("type")
    if kind == "way":
        return way_geometry(element, area)
    if kind == "relation":
        return relation_polygon(element) if area else None
    if kind == "node" and "lat" in element:
        return Point(element["lon"], element["lat"])
    return None


def element_point(element: dict):
    """Tačka elementa: čvor ili `center` iz `out center`."""
    if "lat" in element and "lon" in element:
        return element["lon"], element["lat"]
    center = element.get("center")
    if center:
        return center["lon"], center["lat"]
    return None


def polygons_of(geometry) -> list[Polygon]:
    if geometry is None or geometry.is_empty:
        return []
    if isinstance(geometry, Polygon):
        return [geometry]
    if isinstance(geometry, MultiPolygon):
        return list(geometry.geoms)
    return [g for g in getattr(geometry, "geoms", []) if isinstance(g, Polygon)]
