"""
weather_service.py
===================
Servizio meteo storico basato su Open-Meteo (gratuito, nessuna API key).

API utilizzate:
  - Geocoding: https://geocoding-api.open-meteo.com/v1/search
  - Archivio:  https://archive-api.open-meteo.com/v1/archive

Fornisce:
  - geocode_city(city_name)        → (lat, lon, display_name)
  - fetch_weather(lat, lon, start, end) → dict con dati orari
  - correlate_weather_with_rsl(...)     → analisi correlazione
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

import requests

logger = logging.getLogger(__name__)

# ── WMO Weather Code → descrizione italiana ───────────────────────────────────
WMO_DESCRIPTIONS = {
    0:  "Sereno",
    1:  "Prevalentemente sereno",
    2:  "Parzialmente nuvoloso",
    3:  "Coperto",
    45: "Nebbia",
    48: "Nebbia con brina",
    51: "Pioggia leggera",
    53: "Pioggia moderata",
    55: "Pioggia intensa",
    61: "Pioggia leggera",
    63: "Pioggia moderata",
    65: "Pioggia intensa",
    71: "Neve leggera",
    73: "Neve moderata",
    75: "Neve intensa",
    80: "Rovesci leggeri",
    81: "Rovesci moderati",
    82: "Rovesci violenti",
    85: "Nevicate leggere",
    86: "Nevicate intense",
    95: "Temporale",
    96: "Temporale con grandine",
    99: "Temporale violento con grandine",
}

WMO_SEVERITY = {
    # 0-2: ok, 3: leggero, 4: moderato, 5: severo
    0: 0, 1: 0, 2: 1, 3: 2,
    45: 3, 48: 3,
    51: 2, 53: 3, 55: 4,
    61: 2, 63: 3, 65: 4,
    71: 3, 73: 4, 75: 5,
    80: 3, 81: 4, 82: 5,
    85: 3, 86: 5,
    95: 5, 96: 5, 99: 5,
}


# ─────────────────────────────────────────────────────────────────────────────
#  Geocoding
# ─────────────────────────────────────────────────────────────────────────────

def geocode_city(city_name: str) -> Optional[dict]:
    """
    Converte un nome città in coordinate lat/lon usando Open-Meteo Geocoding.
    Restituisce None se la città non viene trovata.

    Returns:
        {"lat": float, "lon": float, "name": str, "country": str}
    """
    url = "https://geocoding-api.open-meteo.com/v1/search"
    params = {
        "name":     city_name,
        "count":    1,
        "language": "it",
        "format":   "json",
    }
    try:
        r = requests.get(url, params=params, timeout=8)
        r.raise_for_status()
        data = r.json()
        results = data.get("results", [])
        if not results:
            return None
        hit = results[0]
        return {
            "lat":     hit["latitude"],
            "lon":     hit["longitude"],
            "name":    hit["name"],
            "country": hit.get("country", ""),
            "region":  hit.get("admin1", ""),
        }
    except Exception as e:
        logger.error("Geocoding fallito per '%s': %s", city_name, e)
        return None


# ─────────────────────────────────────────────────────────────────────────────
#  Fetch dati meteo storici
# ─────────────────────────────────────────────────────────────────────────────

def fetch_weather(lat: float, lon: float, start_date: str, end_date: str) -> Optional[dict]:
    """
    Scarica dati meteo orari per un range di date da Open-Meteo Archive.

    Args:
        lat, lon:    coordinate geografiche
        start_date:  "YYYY-MM-DD"
        end_date:    "YYYY-MM-DD"

    Returns:
        {
          "times":         [str, ...],          # ISO8601 orario
          "precipitation": [float, ...],        # mm
          "windspeed":     [float, ...],         # km/h
          "cloudcover":    [float, ...],         # %
          "weathercode":   [int, ...],
          "wmo_labels":    [str, ...],           # descrizione italiana
          "units":         {"precipitation": "mm", ...}
        }
    """
    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude":   lat,
        "longitude":  lon,
        "start_date": start_date,
        "end_date":   end_date,
        "hourly":     "precipitation,windspeed_10m,cloudcover,weathercode",
        "timezone":   "Europe/Rome",
        "timeformat": "iso8601",
    }
    try:
        r = requests.get(url, params=params, timeout=15)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        logger.error("Fetch meteo fallito: %s", e)
        return None

    hourly = data.get("hourly", {})
    times  = hourly.get("time", [])
    precip = hourly.get("precipitation", [])
    wind   = hourly.get("windspeed_10m", [])
    cloud  = hourly.get("cloudcover", [])
    codes  = hourly.get("weathercode", [])

    wmo_labels = [WMO_DESCRIPTIONS.get(c, f"WMO {c}") for c in codes]

    return {
        "times":         times,
        "precipitation": precip,
        "windspeed":     wind,
        "cloudcover":    cloud,
        "weathercode":   codes,
        "wmo_labels":    wmo_labels,
        "units": {
            "precipitation": "mm",
            "windspeed":     "km/h",
            "cloudcover":    "%",
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
#  Correlazione meteo ↔ degrado RSL / ES
# ─────────────────────────────────────────────────────────────────────────────

def get_weather_impact_score(
    freq_ghz: float,
    worst_prec: float,
    worst_wind: float,
    severity: int
) -> float:
    """
    Ritorna uno score 0-100 di probabilità che il degrado sia causato dal meteo,
    calibrato in base alla frequenza operativa della tratta (fading da pioggia/vento).
    """
    if freq_ghz > 15.0:
        # Frequenze alte (es. 15-18+ GHz, mmWave): la pioggia è estremamente critica
        rainfall_impact = min(worst_prec / 2.0, 1.0) * 45.0  # max 45 punti
        wind_impact     = min(worst_wind / 50.0, 1.0) * 25.0  # max 25 punti (strutture sensibili al vento)
    elif freq_ghz > 8.0:
        # Frequenze medie (8-15 GHz): impatto moderato da pioggia, vento medio
        rainfall_impact = min(worst_prec / 5.0, 1.0) * 25.0  # max 25 punti
        wind_impact     = min(worst_wind / 80.0, 1.0) * 15.0  # max 15 punti
    else:
        # Frequenze basse (<8 GHz): pioggia trascurabile, vento quasi irrilevante
        rainfall_impact = min(worst_prec / 10.0, 1.0) * 10.0 # max 10 punti
        wind_impact     = 0.0

    severity_impact = min(severity, 5) * 10.0  # max 50 punti (basato su WMO Severity 0-5)
    return min(rainfall_impact + wind_impact + severity_impact, 100.0)


def correlate_weather_with_degradation(
    weather: dict,
    degradation_windows: list,   # lista di {"start": "YYYY-MM-DDTHH:MM", "end": ..., "min_rsl": float, "es": int}
    freq_ghz: float = 13.0,
) -> dict:
    """
    Confronta i dati meteo orari con le finestre temporali di degrado RSL/ES.
    Calcola uno score adattivo basato sulla frequenza operativa della tratta.

    Returns dict con:
      - correlation_score: 0-100 (quanto bene il meteo spiega il degrado)
      - events: lista di eventi meteo sovrapposti al degrado
      - summary_text: testo riassuntivo italiano
      - confirmed_environmental: bool
    """
    if not weather or not degradation_windows:
        return {
            "correlation_score": 0,
            "events": [],
            "summary_text": "Impossibile calcolare la correlazione (dati assenti).",
            "confirmed_environmental": False,
        }

    times  = weather["times"]
    precip = weather["precipitation"]
    wind   = weather["windspeed"]
    cloud  = weather["cloudcover"]
    codes  = weather["weathercode"]
    labels = weather["wmo_labels"]

    # Costruisci un indice tempo → indice
    time_index = {t: i for i, t in enumerate(times)}

    matched_events   = []
    total_windows    = len(degradation_windows)
    confirmed_count  = 0

    for dw in degradation_windows:
        # Espandi la finestra di ±1h per robustezza (dati orari)
        try:
            t_start = datetime.fromisoformat(dw["start"].replace("Z", ""))
            t_end   = datetime.fromisoformat(dw["end"].replace("Z", ""))
        except Exception:
            continue

        # Cerca l'ora più vicina nel dataset meteo
        best_hour  = t_start.replace(minute=0, second=0, microsecond=0)
        worst_prec = 0.0
        worst_wind = 0.0
        worst_cloud = 0.0
        worst_code  = 0
        worst_label = "Sereno"
        matched_hours = []

        check_dt = best_hour - timedelta(hours=1)
        while check_dt <= t_end + timedelta(hours=1):
            key = check_dt.strftime("%Y-%m-%dT%H:00")
            idx = time_index.get(key)
            if idx is not None:
                p = precip[idx] or 0
                w = wind[idx]   or 0
                c = cloud[idx]  or 0
                code = codes[idx] or 0
                if p > worst_prec or WMO_SEVERITY.get(code, 0) > WMO_SEVERITY.get(worst_code, 0):
                    worst_prec  = p
                    worst_wind  = w
                    worst_cloud = c
                    worst_code  = code
                    worst_label = labels[idx]
                matched_hours.append(key)
            check_dt += timedelta(hours=1)

        # Valuta se il meteo spiega il degrado usando la probabilità adattiva per frequenza
        severity   = WMO_SEVERITY.get(worst_code, 0)
        impact_score = get_weather_impact_score(freq_ghz, worst_prec, worst_wind, severity)
        
        # Consideriamo avverso se l'impatto stimato è significativo o se le soglie assolute sono violate
        is_adverse = impact_score >= 30.0 or worst_prec > 0.5 or severity >= 3

        if is_adverse:
            confirmed_count += 1

        matched_events.append({
            "window_start":  dw["start"],
            "window_end":    dw["end"],
            "min_rsl":       dw.get("min_rsl"),
            "es_count":      dw.get("es", 0),
            "precipitation": round(worst_prec, 2),
            "windspeed":     round(worst_wind, 1),
            "cloudcover":    round(worst_cloud, 0),
            "weathercode":   worst_code,
            "weather_label": worst_label,
            "impact_score":  round(impact_score, 1),
            "is_adverse":    is_adverse,
            "matched_hours": matched_hours,
        })

    # Calcola score correlazione
    score = round((confirmed_count / total_windows) * 100) if total_windows > 0 else 0
    confirmed_environmental = score >= 60

    # Testo riepilogativo
    if confirmed_environmental:
        max_prec = max((e['precipitation'] for e in matched_events), default=0.0)
        max_impact = max((e['impact_score'] for e in matched_events), default=0.0)
        
        if max_prec > 0.5:
            summary_text = (
                f"✅ CORRELAZIONE METEO CONFERMATA: il degrado RSL rilevato coincide con precipitazioni "
                f"di {max_prec:.1f} mm/h registrate nella zona. Probabilità impatto meteo: {max_impact:.0f}%. "
                f"Score correlazione: {score}%. L'attenuazione da pioggia spiega il fenomeno (Link Freq: {freq_ghz} GHz)."
            )
        elif any(e["weathercode"] in (95, 96, 99) for e in matched_events):
            summary_text = (
                f"✅ CORRELAZIONE METEO CONFERMATA: degrado coincidente con forte temporale rilevato in zona. "
                f"Probabilità impatto: {max_impact:.0f}%. Score correlazione: {score}%. Si raccomanda di attendere il ripristino naturale."
            )
        else:
            summary_text = (
                f"✅ CORRELAZIONE METEO PROBABILE: condizioni di forte vento ({max(e['windspeed'] for e in matched_events):.1f} km/h) "
                f"o maltempo nella zona. Score correlazione: {score}%. Possibile oscillazione dei pali o rifrazione atmosferica."
            )
    elif score > 0:
        summary_text = (
            f"⚠️ CORRELAZIONE PARZIALE: solo {confirmed_count}/{total_windows} finestre di degrado "
            f"coincidono con condizioni avverse. Score correlazione: {score}%. "
            f"Verificare anche potenziali cause hardware o interferenze locali."
        )
    else:
        summary_text = (
            f"❌ CORRELAZIONE NON CONFERMATA: il meteo era favorevole durante il degrado della tratta. "
            f"La causa atmosferica è esclusa. Intervenire sull'hardware (ODU/connettori) o cercare fonti di interferenza co-canale."
        )

    return {
        "correlation_score":      score,
        "events":                 matched_events,
        "summary_text":           summary_text,
        "confirmed_environmental": confirmed_environmental,
    }
