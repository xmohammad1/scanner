from asyncio import create_subprocess_exec, run
from json import loads, dumps
from httpx import AsyncClient, Timeout
from time import perf_counter
from os import devnull
import aiofiles

# Script config
list_file="./List_1.txt"
get_timeout = 1.0
connect_timeout = 1.0

result_filename = "./result.csv"
async def configer(domain):
    async with aiofiles.open("./main.json", "rt") as main_config_file:
        main_config = loads(await main_config_file.read())
    main_config["outbounds"][0]["streamSettings"]["tcpSettings"]["header"]["request"]["headers"]["Host"] = domain
    async with aiofiles.open("./config.json", "wt") as config_file:
        await config_file.write(dumps(main_config))

def findport() -> int:
    with open("./main.json", "rt") as config_file:
        for inbound in loads(config_file.read())["inbounds"]:
            if inbound["protocol"] == "socks":
                return inbound["port"]

    raise "Socks inbound required!"

async def main(start_line=0):
    scanned_count = start_line
    port = findport()
    domains = open("./List_1.txt", "rt").read().split("\n")

    async with aiofiles.open(list_file, "rt") as domains_file:
        domains = (await domains_file.read()).splitlines()
    async with aiofiles.open(result_filename, "a+") as result_file:
        if await result_file.tell() == 0:
            await result_file.write("Domain,Delay\r")
    for domain in domains[start_line:]:
        # generate config file
        try:
            await configer(domain.strip())
        except:  # noqa: E722
            continue

        # run xray with config
        xray = await create_subprocess_exec(
            "./xray.exe",
            stdout=open(devnull, 'wb'),
            stderr=open(devnull, 'wb')
        )

        try:
            # httpx client using proxy to xray socks
            async with AsyncClient(proxy=f'socks5://127.0.0.1:{port}', timeout=Timeout(get_timeout, connect=connect_timeout)) as client:
                stime = perf_counter()
                req = await client.get(url="https://www.gstatic.com/generate_204")
                etime = perf_counter()
                if req.status_code == 204 or req.status_code == 200:
                    latency = etime - stime
                    async with aiofiles.open(result_filename, "a") as result_file:
                        await result_file.write(f"{domain},{int(latency*1000)}\n")
                    print(f"{scanned_count}. {domain}: {int(latency * 1000)}")
        except:  # noqa: E722
            print(f"{scanned_count}. {domain},timeout")

        xray.terminate()
        await xray.wait()
        scanned_count += 1

# Set start_line to the desired line number to start from (0-based index)
start_line = 0  # For example, to start from line 1
run(main(start_line))
