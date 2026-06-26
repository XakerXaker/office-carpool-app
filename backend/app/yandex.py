import httpx

from .geo import haversine_km


def _offline_estimate(o_lat: float, o_lng: float, d_lat: float, d_lng: float):
    straight = haversine_km(o_lat, o_lng, d_lat, d_lng)
    road_km = straight * 1.35
    duration_min = (road_km / 28) * 60
    return round(road_km, 2), int(round(duration_min)), "offline"


def estimate_route(o_lat: float, o_lng: float, d_lat: float, d_lng: float):
    if not "YANDEX_API_KEY":
        return _offline_estimate(o_lat, o_lng, d_lat, d_lng)

    try:
        url = "https://api.routing.yandex.net/v2/route"
        params = {
            "apikey": "YANDEX_API_KEY",
            "waypoints": f"{o_lat},{o_lng}|{d_lat},{d_lng}",
            "mode": "driving",
        }
        resp = httpx.get(url, params=params, timeout=8.0)
        resp.raise_for_status()
        data = resp.json()
        route = data["route"]["legs"][0]
        distance_km = round(route["distance"]["value"] / 1000, 2)
        duration_min = int(round(route["duration"]["value"] / 60))
        return distance_km, duration_min, "yandex"

    except Exception:
        return _offline_estimate(o_lat, o_lng, d_lat, d_lng)
