import asyncio
import os
import httpx
from TikTokLive import TikTokLiveClient
from TikTokLive.events import ConnectEvent, EnvelopeEvent

ACCOUNTS = [
    "loupleking",
    "banaking922",
    "boembap2",
    "jaltaaaa83",
]

SCAN_SECONDS = 600
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

seen = set()
seen_lock = asyncio.Lock()


async def telegram(text):
    if not TOKEN or not CHAT_ID:
        print("TELEGRAM SECRETS MISSING", flush=True)
        return

    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    async with httpx.AsyncClient(timeout=20) as http:
        try:
            response = await http.post(
                url, data={"chat_id": CHAT_ID, "text": text}
            )
            response.raise_for_status()
            print("TELEGRAM SENT", flush=True)
        except Exception as exc:
            print("TELEGRAM ERROR:", type(exc).__name__, flush=True)


async def scan_user(username):
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

        async with seen_lock:
            if envelope_id in seen:
                return
            seen.add(envelope_id)

        print("ENVELOPE:", username, envelope_id, flush=True)

        await telegram(
            "TikTok LIVE - Phat hien su kien ruong/phong bao!\n"
            f"Tai khoan: @{username}\n"
            f"Ma ruong: {envelope_id}\n"
            "Thoi gian con lai: Chua xac dinh\n"
            "So xu: Chua xac dinh\n"
            f"https://www.tiktok.com/@{username}/live"
        )

    try:
        await asyncio.wait_for(
            client.start(), timeout=SCAN_SECONDS
        )
    except asyncio.TimeoutError:
        print("SCAN TIMEOUT:", username, flush=True)
    except Exception as exc:
        print("SCAN ERROR:", username,
              type(exc).__name__, str(exc)[:150], flush=True)
    finally:
        try:
            await client.disconnect()
        except Exception:
            pass


async def main():
    if not TOKEN or not CHAT_ID:
        raise RuntimeError("Missing Telegram secrets")

    print("SCANNING ACCOUNTS:", len(ACCOUNTS), flush=True)

    await asyncio.gather(
        *(scan_user(user) for user in ACCOUNTS)
    )

    print("TOTAL UNIQUE ENVELOPES:", len(seen), flush=True)


asyncio.run(main())
