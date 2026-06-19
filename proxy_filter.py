#!/usr/bin/env python3

import asyncio
import aiohttp
import csv
import time

PROXY_LIST_URL = (
"https://raw.githubusercontent.com/"
"proxifly/free-proxy-list/main/"
"proxies/protocols/http/data.txt"
)

CONCURRENCY = 300
TIMEOUT = 5

IP_CHECK_URL = "https://httpbin.org/ip"
HEADERS_CHECK_URL = "https://httpbin.org/headers"

OUTPUT_FILE = "trusted_proxies.csv"

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
            IP_CHECK_URL,
            proxy=proxy_url,
            timeout=TIMEOUT,
        ) as response:

            if response.status != 200:
                return None

            await response.text()

        async with session.get(
            HEADERS_CHECK_URL,
            proxy=proxy_url,
            timeout=TIMEOUT,
        ) as response:

            if response.status != 200:
                return None

            data = await response.json()

        latency = round(
            time.perf_counter() - start,
            2
        )

        headers = {
            k.lower(): str(v)
            for k, v in data.get(
                "headers", {}
            ).items()
        }

        leaked = any(
            header in headers
            for header in (
                "via",
                "forwarded",
                "x-forwarded-for",
                "proxy-connection",
            )
        )

        score = 100

        if leaked:
            score -= 50

        if latency < 1:
            score += 25
        elif latency < 2:
            score += 15
        elif latency < 3:
            score += 10

        return {
            "proxy": proxy_url,
            "latency": latency,
            "leaked_headers": leaked,
            "score": score,
        }

    except Exception:
        return None

async def main():

proxies = await download_proxy_list()

semaphore = asyncio.Semaphore(CONCURRENCY)

connector = aiohttp.TCPConnector(
    limit=CONCURRENCY,
    ssl=False,
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
    key=lambda x: (
        x["score"],
        -x["latency"]
    ),
    reverse=True,
)

with open(
    OUTPUT_FILE,
    "w",
    newline="",
    encoding="utf-8",
) as f:

    writer = csv.DictWriter(
        f,
        fieldnames=[
            "proxy",
            "latency",
            "leaked_headers",
            "score",
        ],
    )

    writer.writeheader()

    writer.writerows(results)

print()
print(
    f"[+] Saved "
    f"{len(results)} working proxies"
)
print(
    f"[+] Output file: "
    f"{OUTPUT_FILE}"
)

if name == "main":
asyncio.run(main())
