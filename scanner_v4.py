import asyncio
import os
import re
from urllib.parse import urlparse
from collections import defaultdict

import httpx
from playwright.async_api import async_playwright
from TikTokLive import TikTokLiveClient
from TikTokLive.events import ConnectEvent, EnvelopeEvent

# V4: Khong su dung Following
REGIONS = {
    "VN": "vi-VN",
    "TH": "th-TH",
    "ID": "id-ID",
    "PH": "en-PH",
    "MY": "ms-MY",
    "US": "en-US",
    "GB": "en-GB",
    "BR": "pt-BR",
    "JP": "ja-JP",
    "KR": "ko-KR",
}

# Gioi han de tranh gui qua nhieu request
MAX_ROOMS = 8
MAX_CONCURRENT = 3
SCAN_SECONDS = 180
PAGE_WAIT_MS = 3500

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

USERNAME_RE = re.compile(r"^[A-Za-z0-9._]{2,24}$")
seen = set()
stats = defaultdict(int)


async def telegram(message):
    if not TOKEN or not CHAT_ID:
        print("TELEGRAM DISABLED: missing secrets", flush=True)
        return

    try:
        async with httpx.AsyncClient(timeout=15) as http:
            response = await http.post(
                f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                data={"chat_id": CHAT_ID, "text": message},
            )
            result = response.json()
            print(
                "TELEGRAM SENT" if result.get("ok")
                else "TELEGRAM ERROR: " +
                     str(result.get("description", ""))[:100],
                flush=True,
            )
    except Exception as exc:
        print("TELEGRAM ERROR:", type(exc).__name__, flush=True)


def parse_live_link(url):
    """
    Chi nhan duong dan LIVE ro rang.
    Khong bien moi link profile thanh phong LIVE.
    """
    try:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()

        if host not in ("tiktok.com", "www.tiktok.com"):
            return None

        match = re.fullmatch(
            r"/@([^/]+)/live/?",
            parsed.path,
            flags=re.I,
        )

        if not match:
            return None

        username = match.group(1)

        if USERNAME_RE.fullmatch(username):
            return username

    except Exception:
        pass

    return None


async def discover():
    """
    Thu doc cac trang LIVE cong khai.
    Tham so lang KHONG xac minh quoc gia cua chu phong.
    """
    found = {}
    results = {}

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--disable-dev-shm-usage"],
        )

        try:
            for region, language in REGIONS.items():
                context = await browser.new_context(
                    locale=language,
                    viewport={"width": 1280, "height": 850},
                )

                page = await context.new_page()

                # Day la cac trang THU NGHIEM,
                # khong phai API kham pha chinh thuc.
                urls = [
                    f"https://www.tiktok.com/live?lang={language}",
                    f"https://www.tiktok.com/live/explore?lang={language}",
                ]

                region_names = set()
                statuses = []

                for url in urls:
                    try:
                        response = await page.goto(
                            url,
                            wait_until="domcontentloaded",
                            timeout=18000,
                        )

                        status = response.status if response else 0
                        statuses.append(status)

                        await page.wait_for_timeout(PAGE_WAIT_MS)

                        links = await page.locator(
                            'a[href*="/live"]'
                        ).evaluate_all(
                            "els => els.map(e => e.href || '')"
                        )

                        for link in links:
                            username = parse_live_link(link)
                            if username:
                                region_names.add(username)
                                found.setdefault(username.lower(), {
                                    "username": username,
                                    "source": region,
                                })

                    except Exception as exc:
                        print(
                            "SOURCE ERROR:", region,
                            type(exc).__name__,
                            str(exc)[:100],
                            flush=True,
                        )

                results[region] = len(region_names)

                print(
                    "REGION:", region,
                    "HTTP:", statuses,
                    "LIVE LINKS:", len(region_names),
                    flush=True,
                )

                await context.close()

        finally:
            await browser.close()

    print("DISCOVERY SUMMARY:", results, flush=True)
    print("TOTAL UNIQUE CANDIDATES:", len(found), flush=True)

    return list(found.values())


async def scan_room(item, semaphore):
    async with semaphore:
        username = item["username"]
        source = item["source"]

        client = TikTokLiveClient(unique_id=username)

        @client.on(ConnectEvent)
        async def on_connect(event):
            stats["connected"] += 1
            print(
                "CONNECTED:", username,
                "SOURCE:", source,
                "ROOM:", client.room_id,
                flush=True,
            )

        @client.on(EnvelopeEvent)
        async def on_envelope(event):
            info = getattr(event, "envelope_info", None)

            envelope_id = str(
                getattr(info, "envelope_id", "") or ""
            )

            room_id = str(
                getattr(info, "room_id", "") or ""
            )

            if not envelope_id:
                return

            key = (username.lower(), envelope_id)

            if key in seen:
                return

            seen.add(key)
            stats["envelopes"] += 1

            print(
                "ENVELOPE:",
                username,
                envelope_id,
                flush=True,
            )

            message = (
                "GLOBAL TIKTOK SCANNER V4\n"
                "Phat hien su kien ruong/phong bao!\n\n"
                f"Tai khoan: @{username}\n"
                f"Nguon kham pha: {source}\n"
                f"Ma su kien: {envelope_id}\n"
                f"Room ID: {room_id}\n"
                "So xu: Chua xac minh\n"
                "Thoi gian mo: Chua xac minh\n\n"
                f"https://www.tiktok.com/@{username}/live"
            )

            await telegram(message)

        print("CHECKING:", username, flush=True)

        try:
            # is_live chi kiem tra tai khoan da biet,
            # khong tu tim them tai khoan moi.
            live = await asyncio.wait_for(
                client.is_live(),
                timeout=20,
            )

            if not live:
                print("NOT LIVE:", username, flush=True)
                stats["offline"] += 1
                return

            print("LIVE CONFIRMED:", username, flush=True)
            stats["live"] += 1

            await asyncio.wait_for(
                client.start(),
                timeout=SCAN_SECONDS,
            )

        except asyncio.TimeoutError:
            print("SCAN TIME LIMIT:", username, flush=True)

        except Exception as exc:
            stats["errors"] += 1
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
    print("GLOBAL TIKTOK SCANNER V4 START", flush=True)
    print("MODE: MULTI-REGION PUBLIC DISCOVERY", flush=True)
    print("FOLLOWING: DISABLED", flush=True)

    candidates = await discover()

    if not candidates:
        print(
            "DISCOVERY FAILED: NO LIVE ACCOUNTS FOUND",
            flush=True,
        )
        print(
            "PUBLIC PAGES MAY REQUIRE LOGIN OR "
            "MAY NOT EXPOSE LIVE ROOM LINKS.",
            flush=True,
        )
        print(
            "NO ROOM SCANNED. NO TREASURE ALERT SENT.",
            flush=True,
        )
        return

    selected = candidates[:MAX_ROOMS]

    print("SELECTED ROOMS:", len(selected), flush=True)

    semaphore = asyncio.Semaphore(MAX_CONCURRENT)

    await asyncio.gather(
        *(scan_room(item, semaphore) for item in selected)
    )

    print("FINAL SUMMARY", flush=True)
    print("CANDIDATES:", len(candidates), flush=True)
    print("LIVE CONFIRMED:", stats["live"], flush=True)
    print("CONNECTED:", stats["connected"], flush=True)
    print("ENVELOPES:", stats["envelopes"], flush=True)
    print("SCAN ERRORS:", stats["errors"], flush=True)


if __name__ == "__main__":
    asyncio.run(main())
