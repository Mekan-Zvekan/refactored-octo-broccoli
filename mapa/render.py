"""Crtanje postera "Biračka mesta u Beogradu" u stilu mape ambasada."""

import datetime as dt
from collections import Counter
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import shapely
from matplotlib import font_manager
from matplotlib.collections import LineCollection
from matplotlib.lines import Line2D
from matplotlib.patches import FancyArrow, PathPatch
from matplotlib.path import Path as MplPath
from pyproj import Transformer
from shapely.geometry import LineString, MultiLineString, Polygon, box
from shapely.geometry.polygon import orient
from shapely.ops import unary_union

from .config import (
    COLORS, DISTRICT_LABELS, MUNICIPALITY_COLORS, OTHER_COLOR, PROJECTED_CRS,
    RIVER_LABELS, MapSettings,
)
from .geometry import element_geometry, polygons_of

FIG_W, FIG_H = 20.0, 15.6
MAP_RECT = [0.0275, 0.067, 0.945, 0.719]  # levo, dole, širina, visina (udeo figure)

MONTHS = ["januar", "februar", "mart", "april", "maj", "jun", "jul", "avgust",
          "septembar", "oktobar", "novembar", "decembar"]

# Širina linije (pt) i redosled crtanja po klasi puta.
ROAD_STYLE = {
    "motorway": (2.4, 6), "trunk": (2.2, 6), "primary": (1.9, 5), "secondary": (1.5, 4),
    "tertiary": (1.1, 3), "link": (0.9, 2), "minor": (0.45, 1),
}

_TO_UTM = Transformer.from_crs("EPSG:4326", PROJECTED_CRS, always_xy=True)
_TO_WGS = Transformer.from_crs(PROJECTED_CRS, "EPSG:4326", always_xy=True)


def _font_family() -> str:
    available = {f.name for f in font_manager.fontManager.ttflist}
    for name in ("Segoe UI", "Inter", "Open Sans", "Source Sans 3", "Liberation Sans"):
        if name in available:
            return name
    return "DejaVu Sans"


def serbian_date(day: dt.date) -> str:
    return f"{day.day}. {MONTHS[day.month - 1]} {day.year}.".upper()


def project(geometry):
    return shapely.transform(
        geometry, lambda c: np.column_stack(_TO_UTM.transform(c[:, 0], c[:, 1]))
    )


def map_extent(settings: MapSettings):
    """Obuhvat u metrima (UTM) i u stepenima (s, w, n, e) za zadati centar i širinu."""
    cx, cy = _TO_UTM.transform(settings.center_lon, settings.center_lat)
    aspect = (MAP_RECT[2] * FIG_W) / (MAP_RECT[3] * FIG_H)
    half_w = settings.width_km * 500
    half_h = half_w / aspect
    xmin, ymin, xmax, ymax = cx - half_w, cy - half_h, cx + half_w, cy + half_h
    lons, lats = _TO_WGS.transform([xmin, xmin, xmax, xmax], [ymin, ymax, ymin, ymax])
    lonlat = (min(lats), min(lons), max(lats), max(lons))
    return (xmin, ymin, xmax, ymax), lonlat


def _road_class(tags: dict) -> str:
    kind = tags.get("highway", "")
    if kind.endswith("_link"):
        return "link"
    return kind if kind in ROAD_STYLE else "minor"


def _lines(geometry) -> list[np.ndarray]:
    if isinstance(geometry, LineString):
        return [np.asarray(geometry.coords)] if not geometry.is_empty else []
    if isinstance(geometry, MultiLineString):
        return [np.asarray(g.coords) for g in geometry.geoms]
    return [np.asarray(g.coords) for g in getattr(geometry, "geoms", [])
            if isinstance(g, LineString)]


def _area_layer(data: dict, frame: Polygon) -> list[Polygon]:
    parts = []
    for element in data.get("elements", []):
        for polygon in polygons_of(element_geometry(element, area=True)):
            projected = project(polygon)
            if projected.intersects(frame):
                parts.append(projected.intersection(frame))
    return polygons_of(unary_union(parts)) if parts else []


def _polygon_patch(polygons: list[Polygon], **style) -> PathPatch | None:
    vertices, codes = [], []
    for polygon in polygons:
        polygon = orient(polygon, 1.0)
        for ring in (polygon.exterior, *polygon.interiors):
            coords = np.asarray(ring.coords)
            if len(coords) < 4:
                continue
            vertices.append(coords)
            codes.append([MplPath.MOVETO] + [MplPath.LINETO] * (len(coords) - 2) + [MplPath.CLOSEPOLY])
    if not vertices:
        return None
    return PathPatch(MplPath(np.concatenate(vertices), np.concatenate(codes)), **style)


def _draw_roads(ax, data: dict, frame: Polygon) -> None:
    groups: dict[str, list] = {key: [] for key in ROAD_STYLE}
    for element in data.get("elements", []):
        geometry = element_geometry(element, area=False)
        if geometry is None:
            continue
        projected = project(geometry)
        if projected.intersects(frame):
            groups[_road_class(element.get("tags", {}))].extend(_lines(projected.intersection(frame)))
    for key, (width, order) in sorted(ROAD_STYLE.items(), key=lambda kv: kv[1][1]):
        if groups[key]:
            ax.add_collection(LineCollection(
                groups[key], colors=COLORS["road"], linewidths=width,
                capstyle="round", joinstyle="round", zorder=3 + order * 0.01,
            ))


def _draw_waterways(ax, data: dict, frame: Polygon) -> None:
    lines = []
    for element in data.get("elements", []):
        if element.get("type") != "way" or "waterway" not in element.get("tags", {}):
            continue
        geometry = element_geometry(element, area=False)
        if geometry is not None:
            projected = project(geometry)
            if projected.intersects(frame):
                lines.extend(_lines(projected.intersection(frame)))
    if lines:
        ax.add_collection(LineCollection(lines, colors=COLORS["water"], linewidths=1.2, zorder=2.5))


def _draw_boundaries(ax, shapes: dict, frame: Polygon) -> None:
    lines = []
    for geometry in shapes.values():
        for polygon in polygons_of(project(geometry)):
            lines.extend(_lines(polygon.exterior.intersection(frame)))
    if lines:
        ax.add_collection(LineCollection(
            lines, colors=COLORS["boundary"], linewidths=0.8, linestyles=(0, (4, 3)),
            alpha=0.6, zorder=4,
        ))


def _in_frame(x: float, y: float, extent) -> bool:
    xmin, ymin, xmax, ymax = extent
    return xmin < x < xmax and ymin < y < ymax


def _draw_labels(ax, extent, family: str) -> None:
    for lat, lon, text in DISTRICT_LABELS:
        x, y = _TO_UTM.transform(lon, lat)
        if _in_frame(x, y, extent):
            ax.text(x, y, text, fontsize=12, color=COLORS["label"], family=family,
                    ha="center", va="center", zorder=6)
    for lat, lon, text, angle in RIVER_LABELS:
        x, y = _TO_UTM.transform(lon, lat)
        if _in_frame(x, y, extent):
            ax.text(x, y, " ".join(text), fontsize=12, color=COLORS["river_label"],
                    family=family, rotation=angle, ha="center", va="center", zorder=6)


def _draw_scale_bar(ax, extent, family: str) -> None:
    xmin, ymin, xmax, ymax = extent
    x0 = xmin + (xmax - xmin) * 0.027
    y0 = ymin + (ymax - ymin) * 0.05
    length_km = 2 if (xmax - xmin) < 30_000 else 5
    tick = (ymax - ymin) * 0.008
    ax.plot([x0, x0 + length_km * 1000], [y0, y0], color=COLORS["ink"], lw=1.4,
            solid_capstyle="butt", zorder=8)
    for km in range(length_km + 1):
        x = x0 + km * 1000
        ax.plot([x, x], [y0 - tick, y0 + tick], color=COLORS["ink"], lw=1.4, zorder=8)
        label = f"{km} km" if km == length_km else str(km)
        ax.text(x, y0 - tick * 3, label, fontsize=11, color=COLORS["ink"], family=family,
                ha="left" if km == length_km else "center", va="top", zorder=8)


def _draw_north_arrow(ax, extent, family: str) -> None:
    xmin, ymin, xmax, ymax = extent
    x = xmin + (xmax - xmin) * 0.982
    y_base = ymin + (ymax - ymin) * 0.86
    height = (ymax - ymin) * 0.07
    ax.add_patch(FancyArrow(x, y_base, 0, height, width=0, head_width=(xmax - xmin) * 0.006,
                            head_length=height * 0.25, length_includes_head=True,
                            color=COLORS["ink"], lw=1.2, zorder=8))
    ax.text(x, y_base + height * 1.25, "S", fontsize=12, color=COLORS["ink"], family=family,
            ha="center", va="bottom", zorder=8)


def _draw_stations(ax, stations, extent, family: str) -> tuple[int, int]:
    xs, ys, colors, counts = [], [], [], Counter()
    for station in stations:
        x, y = _TO_UTM.transform(station.lon, station.lat)
        if not _in_frame(x, y, extent):
            continue
        name = station.municipality if station.municipality in MUNICIPALITY_COLORS else "Ostalo"
        xs.append(x)
        ys.append(y)
        colors.append(MUNICIPALITY_COLORS.get(name, OTHER_COLOR))
        counts[name] += 1
    if xs:
        ax.scatter(xs, ys, s=26, c=colors, edgecolors=COLORS["paper"], linewidths=0.6, zorder=9)

    handles = []
    for name in list(MUNICIPALITY_COLORS) + ["Ostalo"]:
        if counts[name]:
            handles.append(Line2D([], [], marker="o", linestyle="", markersize=8,
                                  markerfacecolor=MUNICIPALITY_COLORS.get(name, OTHER_COLOR),
                                  markeredgecolor=COLORS["paper"], label=f"{name}  ·  {counts[name]}"))
    if handles:
        legend = ax.legend(handles=handles, loc="lower right", frameon=True, fancybox=False,
                           title="GRADSKE OPŠTINE", borderpad=1.0, labelspacing=0.6,
                           prop={"family": family, "size": 11},
                           title_fontproperties={"family": family, "size": 11})
        legend.get_frame().set_facecolor(COLORS["paper"])
        legend.get_frame().set_edgecolor("none")
        legend.get_frame().set_alpha(0.92)
        legend.set_zorder(10)
        legend.get_title().set_color(COLORS["muted"])
        for text in legend.get_texts():
            text.set_color(COLORS["ink"])
    locations = len({(round(x), round(y)) for x, y in zip(xs, ys)})
    return len(xs), locations


def render(layers: dict, stations: list, municipality_shapes: dict, settings: MapSettings,
           out_paths: list[Path], dpi: int = 200) -> int:
    family = _font_family()
    extent, _ = map_extent(settings)
    xmin, ymin, xmax, ymax = extent
    frame = box(xmin - 500, ymin - 500, xmax + 500, ymax + 500)

    fig = plt.figure(figsize=(FIG_W, FIG_H), facecolor=COLORS["paper"])
    ax = fig.add_axes(MAP_RECT)
    ax.set_facecolor(COLORS["land"])
    ax.set_xlim(xmin, xmax)
    ax.set_ylim(ymin, ymax)
    ax.set_aspect("equal", adjustable="box")
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)

    green = _polygon_patch(_area_layer(layers.get("green", {}), frame),
                           facecolor=COLORS["green"], edgecolor="none", zorder=1)
    if green:
        ax.add_patch(green)
    water = _polygon_patch(_area_layer(layers.get("water", {}), frame),
                           facecolor=COLORS["water"], edgecolor="none", zorder=2)
    if water:
        ax.add_patch(water)
    _draw_waterways(ax, layers.get("water", {}), frame)
    _draw_roads(ax, layers.get("roads", {}), frame)
    _draw_boundaries(ax, municipality_shapes, frame)
    _draw_labels(ax, extent, family)
    _draw_scale_bar(ax, extent, family)
    _draw_north_arrow(ax, extent, family)
    count, locations = _draw_stations(ax, stations, extent, family)

    ink, muted = COLORS["ink"], COLORS["muted"]
    fig.text(0.5, 0.963, settings.title_top, ha="center", va="center", fontsize=15,
             color=ink, family=family)
    fig.text(0.5, 0.916, settings.title, ha="center", va="center_baseline", fontsize=92,
             fontweight="light", color=ink, family=family)
    fig.text(0.5, 0.848, settings.subtitle, ha="center", va="center", fontsize=36,
             fontweight="light", color=ink, family=family)
    count_text = f"{settings.count_label}: {count}"
    if locations and locations != count:
        count_text += f"  ·  LOKACIJA: {locations}"
    fig.text(0.5, 0.81, count_text, ha="center", va="center", fontsize=12, color=muted, family=family)

    sources = settings.sources or ["OpenStreetMap (amenity=polling_station)"]
    fig.text(0.034, 0.046, "Izvori: " + " · ".join(sources), ha="left", va="center",
             fontsize=11, color=muted, family=family)
    fig.text(0.034, 0.029, "Podaci mape © OpenStreetMap saradnici (ODbL) · Overpass API",
             ha="left", va="center", fontsize=9, color=muted, family=family)
    date = settings.date or serbian_date(dt.date.today())
    fig.text(0.966, 0.046, f"ISTRAŽIVANJE {date}", ha="right", va="center", fontsize=11,
             color=muted, family=family)
    fig.text(0.966, 0.029, "openstreetmap.org", ha="right", va="center", fontsize=9,
             color=muted, family=family)

    for path in out_paths:
        path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(path, dpi=dpi, facecolor=fig.get_facecolor())
        print(f"  sačuvano: {path}")
    plt.close(fig)
    return count
