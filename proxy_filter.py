#!/usr/bin/env python3

import asyncio
import aiohttp
import pandas as pd
import time

CSV_URL = (
    "https://raw.githubusercontent.com/"
    "proxifly/free-proxy-list/main/"
    "proxies/protocols/http/data.csv"
)

CONCURRENCY = 200
TIMEOUT = 8

IP_CHECK = "https://httpbin.org/ip"
HEADER_CHECK = "https://httpbin.org/headers"


async def test_proxy(session, proxy):
    proxy_url = f"http://{proxy['ip']}:{proxy['port']}"

    try:
        start = time.perf_counter()

        async with session.get(
            IP_CHECK,
            proxy=proxy_url,
            timeout=TIMEOUT,
        ) as r:

            if r.status != 200:
                return None

            await r.text()

        async with session.get(
            HEADER_CHECK,
            proxy=proxy_url,
            timeout=TIMEOUT,
        ) as r:

            if r.status != 200:
                return None

            data = await r.json()

        latency = round(time.perf_counter() - start, 2)

        headers = {
            k.lower(): v
            for k, v in data.get("headers", {}).items()
        }

        leaked = any(
            h in headers
            for h in (
                "x-forwarded-for",
                "forwarded",
                "via",
                "proxy-connection"
            )
        )

        score = 100

        if leaked:
            score -= 50

        if latency < 1:
            score += 25
        elif latency < 3:
            score += 10

        return {
            "ip": proxy["ip"],
            "port": proxy["port"],
            "latency": latency,
            "leaked_headers": leaked,
            "score": score
        }

    except Exception:
        return None


async def worker(proxies):
    connector = aiohttp.TCPConnector(
        limit=CONCURRENCY,
        ssl=False
    )

    async with aiohttp.ClientSession(
        connector=connector
    ) as session:

        tasks = [
            test_proxy(session, proxy)
            for proxy in proxies
        ]

        results = []

        completed = 0

        for coro in asyncio.as_completed(tasks):

            result = await coro
            completed += 1

            if result:
                results.append(result)

            if completed % 50 == 0:
                print(
                    f"Checked {completed}/{len(proxies)} "
                    f"Working={len(results)}"
                )

        return results


async def main():

    print("Downloading proxy list...")

    df = pd.read_csv(CSV_URL)

    print(f"Total proxies: {len(df)}")

    if "anonymity" in df.columns:
        df = df[
            df["anonymity"]
            .astype(str)
            .str.lower()
            .eq("elite")
        ]

    print(f"Elite proxies: {len(df)}")

    proxies = df.to_dict("records")

    results = await worker(proxies)

    out = pd.DataFrame(results)

    if len(out):

        out = out.sort_values(
            by=["score", "latency"],
            ascending=[False, True]
        )

        out.to_csv(
            "trusted_proxies.csv",
            index=False
        )

    print(
        f"Saved {len(out)} proxies "
        f"to trusted_proxies.csv"
    )


if __name__ == "__main__":
    asyncio.run(main())
