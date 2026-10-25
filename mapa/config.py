"""Podrazumevana podešavanja mape: obuhvat, boje, natpisi."""

from dataclasses import dataclass, field

# Centar mape i širina prikaza (u km). Visina se računa iz odnosa stranica okvira.
CENTER_LAT = 44.800
CENTER_LON = 20.455
WIDTH_KM = 24.0

# UTM zona 34N — metrički koordinatni sistem za Beograd (razmernik u km je tačan).
PROJECTED_CRS = "EPSG:32634"

# Boje u stilu postera "Ambasade u Beogradu".
COLORS = {
    "paper": "#f3efe7",
    "land": "#ebe5d6",
    "green": "#c6d1b2",
    "water": "#5f8db4",
    "road": "#fbf8f1",
    "road_casing": "#e2dccb",
    "boundary": "#9c9682",
    "label": "#7c7a6e",
    "river_label": "#eef3f8",
    "ink": "#1f2a26",
    "muted": "#4a4f4b",
}

# Boje markera po gradskim opštinama.
MUNICIPALITY_COLORS = {
    "Stari grad": "#c0392b",
    "Vračar": "#e67e22",
    "Savski venac": "#8e44ad",
    "Novi Beograd": "#1f3a93",
    "Zemun": "#138d75",
    "Palilula": "#b7950b",
    "Zvezdara": "#c2185b",
    "Voždovac": "#6d4c41",
    "Čukarica": "#2e86c1",
    "Rakovica": "#5d6d7e",
    "Surčin": "#a04000",
    "Grocka": "#7d3c98",
}
OTHER_COLOR = "#333333"

# Natpisi kvartova (lat, lon, tekst) kao na uzoru.
DISTRICT_LABELS = [
    (44.8235, 20.4505, "KALEMEGDAN"),
    (44.8150, 20.4050, "NOVI BEOGRAD"),
    (44.8450, 20.4000, "ZEMUN"),
    (44.7980, 20.4800, "VRAČAR"),
    (44.7920, 20.5250, "ZVEZDARA"),
    (44.8180, 20.5020, "PALILULA"),
    (44.7700, 20.4950, "VOŽDOVAC"),
    (44.7820, 20.4050, "ADA CIGANLIJA"),
    (44.7720, 20.4500, "DEDINJE"),
    (44.7600, 20.4250, "KOŠUTNJAK"),
    (44.7700, 20.3800, "ČUKARICA"),
    (44.7450, 20.4500, "RAKOVICA"),
]

# Natpisi reka (lat, lon, tekst, ugao u stepenima).
RIVER_LABELS = [
    (44.8440, 20.5300, "DUNAV", 12),
    (44.7880, 20.3900, "SAVA", 35),
]


@dataclass
class MapSettings:
    center_lat: float = CENTER_LAT
    center_lon: float = CENTER_LON
    width_km: float = WIDTH_KM
    title_top: str = "BIRAČKA MESTA U"
    title: str = "BEOGRADU"
    subtitle: str = "SRBIJA"
    count_label: str = "BROJ BIRAČKIH MESTA NA MAPI"
    sources: list = field(default_factory=list)
    date: str | None = None
