#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "aiohttp",
#   "beautifulsoup4",
#   "playwright",
# ]
# ///
"""
Leboncoin item detail scraper.
Fetches item pages and extracts details as plain text.

Usage:
    uv run leboncoin_item.py "https://www.leboncoin.fr/ad/sport_plein_air/3134233040"
    uv run leboncoin_item.py url1 url2 url3
    uv run leboncoin_item.py url1 url2 --cdp  # Use existing Chrome on port 9222
"""

import argparse
import asyncio
import json
import sys

import aiohttp
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright


async def scrape_item(url: str, session: aiohttp.ClientSession, semaphore: asyncio.Semaphore) -> dict:
    """Scrape item details from a leboncoin ad page."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
    }

    async with semaphore:
        try:
            async with session.get(
                url, headers=headers, timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                if resp.status != 200:
                    sys.stderr.write(f"HTTP {resp.status} for {url}\n")
                    return {}
                
                html = await resp.text()
                soup = BeautifulSoup(html, "html.parser")
                script = soup.find("script", id="__NEXT_DATA__")
                
                if not script:
                    sys.stderr.write("Could not find __NEXT_DATA__ payload\n")
                    return {}
                
                data = json.loads(script.string)
                props = data.get("props", {}).get("pageProps", {})
                ad = props.get("ad", {})
                
                item = {"url": url}
                
                # Title
                if ad.get("subject"):
                    item["title"] = ad.get("subject")
                
                # Price
                price = ad.get("price")
                if isinstance(price, list) and len(price) > 0:
                    item["price"] = f"{price[0]} €"
                elif price is not None:
                    item["price"] = f"{price} €"
                
                # Description
                if ad.get("body"):
                    item["description"] = ad.get("body")
                
                # Location
                location = ad.get("location", {})
                city = location.get("city")
                zipcode = location.get("zipcode")
                if city and zipcode:
                    item["location"] = f"{city} {zipcode}"
                elif city:
                    item["location"] = city
                
                # Date
                item["date"] = ad.get("first_publication_date") or ad.get("index_date")
                
                # Seller
                owner = ad.get("owner", {})
                if owner.get("name"):
                    item["seller"] = owner.get("name")
                
                # Category
                if ad.get("category_name"):
                    item["category"] = ad.get("category_name")
                
                # Images
                images = ad.get("images", {}).get("urls", [])
                if images:
                    item["images"] = images[:5]
                elif ad.get("images", {}).get("urls_large"):
                    item["images"] = ad.get("images", {}).get("urls_large")[:5]
                
                return item
                
        except Exception as e:
            sys.stderr.write(f"Error scraping item {url}: {e}\n")
            return {}


async def scrape_items(urls: list[str], rate_limit: int = 5) -> list[dict]:
    """Scrape multiple items concurrently."""
    semaphore = asyncio.Semaphore(rate_limit)
    
    async with aiohttp.ClientSession() as session:
        tasks = [scrape_item(url, session, semaphore) for url in urls]
        return await asyncio.gather(*tasks)


async def scrape_item_cdp(page, url: str) -> dict:
    """Scrape item using CDP (existing Chrome)."""
    await page.goto(url, wait_until="domcontentloaded", timeout=30000)
    
    try:
        await page.wait_for_selector('script#__NEXT_DATA__', timeout=10000)
    except:
        return {}
    
    data = await page.evaluate("""() => {
        const script = document.getElementById('__NEXT_DATA__');
        if (!script) return null;
        return JSON.parse(script.textContent);
    }""")
    
    if not data:
        return {}
    
    props = data.get("props", {}).get("pageProps", {})
    ad = props.get("ad", {})
    
    item = {"url": url}
    
    # Title
    if ad.get("subject"):
        item["title"] = ad.get("subject")
    
    # Price
    price = ad.get("price")
    if isinstance(price, list) and len(price) > 0:
        item["price"] = f"{price[0]} €"
    elif price is not None:
        item["price"] = f"{price} €"
    
    # Description
    if ad.get("body"):
        item["description"] = ad.get("body")
    
    # Location
    location = ad.get("location", {})
    city = location.get("city")
    zipcode = location.get("zipcode")
    if city and zipcode:
        item["location"] = f"{city} {zipcode}"
    elif city:
        item["location"] = city
    
    # Date
    item["date"] = ad.get("first_publication_date") or ad.get("index_date")
    
    # Seller
    owner = ad.get("owner", {})
    if owner.get("name"):
        item["seller"] = owner.get("name")
    
    # Category
    if ad.get("category_name"):
        item["category"] = ad.get("category_name")
    
    # Images
    images = ad.get("images", {}).get("urls", [])
    if images:
        item["images"] = images[:5]
    elif ad.get("images", {}).get("urls_large"):
        item["images"] = ad.get("images", {}).get("urls_large")[:5]
    
    return item


async def scrape_items_cdp(urls: list[str]) -> list[dict]:
    """Scrape multiple items using CDP."""
    items = []
    
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp("http://localhost:9222")
        context = browser.contexts[0]
        page = context.pages[0] if context.pages else await context.new_page()
        
        for i, url in enumerate(urls):
            sys.stderr.write(f"Item {i+1}/{len(urls)}... ")
            try:
                item = await scrape_item_cdp(page, url)
                items.append(item)
                sys.stderr.write(f"OK ({item.get('title', 'N/A')[:40]})\n")
            except Exception as e:
                sys.stderr.write(f"Error: {e}\n")
                items.append({})
        
        # Don't close browser for CDP
        # await browser.close()
    
    return items


def format_item(item: dict) -> str:
    """Format item as plain text."""
    lines = []

    lines.append(f"Title: {item.get('title', 'N/A')}")

    if item.get("price"):
        lines.append(f"Price: {item['price']}")

    if item.get("location"):
        lines.append(f"Location: {item['location']}")

    if item.get("date"):
        lines.append(f"Date: {item['date']}")

    if item.get("seller"):
        lines.append(f"Seller: {item['seller']}")

    if item.get("category"):
        lines.append(f"Category: {item['category']}")

    if item.get("description"):
        lines.append("")
        lines.append("Description:")
        lines.append(item["description"])

    if item.get("images"):
        lines.append("")
        lines.append("Images:")
        for img in item["images"]:
            lines.append(f"  {img}")

    lines.append("")
    lines.append(f"URL: {item.get('url', 'N/A')}")

    return "\n".join(lines)


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("urls", nargs="+", help="Leboncoin ad URLs")
    parser.add_argument("--cdp", action="store_true", help="Use existing Chrome on port 9222")
    args = parser.parse_args()

    if args.cdp:
        items = await scrape_items_cdp(args.urls)
    else:
        items = await scrape_items(args.urls)

    for i, item in enumerate(items):
        if i > 0:
            print("\n---\n")
        if item:
            print(format_item(item))
        else:
            print(f"Failed to extract item data for URL")


if __name__ == "__main__":
    asyncio.run(main())
