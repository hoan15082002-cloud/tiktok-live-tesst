"""Read-only diagnostic for the legacy public TikTok LIVE recommendation feed.
No credentials, proxies, signing bypass, or Telegram messages.
A 200 response with an empty body is NOT discovery success.
"""
import json
import requests

URL = "https://webcast.tiktok.com/webcast/feed/"
HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json",
}
def probe(channel):
    try:
        response = requests.get(
            URL,
            params={"channel_id": str(channel), "count": "5", "max_time": "0"},
            headers=HEADERS,
            timeout=18,
            allow_redirects=False,
        )
    except requests.RequestException as exc:
        print(f"CHANNEL {channel}: REQUEST_ERROR {type(exc).__name__}", flush=True)
        return 0
    print(f"CHANNEL {channel}: HTTP={response.status_code} BYTES={len(response.content)} CONTENT_TYPE={response.headers.get('content-type', '')}", flush=True)
    if not response.content:
        print(f"CHANNEL {channel}: EMPTY_BODY (not a working discovery feed)", flush=True)
        return 0
    try:
        payload = response.json()
    except ValueError:
        print(f"CHANNEL {channel}: NON_JSON_RESPONSE", flush=True)
        return 0
    if not isinstance(payload, dict):
        print(f"CHANNEL {channel}: UNEXPECTED_JSON_SHAPE", flush=True)
        return 0
    print(f"CHANNEL {channel}: STATUS_CODE={payload.get('status_code', 'missing')} KEYS={sorted(payload)[:12]}", flush=True)
    entries = payload.get("data")
    if isinstance(entries, dict):
        entries = entries.get("data") or entries.get("rooms") or entries.get("list")
    if not isinstance(entries, list):
        entries = []
    names = set()
    for entry in entries[:50]:
        if not isinstance(entry, dict):
            continue
        room = entry.get("data") if isinstance(entry.get("data"), dict) else entry
        owner = room.get("owner") if isinstance(room, dict) else None
        if isinstance(owner, dict):
            name = owner.get("display_id") or owner.get("unique_id") or owner.get("uniqueId")
            if isinstance(name, str) and name.strip():
                names.add(name.strip().lstrip("@"))
    print(f"CHANNEL {channel}: ENTRIES={len(entries)} USERNAMES={len(names)}", flush=True)
    for name in sorted(names)[:10]:
        print(f"DISCOVERED @{name}", flush=True)
    return len(names)

if __name__ == "__main__":
    print("=== FREE LEGACY FEED DIAGNOSTIC ===", flush=True)
    count = sum(probe(channel) for channel in (87, 86))
    print(f"TOTAL_DISCOVERED={count}", flush=True)
    print("RESULT=DISCOVERY_FOUND" if count else "RESULT=NO_PUBLIC_FEED_VERIFIED", flush=True)
