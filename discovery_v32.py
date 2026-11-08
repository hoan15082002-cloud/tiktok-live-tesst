import asyncio
import json
import re
from pathlib import Path
from urllib.parse import urlparse
from playwright.async_api import async_playwright

SOURCE = "boembap2"
MAX_SCROLLS = 12
OUTPUT = Path("discovery_report")
OUTPUT.mkdir(exist_ok=True)

USER_RE = re.compile(r"^[A-Za-z0-9._]{2,24}$")


def extract_usernames(urls):
    result = set()

    for url in urls:
        path = urlparse(url).path
        match = re.match(r"^/@([^/]+)/?$", path)

        if match:
            name = match.group(1)
            if (
                USER_RE.fullmatch(name)
                and name.lower() != SOURCE.lower()
            ):
                result.add(name)

    return result


async def collect_links(page):
    return await page.locator('a[href*="/@"]').evaluate_all(
        """els => els.map(a => a.href || '')"""
    )


async def diagnose(page, label):
    print(f"=== DIAGNOSTIC {label} ===", flush=True)
    print("URL:", page.url, flush=True)
    print("TITLE:", (await page.title())[:120], flush=True)

    dialogs = page.locator('[role="dialog"]')
    print("DIALOG COUNT:", await dialogs.count(), flush=True)

    selectors = [
        '[data-e2e="following-count"]',
        '[data-e2e*="follow"]',
        '[role="dialog"]',
        '[role="list"]',
        '[role="listitem"]',
        'a[href*="/@"]',
    ]

    for selector in selectors:
        print(
            "SELECTOR:",
            selector,
            "COUNT:",
            await page.locator(selector).count(),
            flush=True
        )

    text = (await page.locator("body").inner_text())[:15000]
    low = text.lower()

    signals = [
        "log in", "login", "sign up",
        "đăng nhập", "đăng ký",
        "verify", "captcha",
        "following", "đang follow",
        "something went wrong",
        "try again",
    ]

    for signal in signals:
        if signal in low:
            print("PAGE SIGNAL:", signal, flush=True)

    # Chỉ lưu số liệu và các tín hiệu, không lưu
    # cookie hoặc dữ liệu phiên đăng nhập.
    return {
        "url": page.url,
        "title": (await page.title())[:120],
        "dialog_count": await dialogs.count(),
        "signals": [s for s in signals if s in low],
        "links_count": await page.locator(
            'a[href*="/@"]'
        ).count(),
    }


async def main():
    print("GLOBAL DISCOVERY V3.3 START", flush=True)
    print("SOURCE:", SOURCE, flush=True)

    usernames = set()
    report = {}
    previous_count = -1
    unchanged = 0

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--disable-dev-shm-usage"]
        )

        context = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            locale="vi-VN",
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

            await page.wait_for_timeout(4000)

            following = page.locator(
                '[data-e2e="following-count"]'
            )

            if await following.count():
                print(
                    "FOLLOWING COUNT:",
                    (await following.first.inner_text())[:80],
                    flush=True
                )
            else:
                print("FOLLOWING COUNT: NOT FOUND", flush=True)

            report["before"] = await diagnose(page, "BEFORE")

            clicked = False

            triggers = [
                following,
                page.get_by_text(
                    re.compile(r"^(Following|Đang follow)$", re.I)
                )
            ]

            for trigger in triggers:
                try:
                    if await trigger.count():
                        await trigger.first.click(timeout=5000)
                        clicked = True
                        break
                except Exception as exc:
                    print(
                        "CLICK ATTEMPT:",
                        type(exc).__name__,
                        flush=True
                    )

            print("FOLLOWING CLICKED:", clicked, flush=True)
            await page.wait_for_timeout(4000)

            report["after"] = await diagnose(page, "AFTER")

            # Kiểm tra liên kết toàn trang.
            initial_links = await collect_links(page)
            print(
                "PAGE PROFILE LINKS:",
                len(initial_links),
                flush=True
            )

            # Chỉ chấp nhận username nếu tìm được
            # vùng Following rõ ràng.
            dialog = page.locator('[role="dialog"]')

            if await dialog.count():
                print("FOLLOWING DIALOG: FOUND", flush=True)

                for index in range(MAX_SCROLLS + 1):
                    active = dialog.last

                    hrefs = await active.locator(
                        'a[href*="/@"]'
                    ).evaluate_all(
                        """els => els.map(a => a.href || '')"""
                    )

                    usernames.update(extract_usernames(hrefs))

                    print(
                        "SCROLL:",
                        index,
                        "USERNAMES:",
                        len(usernames),
                        flush=True
                    )

                    if len(usernames) == previous_count:
                        unchanged += 1
                    else:
                        unchanged = 0

                    previous_count = len(usernames)

                    if unchanged >= 4:
                        print(
                            "SCROLL STOP: NO NEW ACCOUNTS",
                            flush=True
                        )
                        break

                    await active.evaluate(
                        """el => {
                            const nodes = [el, ...el.querySelectorAll('*')];
                            for (const n of nodes) {
                                if (n.scrollHeight > n.clientHeight + 50) {
                                    n.scrollTop = n.scrollHeight;
                                }
                            }
                        }"""
                    )

                    await page.wait_for_timeout(1400)

            else:
                print(
                    "FOLLOWING DIALOG: NOT FOUND",
                    flush=True
                )

            print(
                "FOLLOWING USERNAMES FOUND:",
                len(usernames),
                flush=True
            )

            if usernames:
                print(
                    "SAMPLE:",
                    ", ".join(sorted(usernames)[:10]),
                    flush=True
                )
            else:
                print(
                    "DISCOVERY BLOCKED OR STRUCTURE UNKNOWN",
                    flush=True
                )

            report["clicked"] = clicked
            report["following_usernames_found"] = len(usernames)
            report["candidate_links_on_page"] = len(initial_links)
            report["note"] = (
                "Names from dialog are candidates only; "
                "membership must be verified."
            )

            # Ảnh chỉ dùng để xem giao diện TikTok
            # có hiện danh sách hay thông báo lỗi.
            await page.screenshot(
                path=str(OUTPUT / "following_screen.png"),
                full_page=False,
                timeout=15000
            )

        except Exception as exc:
            print(
                "DISCOVERY ERROR:",
                type(exc).__name__,
                str(exc)[:300],
                flush=True
            )
            report["error"] = (
                f"{type(exc).__name__}: {str(exc)[:300]}"
            )
            raise

        finally:
            (OUTPUT / "report.json").write_text(
                json.dumps(
                    report,
                    ensure_ascii=False,
                    indent=2
                ),
                encoding="utf-8"
            )

            (OUTPUT / "usernames.txt").write_text(
                "\n".join(sorted(usernames)),
                encoding="utf-8"
            )

            await browser.close()


asyncio.run(main())
