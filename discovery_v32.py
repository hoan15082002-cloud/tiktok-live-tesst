import asyncio
import re
from urllib.parse import urlparse
from playwright.async_api import async_playwright

SOURCE = "boembap2"
MAX_SCROLLS = 18
USER_RE = re.compile(r"^[A-Za-z0-9._]{2,24}$")


async def main():
    names = set()

    print("DISCOVERY V3.2 START", flush=True)
    print("SOURCE:", SOURCE, flush=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        context = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            locale="vi-VN",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
        )

        page = await context.new_page()

        try:
            response = await page.goto(
                f"https://www.tiktok.com/@{SOURCE}",
                wait_until="domcontentloaded",
                timeout=45000
            )

            print(
                "PROFILE HTTP:",
                response.status if response else "NONE",
                flush=True
            )

            await page.wait_for_timeout(4500)

            print(
                "PAGE TITLE:",
                (await page.title())[:100],
                flush=True
            )

            following = page.locator(
                '[data-e2e="following-count"]'
            )

            if await following.count():
                print(
                    "FOLLOWING COUNT LABEL:",
                    (await following.first.inner_text())[:80],
                    flush=True
                )
            else:
                print(
                    "FOLLOWING COUNT LABEL: NOT FOUND",
                    flush=True
                )

            triggers = [
                page.locator(
                    '[data-e2e="following-count"]'
                ),
                page.get_by_text(
                    re.compile(
                        r"^(Following|Đang follow)$",
                        re.I
                    )
                ),
            ]

            opened = False

            for trigger in triggers:
                try:
                    if await trigger.count():
                        await trigger.first.click(
                            timeout=4000
                        )
                        opened = True
                        break
                except Exception:
                    continue

            print(
                "FOLLOWING CLICKED:",
                opened,
                flush=True
            )

            await page.wait_for_timeout(3500)

            for index in range(MAX_SCROLLS + 1):
                dialogs = page.locator(
                    '[role="dialog"]'
                )

                if not await dialogs.count():
                    if index == 0:
                        print(
                            "FOLLOWING DIALOG: NOT FOUND",
                            flush=True
                        )
                    break

                dialog = dialogs.last

                hrefs = await dialog.locator(
                    'a[href*="/@"]'
                ).evaluate_all(
                    "els => els.map(a => "
                    "a.getAttribute('href') || '')"
                )

                for href in hrefs:
                    path = urlparse(href).path
                    match = re.match(
                        r"^/@([^/]+)/?$",
                        path
                    )

                    if match and USER_RE.fullmatch(
                        match.group(1)
                    ):
                        username = match.group(1)

                        if username.lower() != SOURCE.lower():
                            names.add(username)

                if index % 3 == 0:
                    print(
                        "SCROLL:",
                        index,
                        "UNIQUE FOLLOWING:",
                        len(names),
                        flush=True
                    )

                await dialog.evaluate(
                    """el => {
                        el.scrollTop = el.scrollHeight;
                        const nodes = [...el.querySelectorAll('*')]
                            .filter(n => n.scrollHeight >
                                         n.clientHeight + 100);
                        for (const n of nodes)
                            n.scrollTop = n.scrollHeight;
                    }"""
                )

                await page.wait_for_timeout(1100)

            print(
                "FOLLOWING USERNAMES FOUND:",
                len(names),
                flush=True
            )

            if names:
                print(
                    "SAMPLE USERNAMES:",
                    ", ".join(sorted(names)[:8]),
                    flush=True
                )
            else:
                print(
                    "NO FOLLOWING DATA: public visibility "
                    "does not guarantee browser access",
                    flush=True
                )

        except Exception as exc:
            print(
                "DISCOVERY ERROR:",
                type(exc).__name__,
                str(exc)[:250],
                flush=True
            )
            raise

        finally:
            await browser.close()


asyncio.run(main())
