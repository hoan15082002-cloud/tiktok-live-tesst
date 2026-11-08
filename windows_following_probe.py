"""Windows diagnostic: read publicly visible TikTok Following via a real Chrome window.
No credentials, cookies, paid API or TikTok endpoint signing.
Run: py -m pip install playwright
     py -m playwright install chromium
     py windows_following_probe.py --user boembap2
"""
import argparse
import csv
import re
import time
from pathlib import Path
from urllib.parse import unquote, urlparse
from playwright.sync_api import sync_playwright

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--user", default="boembap2")
    p.add_argument("--scrolls", type=int, default=35)
    args=p.parse_args()
    username=args.user.strip().lstrip("@")
    if not re.fullmatch(r"[A-Za-z0-9._]+", username):
        raise SystemExit("Invalid TikTok username")
    out=Path("following_"+username+".csv")
    with sync_playwright() as pw:
        ctx=pw.chromium.launch_persistent_context(
            user_data_dir=str(Path(".tiktok_probe_browser").resolve()),
            headless=False,
            viewport={"width":1280,"height":850},
            locale="vi-VN",
        )
        page=ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto("https://www.tiktok.com/@"+username, wait_until="domcontentloaded", timeout=45000)
        print("PROFILE_URL:",page.url)
        print("Chrome has opened. If a challenge appears, use normal on-screen controls.")
        input("When profile is visible, press ENTER in this terminal to continue...")
        # Prefer the visible Following control; do not mistake Followers for Following.
        clicked=False
        for selector in [
            '[data-e2e="following-count"]',
            '[data-e2e="following"]',
            'a[href$="/following"]',
            'button:has-text("Following")',
            'button:has-text("Đang follow")',
        ]:
            try:
                loc=page.locator(selector).first
                if loc.count() and loc.is_visible():
                    loc.click(timeout=3000)
                    clicked=True
                    break
            except Exception:
                pass
        if not clicked:
            print("AUTO_CLICK_FAILED: Click the Following/Đang follow count manually in Chrome.")
        input("Once the Following list is OPEN, press ENTER here...")
        seen=set()
        # Extract visible profile links from the Following dialog only, not the whole profile page.
        for i in range(max(1,args.scrolls)):
            found=page.evaluate("""() => {
                const dialogs=[...document.querySelectorAll('[role="dialog"], [data-e2e*="follow"], [class*="DivUserListContainer"]')];
                const visible=dialogs.filter(e=>e.getBoundingClientRect().width>0 && e.getBoundingClientRect().height>0);
                const root=visible.sort((a,b)=>b.querySelectorAll('a[href*="/@"]').length-a.querySelectorAll('a[href*="/@"]').length)[0];
                if (!root) return {users:[],scrolled:false};
                const links=[...root.querySelectorAll('a[href*="/@"]')].map(a=>a.getAttribute('href'));
                const candidates=[root,...root.querySelectorAll('*')].filter(e=>e.scrollHeight>e.clientHeight+80);
                candidates.sort((a,b)=>(b.scrollHeight-b.clientHeight)-(a.scrollHeight-a.clientHeight));
                if(candidates[0]) candidates[0].scrollTop += Math.max(450,candidates[0].clientHeight*.8);
                return {users:links,scrolled:!!candidates[0]};
            }""")
            for href in found["users"]:
                m=re.search(r"/@([A-Za-z0-9._]+)", unquote(href or ""))
                if m and m.group(1).lower()!=username.lower():
                    seen.add(m.group(1))
            print(f"SCROLL {i+1}/{args.scrolls}: {len(seen)} unique following; scrollable={found['scrolled']}", flush=True)
            time.sleep(1.1)
            if not found["scrolled"] and i>=2:
                break
        with out.open("w",newline="",encoding="utf-8-sig") as f:
            w=csv.writer(f); w.writerow(["username","profile_url"])
            for u in sorted(seen): w.writerow([u,"https://www.tiktok.com/@"+u])
        print("RESULT:", "FOLLOWING_FOUND" if seen else "NO_FOLLOWING_EXTRACTED")
        print("COUNT:",len(seen))
        print("OUTPUT:",out.resolve())
        print("Note: count is visible/extracted usernames only; completeness is NOT guaranteed.")
        input("Press ENTER to close Chrome...")
        ctx.close()

if __name__=="__main__":
    main()
