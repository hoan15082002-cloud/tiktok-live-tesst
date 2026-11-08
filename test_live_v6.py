import asyncio
import httpx
from TikTokLive import TikTokLiveClient
from TikTokLive.events import ConnectEvent, EnvelopeEvent

USERNAME = "oss_naoto_official"
TEST_SECONDS = 120

client = TikTokLiveClient(unique_id=USERNAME)
connected = False
envelopes = 0


@client.on(ConnectEvent)
async def on_connect(event):
    global connected
    connected = True
    print("WEBSOCKET CONNECTED", flush=True)
    print("ROOM ID:", client.room_id, flush=True)


@client.on(EnvelopeEvent)
async def on_envelope(event):
    global envelopes
    envelopes += 1
    info = getattr(event, "envelope_info", None)
    print(
        "ENVELOPE EVENT:",
        getattr(info, "envelope_id", "unknown"),
        flush=True,
    )


async def main():
    print("=== V6 LIVE CONNECTION TEST ===", flush=True)
    print("USERNAME:", USERNAME, flush=True)

    url = f"https://www.tiktok.com/@{USERNAME}/live"

    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=15,
        ) as http:
            response = await http.get(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0"
                },
            )
            print("PAGE HTTP:", response.status_code, flush=True)
            print("FINAL URL:", str(response.url), flush=True)
    except Exception as exc:
        print(
            "PAGE ERROR:",
            type(exc).__name__,
            str(exc)[:150],
            flush=True,
        )

    try:
        status = await asyncio.wait_for(
            client.is_live(),
            timeout=25,
        )
        print("IS_LIVE:", status, flush=True)
    except Exception as exc:
        print(
            "IS_LIVE ERROR:",
            type(exc).__name__,
            str(exc)[:150],
            flush=True,
        )

    try:
        await asyncio.wait_for(
            client.connect(),
            timeout=TEST_SECONDS,
        )
    except asyncio.TimeoutError:
        print("TEST TIME LIMIT REACHED", flush=True)
    except Exception as exc:
        print(
            "CONNECT ERROR:",
            type(exc).__name__,
            str(exc)[:300],
            flush=True,
        )
    finally:
        try:
            await client.disconnect()
        except Exception:
            pass

    print("=== V6 SUMMARY ===", flush=True)
    print("CONNECTED:", connected, flush=True)
    print("ENVELOPE EVENTS:", envelopes, flush=True)


asyncio.run(main())
