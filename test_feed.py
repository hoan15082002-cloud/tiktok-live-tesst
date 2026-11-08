import requests

url = "https://webcast.tiktok.com/webcast/feed/"
params = {
    "channel_id": "86",
    "count": "5",
}

try:
    r = requests.get(
        url,
        params=params,
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=15,
    )

    print("HTTP STATUS:", r.status_code)
    print("CONTENT TYPE:", r.headers.get("content-type"))
    print("RESPONSE LENGTH:", len(r.content))

    try:
        data = r.json()
        print("JSON KEYS:", list(data.keys())[:15])
        print("STATUS CODE:", data.get("status_code"))
        print("ROOM COUNT:", len(data.get("data") or []))
    except ValueError:
        print("NOT A JSON RESPONSE")
        print("BODY PREVIEW:", r.text[:150])

except Exception as e:
    print("REQUEST ERROR:", type(e).__name__, str(e)[:250])
