import asyncio
import os
import re
import time
from urllib.parse import unquote

import httpx
from TikTokLive import TikTokLiveClient
from TikTokLive.events import ConnectEvent, EnvelopeEvent

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# Các tài khoản dự phòng từng được thử ở V2.
# Đây KHÔNG phải danh sách phòng chắc chắn đang LIVE.
FALLBACK = [
    "jaltaaaa83",
    "loupleking",
    "banaking922",
    "boembap2",
]

# Thử tìm phòng từ các trang LIVE công khai.
# Các trang này có thể không trả về danh sách phòng.
REGIONS = [
    "vi-VN", "th-TH", "id-ID", "en-PH",
    "ms-MY", "en-US", "en-GB",
    "pt-BR", "ja-JP", "ko-KR",
]

SCAN_SECONDS = 480
MAX_ROOMS = 5
DISCOVERY_LIMIT = 20

seen_envelopes = set()
connected_rooms = set()
detected_count = 0


async def telegram(message):
    if not TOKEN or not CHAT_ID:
        print("TELEGRAM DISABLED: MISSING SECRETS", flush=True)
        return

    try:
        async with httpx.AsyncClient(timeout=15) as http:
            response = await http.post(
                f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                data={
                    "chat_id": CHAT_ID,
                    "text": message,
                    "disable_web_page_preview": "true",
                },
            )
            result = response.json()
            if response.is_success and result.get("ok"):
                print("TELEGRAM SENT", flush=True)
            else:
                print(
                    "TELEGRAM ERROR:",
                    response.status_code,
                    result.get("description", "")[:120],
                    flush=True,
                )
    except Exception as exc:
        print("TELEGRAM ERROR:", type(exc).__name__, flush=True)


def normalize_username(value):
    value = unquote(str(value)).strip().lstrip("@")
    if re.fullmatch(r"[A-Za-z0-9._]{2,24}", value):
        return value
    return None


async def discover():
    candidates = []
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) "
            "AppleWebKit/605.1.15 Version/18.0 Mobile Safari/604.1"
        )
    }

    pattern = re.compile(
        r"(?:https?://(?:www\.)?tiktok\.com)?"
        r"/@([A-Za-z0-9._]{2,24})/live",
        re.IGNORECASE,
    )

    async with httpx.AsyncClient(
        headers=headers,
        follow_redirects=True,
        timeout=12,
    ) as http:
        for region in REGIONS:
            try:
                response = await http.get(
                    "https://www.tiktok.com/live",
                    params={"lang": region},
                    headers={"Accept-Language": region},
                )

                names = []
                if response.status_code == 200:
                    names = [
                        normalize_username(name)
                        for name in pattern.findall(response.text)
                    ]
                    names = [name for name in names if name]

                unique = list(dict.fromkeys(names))
                print(
                    "DISCOVERY REGION:",
                    region,
                    "HTTP:",
                    response.status_code,
                    "FOUND:",
                    len(unique),
                    flush=True,
                )

                candidates.extend(unique)

            except Exception as exc:
                print(
                    "DISCOVERY ERROR:",
                    region,
                    type(exc).__name__,
                    flush=True,
                )

    candidates = list(dict.fromkeys(candidates))
    print("DISCOVERY TOTAL:", len(candidates), flush=True)

    if not candidates:
        print(
            "DISCOVERY UNAVAILABLE: NO PUBLIC LIVE LINKS",
            flush=True,
        )

    return candidates[:DISCOVERY_LIMIT]


async def scan_room(username):
    global detected_count

    client = TikTokLiveClient(unique_id=username)

    @client.on(ConnectEvent)
    async def on_connect(event):
        connected_rooms.add(username)
        print(
            "CONNECTED:",
            username,
            "ROOM:",
            client.room_id,
            flush=True,
        )

    @client.on(EnvelopeEvent)
    async def on_envelope(event):
        global detected_count

        info = getattr(event, "envelope_info", None)
        envelope_id = str(
            getattr(info, "envelope_id", "") or ""
        )
        room_id = str(
            getattr(info, "room_id", "") or ""
        )

        if not envelope_id:
            print("ENVELOPE WITHOUT ID:", username, flush=True)
            return

        key = (username, envelope_id)
        if key in seen_envelopes:
            return

        seen_envelopes.add(key)
        detected_count += 1

        print(
            "ENVELOPE:",
            username,
            envelope_id,
            flush=True,
        )

        message = (
            "GLOBAL TIKTOK SCANNER V5\n"
            "Phat hien su kien ruong/phong bao!\n\n"
            f"Tai khoan: @{username}\n"
            f"Ma su kien: {envelope_id}\n"
            f"Room ID: {room_id}\n"
            "So xu: Chua xac dinh\n"
            "Thoi gian mo: Chua xac dinh\n\n"
            f"https://www.tiktok.com/@{username}/live"
        )

        await telegram(message)

    print("CHECKING:", username, flush=True)

    try:
        await asyncio.wait_for(
            client.start(),
            timeout=SCAN_SECONDS,
        )
    except asyncio.TimeoutError:
        print("SCAN TIME LIMIT:", username, flush=True)
    except Exception as exc:
        print(
            "SCAN ERROR:",
            username,
            type(exc).__name__,
            str(exc)[:160],
            flush=True,
        )
    finally:
        try:
            await client.disconnect()
        except Exception:
            pass


async def main():
    print("GLOBAL TIKTOK SCANNER V5 START", flush=True)
    print("MODE: PUBLIC DISCOVERY + FALLBACK", flush=True)
    print("FOLLOWING: DISABLED", flush=True)
    print("SCAN SECONDS:", SCAN_SECONDS, flush=True)

    discovered = await discover()

    # Ưu tiên phòng tìm được, sau đó bổ sung nguồn dự phòng.
    usernames = list(
        dict.fromkeys(discovered + FALLBACK)
    )[:MAX_ROOMS]

    print("TOTAL CANDIDATES:", len(usernames), flush=True)
    print("CANDIDATES:", ", ".join(usernames), flush=True)

    if not usernames:
        print("NO ACCOUNTS TO SCAN", flush=True)
        return

    await telegram(
        "Global TikTok Scanner V5 started\n"
        f"Public discovery: {len(discovered)}\n"
        f"Candidates to check: {len(usernames)}\n"
        "Coin and countdown: not yet verified"
    )

    started = time.monotonic()

    await asyncio.gather(
        *(scan_room(name) for name in usernames),
        return_exceptions=True,
    )

    elapsed = round(time.monotonic() - started)

    print("=== FINAL SUMMARY ===", flush=True)
    print("DISCOVERED:", len(discovered), flush=True)
    print("CANDIDATES:", len(usernames), flush=True)
    print("CONNECTED ROOMS:", len(connected_rooms), flush=True)
    print("ENVELOPES:", detected_count, flush=True)
    print("ELAPSED SECONDS:", elapsed, flush=True)

    if not connected_rooms:
        print(
            "NO LIVE CONNECTION: CHECK DISCOVERY AND OFFLINE ERRORS",
            flush=True,
        )


if __name__ == "__main__":
    asyncio.run(main())
