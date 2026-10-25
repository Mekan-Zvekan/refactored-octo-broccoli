# Biračka mesta u Beogradu

Poster-mapa biračkih mesta u Beogradu, u stilu mape „Ambasade u Beogradu“:
krem podloga, zelene površine, plave reke, bele ulice, veliki naslov,
broj tačaka na mapi, razmernik, strelica severa i izvori u podnožju.
Biračka mesta su obojena po gradskim opštinama, a legenda prikazuje broj po opštini.

## Instalacija

```bash
pip install -r requirements.txt
```

## Pokretanje

Samo sa podacima iz OpenStreetMap-a (`amenity=polling_station`):

```bash
python -m mapa
```

Sa zvaničnim spiskom biračkih mesta (preporučeno — OSM ih u Beogradu ima malo):

```bash
python -m mapa --csv data/biracka_mesta.csv --izvor oba
```

Rezultat: `output/biracka_mesta_beograd.png` i `.pdf`.

Korisne opcije:

| Opcija | Značenje |
| --- | --- |
| `--centar LAT LON` | centar mape (podrazumevano `44.800 20.455`) |
| `--sirina-km N` | širina prikaza u km (podrazumevano 24) |
| `--izvor auto/osm/csv/oba` | odakle se uzimaju biračka mesta |
| `--datum "21. OKTOBAR 2026."` | datum u podnožju (podrazumevano današnji) |
| `--osvezi` | ponovo preuzmi podatke umesto keša iz `data/cache/` |
| `--bez-geokodiranja` | preskoči adrese bez koordinata umesto geokodiranja |

## Zvanični spisak (CSV)

Republička izborna komisija za svake izbore objavljuje rešenja o određivanju
biračkih mesta po opštinama (naziv i adresa, bez koordinata). Prepišite ih u CSV
po šablonu `data/biracka_mesta.primer.csv` (separator `;` ili `,`, UTF-8):

```
opstina;broj;naziv;adresa;lat;lon
Vračar;1;<naziv objekta>;<ulica i broj>;;
```

Kolone `lat`/`lon` su opcione — adrese bez koordinata se geokodiraju preko
Nominatima (1 zahtev u sekundi, rezultati se keširaju u `data/cache/geocode.json`).
Naziv opštine može biti ćirilicom ili latinicom. Ako opština nije navedena,
određuje se iz OSM granica opština.

## Potreban pristup mreži

Skripta preuzima podatke sa:

- `overpass-api.de` (ili `overpass.kumi.systems`, `overpass.private.coffee`) — podloga i OSM biračka mesta
- `nominatim.openstreetmap.org` — samo za geokodiranje CSV adresa

## Testovi

```bash
python -m pytest
```

Podaci mape © OpenStreetMap saradnici, licenca ODbL.
