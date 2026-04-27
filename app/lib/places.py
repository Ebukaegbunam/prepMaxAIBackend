"""Google Places API wrapper for restaurant search."""
import httpx
import structlog

log = structlog.get_logger()

_PLACES_URL = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"


async def nearby_restaurants(
    lat: float,
    lng: float,
    radius_m: int,
    api_key: str,
    keyword: str | None = None,
    max_results: int = 5,
) -> list[dict]:
    params: dict = {
        "location": f"{lat},{lng}",
        "radius": radius_m,
        "type": "restaurant",
        "key": api_key,
    }
    if keyword:
        params["keyword"] = keyword

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(_PLACES_URL, params=params)
        response.raise_for_status()
        data = response.json()

    results = []
    for place in data.get("results", [])[:max_results]:
        geometry = place.get("geometry", {}).get("location", {})
        results.append({
            "place_id": place.get("place_id"),
            "name": place.get("name"),
            "address": place.get("vicinity"),
            "rating": place.get("rating"),
            "lat": geometry.get("lat"),
            "lng": geometry.get("lng"),
        })
    return results
