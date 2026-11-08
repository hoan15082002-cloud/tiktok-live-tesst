import asyncio
import json
import re
from urllib.parse import urlparse

from playwright.async_api import async_playwright
from TikTokLive import TikTokLiveClient

REGIONS = {
    "VN": "vi-VN",
    "TH": "th-TH",
    "US": "en-US",
    "JP": "ja-JP",
    "BR": "pt-BR",
}

MAX_VERIFY = 12
candidates = set()
sources = set()

USER_RE = re.compile(r"^[A-Za-z0-9._]{2,24}$")


def add_username(value):
    if not isinstance(value, str):
        return
    name = value.lstrip("@")
    if USER_RE.fullmatch(name):
        candidates.add(name)


def inspect_json(obj, depth=0):
    if depth > 12:
        return

    if isinstance(obj, dict):
        # Chi nhan tai khoan trong cau truc
        # co dau hieu lien quan den LIVE.
        keys = set(obj.keys())
        live_keys = {
            "roomId", "room_id", "roomInfo",
            "liveRoom", "live_room",
            "webcastId", "webcast_id",
        }

        if keys & live_keys:
            for key in ("uniqueId", "unique_id", "username"):
                add_username(obj.get(key))

            for key in ("owner", "user", "host"):
                owner = obj.get(key)
                if isinstance(owner, dict):
                    for field in (
                        "uniqueId", "unique_id", "username"
                    ):
                        add_username(owner.get(field))

        for value in obj.values():
            inspect_json(value, depth + 1)

    elif isinstance(obj, list):
        for value in obj[:300]:
            inspect_json(value, depth + 1)


async def inspect_page(page, region):
    links = await page.locator(
        'a[href*="/@"]'
    ).evaluate_all(
        "els => els.map(e => e.href || '')"
    )

    live_links = 0

    for link in links:
        parsed = urlparse(link)
        match = re.fullmatch(
            r"/@([^/]+)/live/?",
            parsed.path,
        )
        if match:
            add_username(match.group(1))
            live_links += 1

    print(
        "PAGE LIVE LINKS:",
        region, live_links,
        flush=True,
    )

    scripts = await page.locator(
        'script[type="application/json"],'
        'script#__UNIVERSAL_DATA_FOR_REHYDRATION__,'
        'script#SIGI_STATE'
    ).all_text_contents()

    print(
        "JSON SCRIPTS:",
        region, len(scripts),
        flush=True,
    )

    for raw in scripts[:15]:
        try:
            inspect_json(json.loads(raw))
        except (ValueError, TypeError):
            pass


async def verify(username):
    client = TikTokLiveClient(unique_id=username)

    try:
        result = await asyncio.wait_for(
            client.is_live(), timeout=20
        )
        print(
            "VERIFY:",
            username,
            "LIVE" if result else "OFFLINE",
            flush=True,
        )
        return bool(result)
    except Exception as exc:
        print(
            "VERIFY ERROR:",
            username,
            type(exc).__name__,
            flush=True,
        )
        return False
    finally:
        try:
            await client.disconnect()
        except Exception:
            pass


async def main():
    print("=== GLOBAL DISCOVERY V7 ===", flush=True)
    print("MODE: PUBLIC LIVE FEED DIAGNOSTIC", flush=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        try:
            for region, locale in REGIONS.items():
                context = await browser.new_context(
                    locale=locale,
                    viewport={"width": 1280, "height": 850},
                )
                page = await context.new_page()

                # Chi ghi nhan URL va status,
                # khong ghi cookie hoac token.
                async def on_response(response):
                    url = response.url.lower()
                    if (
                        "tiktok.com" in url
                        and any(word in url for word in (
                            "webcast", "live/feed",
                            "live/explore"
                        ))
                    ):
                        sources.add(urlparse(url).path)

                page.on("response", on_response)

                for path in ("/live", "/live/explore"):
                    try:
                        response = await page.goto(
                            "https://www.tiktok.com" + path,
                            wait_until="domcontentloaded",
                            timeout=18000,
                        )

                        await page.wait_for_timeout(2500)

                        print(
                            "REGION:", region,
                            "PATH:", path,
                            "HTTP:",
                            response.status if response else 0,
                            "TITLE:",
                            (await page.title())[:65],
                            flush=True,
                        )

                        await inspect_page(page, region)

                    except Exception as exc:
                        print(
                            "PAGE ERROR:",
                            region,
                            type(exc).__name__,
                            flush=True,
                        )

                await context.close()

        finally:
            await browser.close()

    print(
        "LIVE RELATED ENDPOINT PATHS:",
        sorted(sources)[:20],
        flush=True,
    )

    print(
        "UNIQUE CANDIDATES:",
        len(candidates),
        flush=True,
    )

    if not candidates:
        print(
            "DISCOVERY FAILED: NO LIVE USERNAMES",
            flush=True,
        )
        print(
            "No verified public LIVE feed available.",
            flush=True,
        )
        return

    names = sorted(candidates)[:MAX_VERIFY]

    print("VERIFYING:", len(names), flush=True)

    results = await asyncio.gather(
        *(verify(name) for name in names)
    )

    live_names = [
        name for name, live in zip(names, results)
        if live
    ]

    print("LIVE VERIFIED:", len(live_names), flush=True)

    for name in live_names:
        print("VERIFIED ROOM:", name, flush=True)

    print("V7 DISCOVERY TEST FINISHED", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
