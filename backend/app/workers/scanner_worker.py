import asyncio
import httpx

API_URL = "http://api:8000"


async def scan():
    async with httpx.AsyncClient(timeout=60) as client:
        while True:
            try:
                print("Running automatic scan...", flush=True)

                response = await client.get(
                    f"{API_URL}/scanner/search",
                    params={"query": "SOL"},
                )

                response.raise_for_status()
                print(response.json(), flush=True)

            except Exception as error:
                print(f"Scanner error: {error}", flush=True)

            await asyncio.sleep(60)


if __name__ == "__main__":
    asyncio.run(scan())
