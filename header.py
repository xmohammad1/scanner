from asyncio import create_subprocess_exec, run, sleep
from json import loads, dumps
from os import devnull
from os.path import isfile
from httpx import AsyncClient, Timeout
from time import perf_counter

# Script config
get_timeout = 1.0
connect_timeout = 1.0

def configer(domain):
    main_config = loads(open("./main.json", "rt").read())
    main_config["outbounds"][0]["streamSettings"]["tcpSettings"]["header"]["request"]["headers"]["Host"] = domain
    open("./config.json", "wt").write(dumps(main_config))


def findport() -> int:
    with open("./main.json", "rt") as config_file:
        for inbound in loads(config_file.read())["inbounds"]:
            if inbound["protocol"] == "socks":
                return inbound["port"]

    raise "Socks inbound required!"


async def main():
    port = findport()
    domains = open("./List_1.txt", "rt").read().split("\n")

    if isfile("./result.csv"):
        result = open("./result.csv", "at")
    else:
        result = open("./result.csv", "at")
        result.write("Domain,Delay\r")

    for domain in domains:
        # generate config file
        try:
            configer(domain.strip())
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
                    result.write(f"{domain},{int(latency * 1000)}\n")
                    print(f"{domain}: {int(latency * 1000)}")
        except:  # noqa: E722
            print(f"{domain},Timeout")

        # kill the xray
        xray.terminate()
        xray.kill()

        await sleep(0.1)


run(main())
