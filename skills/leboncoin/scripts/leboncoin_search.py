#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "playwright",
#   "aiohttp",
#   "beautifulsoup4",
# ]
# ///
"""
Leboncoin URL scraper.
Fetches multiple pages and returns list of item detail URLs.

Usage:
    uv run leboncoin_search.py "https://www.leboncoin.fr/recherche?text=haltere&locations=Paris__..."
    uv run leboncoin_search.py "https://..." --pages 5
"""

import argparse
import asyncio
import sys
from urllib.parse import urlparse, parse_qs, urlencode

from playwright.async_api import async_playwright
import aiohttp
from bs4 import BeautifulSoup


async def get_item_urls(page, url: str) -> list[str]:
    """Get item detail URLs from a listing page."""
    await page.goto(url, wait_until="domcontentloaded", timeout=30000)

    try:
        await page.wait_for_selector('[data-qa-id="aditem_container"]', timeout=10000)
    except:
        return []

    await asyncio.sleep(0.5)

    urls = await page.evaluate("""() => {
        const urls = new Set();
        document.querySelectorAll('[data-qa-id="aditem_container"]').forEach(container => {
            const link = container.querySelector('a[href*="/ad/"]');
            if (link && link.href) {
                urls.add(link.href);
            }
        });
        return Array.from(urls);
    }""")

    return urls or []


def get_page_url(base_url: str, page_num: int) -> str:
    """Generate URL for a specific page number."""
    parsed = urlparse(base_url)
    params = parse_qs(parsed.query)
    params["page"] = [str(page_num)]
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}?{urlencode(params, doseq=True)}"


async def scrape_raw(url: str, pages: int, rate_limit: int = 10) -> list[str]:
    """Scrape using aiohttp (no browser). May be blocked by bot protection."""
    all_urls = []
    semaphore = asyncio.Semaphore(rate_limit)

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
    }

    async def fetch_page(session, page_url: str) -> list[str]:
        async with semaphore:
            try:
                async with session.get(
                    page_url, headers=headers, timeout=aiohttp.ClientTimeout(total=30)
                ) as resp:
                    if resp.status != 200:
                        sys.stderr.write(f"HTTP {resp.status}\n")
                        return []
                    html = await resp.text()
                    return parse_urls(html)
            except Exception as e:
                sys.stderr.write(f"Error: {e}\n")
                return []

    def parse_urls(html: str) -> list[str]:
        soup = BeautifulSoup(html, "html.parser")
        urls = []
        for a in soup.select('[data-qa-id="aditem_container"] a'):
            href = a.get("href", "")
            if "/ad/" in href:
                if href.startswith("/"):
                    href = f"https://www.leboncoin.fr{href}"
                urls.append(href)
        return urls

    async with aiohttp.ClientSession() as session:
        tasks = []
        for page_num in range(1, pages + 1):
            page_url = get_page_url(url, page_num)
            sys.stderr.write(f"Page {page_num}... ")
            tasks.append(fetch_page(session, page_url))

        results = await asyncio.gather(*tasks)

        for i, urls in enumerate(results, 1):
            new_urls = [u for u in urls if u not in all_urls]
            all_urls.extend(new_urls)
            sys.stderr.write(f"{len(new_urls)} URLs\n")

    return all_urls


async def scrape(url: str, pages: int, cdp: bool = False) -> list[str]:
    """Scrape multiple pages and return all item URLs."""
    all_urls = []

    async with async_playwright() as p:
        if cdp:
            browser = await p.chromium.connect_over_cdp("http://localhost:9222")
            context = browser.contexts[0]
            page = context.pages[0] if context.pages else await context.new_page()
        else:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                locale="fr-FR",
            )
            page = await context.new_page()

        try:
            for page_num in range(1, pages + 1):
                page_url = get_page_url(url, page_num)
                sys.stderr.write(f"Page {page_num}... ")

                try:
                    urls = await get_item_urls(page, page_url)
                    new_urls = [u for u in urls if u not in all_urls]
                    all_urls.extend(new_urls)
                    sys.stderr.write(f"{len(new_urls)} URLs\n")

                    if not new_urls:
                        break
                except Exception as e:
                    sys.stderr.write(f"Error: {e}\n")

                if page_num < pages:
                    await asyncio.sleep(1)
        finally:
            if not cdp:
                await browser.close()

    return all_urls


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("url", help="Leboncoin search URL")
    parser.add_argument(
        "--pages", "-p", type=int, default=1, help="Pages to scrape (default: 1)"
    )
    parser.add_argument(
        "--playwright",
        action="store_true",
        help="Use browser (if raw request is blocked)",
    )
    parser.add_argument(
        "--cdp",
        action="store_true",
        help="Connect to existing Chrome on port 9222",
    )
    args = parser.parse_args()

    if args.playwright or args.cdp:
        urls = await scrape(args.url, args.pages, cdp=args.cdp)
    else:
        urls = await scrape_raw(args.url, args.pages)

    for url in urls:
        print(url)


if __name__ == "__main__":
    asyncio.run(main())

