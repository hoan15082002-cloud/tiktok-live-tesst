import asyncio
import os
import re
import html
from urllib.parse import unquote

import httpx
from TikTokLive import TikTokLiveClient
from TikTokLive.events import ConnectEvent, EnvelopeEvent

SOURCE_ACCOUNT = "boembap2"
REGIONS = ["vi-VN", "th-TH", "id-ID", "en-US", "en-GB"]
MAX_ROOMS = 20
MAX_CONCURRENT = 5
SCAN_SECONDS = 480
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 Version/18.0 Mobile Safari/604.1",
    "Accept": "text/html",
}
seen = set()
lock = asyncio.Lock()
semaphore = asyncio.Semaphore(MAX_CONCURRENT)


def normalized_page(content):
    return unquote(html.unescape(content).replace('\\/', '/'))


def extract_live_accounts(content):
    text = normalized_page(content)
    return set(re.findall(r'(?:https?://www\.tiktok\.com)?/@([A-Za-z0-9._]{2,24})/live(?:[?"\\/]|\b)', text, re.I))


def extract_following_accounts(content):
    # Experimental: public profile HTML may not expose the Following list.
    text = normalized_page(content)
    names = set()
    for match in re.finditer(r'"followingList"\s*:\s*\[(.*?)\]', text, re.S):
        names.update(re.findall(r'"uniqueId"\s*:\s*"([A-Za-z0-9._]{2,24})"', match.group(1)))
    names.discard(SOURCE_ACCOUNT)
    return names


async def discover():
    following = set()
    global_rooms = set()
    async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True, timeout=20) as http:
        try:
            response = await http.get(f"https://www.tiktok.com/@{SOURCE_ACCOUNT}")
            print("FOLLOWING SOURCE HTTP:", response.status_code, flush=True)
            if response.status_code == 200:
                following = extract_following_accounts(response.text)
            print("FOLLOWING FOUND:", len(following), flush=True)
        except Exception as exc:
            print("FOLLOWING ERROR:", type(exc).__name__, str(exc)[:120], flush=True)

        for region in REGIONS:
            try:
                response = await http.get("https://www.tiktok.com/live", headers={"Accept-Language": region})
                accounts = extract_live_accounts(response.text) if response.status_code == 200 else set()
                global_rooms.update(accounts)
                print("GLOBAL REGION:", region, "HTTP:", response.status_code, "FOUND:", len(accounts), flush=True)
            except Exception as exc:
                print("GLOBAL ERROR:", region, type(exc).__name__, flush=True)

    print("FOLLOWING TOTAL:", len(following), flush=True)
    print("GLOBAL TOTAL:", len(global_rooms), flush=True)
    return sorted(following | global_rooms)[:MAX_ROOMS]


async def telegram(message):
    try:
        async with httpx.AsyncClient(timeout=20) as http:
            response = await http.post(
                f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                data={"chat_id": CHAT_ID, "text": message},
            )
            response.raise_for_status()
            print("TELEGRAM SENT" if response.json().get("ok") else "TELEGRAM REJECTED", flush=True)
    except Exception as exc:
        print("TELEGRAM ERROR:", type(exc).__name__, flush=True)


async def scan(username):
    async with semaphore:
        client = TikTokLiveClient(unique_id=username)

        @client.on(ConnectEvent)
        async def connected(event):
            print("CONNECTED:", username, flush=True)

        @client.on(EnvelopeEvent)
        async def envelope(event):
            info = getattr(event, "envelope_info", None)
            envelope_id = str(getattr(info, "envelope_id", "") or "")
            if not envelope_id:
                return
            key = (username, envelope_id)
            async with lock:
                if key in seen:
                    return
                seen.add(key)
            print("ENVELOPE:", username, envelope_id, flush=True)
            await telegram(
                "Global TikTok Scanner V3\n"
                "Phat hien su kien ruong/phong bao!\n\n"
                f"Tai khoan: @{username}\n"
                f"Ma su kien: {envelope_id}\n"
                "So xu: Chua xac dinh\n"
                "Thoi gian mo: Chua xac dinh\n\n"
                f"https://www.tiktok.com/@{username}/live"
            )

        try:
            await asyncio.wait_for(client.start(), timeout=SCAN_SECONDS)
        except asyncio.TimeoutError:
            print("SCAN TIMEOUT:", username, flush=True)
        except Exception as exc:
            print("SCAN ERROR:", username, type(exc).__name__, str(exc)[:120], flush=True)
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass


async def main():
    if not TOKEN or not CHAT_ID:
        raise RuntimeError("Missing Telegram GitHub Secrets")
    print("GLOBAL SCANNER V3 STARTED", flush=True)
    print("SOURCE ACCOUNT:", SOURCE_ACCOUNT, flush=True)
    accounts = await discover()
    print("TOTAL CANDIDATES:", len(accounts), flush=True)
    if not accounts:
        print("DISCOVERY FAILED: NO ACCOUNTS FOUND", flush=True)
        return
    await asyncio.gather(*(scan(name) for name in accounts))
    print("UNIQUE ENVELOPE EVENTS:", len(seen), flush=True)
    print("SCAN FINISHED", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
