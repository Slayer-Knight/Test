#!/usr/bin/env python3

import asyncio
import aiohttp
import time

PROXY_LIST_URL = (
    "https://raw.githubusercontent.com/"
    "proxifly/free-proxy-list/main/"
    "proxies/protocols/http/data.txt"
)

CONCURRENCY = 300
TIMEOUT = 5

TEST_URL = "https://httpbin.org/ip"

OUTPUT_FILE = "trusted_proxies.txt"


async def download_proxy_list():
    print("[+] Downloading proxy list...")

    async with aiohttp.ClientSession() as session:
        async with session.get(PROXY_LIST_URL, timeout=30) as response:
            response.raise_for_status()
            text = await response.text()

    proxies = [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]

    print(f"[+] Loaded {len(proxies)} proxies")

    return proxies


async def test_proxy(session, semaphore, proxy_url):
    async with semaphore:
        try:
            start = time.perf_counter()

            async with session.get(
                TEST_URL,
                proxy=proxy_url,
                timeout=aiohttp.ClientTimeout(total=TIMEOUT),
            ) as response:

                if response.status != 200:
                    return None

                await response.text()

            latency = round(
                time.perf_counter() - start,
                2
            )

            return {
                "proxy": proxy_url,
                "latency": latency
            }

        except Exception:
            return None


async def main():

    proxies = await download_proxy_list()

    semaphore = asyncio.Semaphore(CONCURRENCY)

    connector = aiohttp.TCPConnector(
        limit=CONCURRENCY,
        ssl=False
    )

    results = []

    async with aiohttp.ClientSession(
        connector=connector
    ) as session:

        tasks = [
            test_proxy(
                session,
                semaphore,
                proxy
            )
            for proxy in proxies
        ]

        completed = 0

        for future in asyncio.as_completed(tasks):

            result = await future
            completed += 1

            if result:
                results.append(result)

            if completed % 50 == 0:
                print(
                    f"[+] Checked "
                    f"{completed}/{len(proxies)} | "
                    f"Working={len(results)}"
                )

    results.sort(
        key=lambda x: x["latency"]
    )

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        for item in results:
            f.write(item["proxy"] + "\n")

    print()
    print(f"[+] Working proxies: {len(results)}")
    print(f"[+] Saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    asyncio.run(main())
