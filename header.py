from asyncio import create_subprocess_exec, run
from json import loads, dumps
from httpx import AsyncClient, Timeout
from time import perf_counter
from os import devnull
import aiofiles
import socketserver

# Script config
start_line = 0
first_test = "x.com"
list_file="./List_1.txt"
result_filename = "./result.csv"
get_timeout = 1.0
connect_timeout = 1.0

result_filename = "./result.csv"
async def configer(domain, port):
    async with aiofiles.open("./main.json", "rt") as main_config_file:
        main_config = loads(await main_config_file.read())
    main_config["outbounds"][0]["streamSettings"]["tcpSettings"]["header"]["request"]["headers"]["Host"] = domain
    main_config["inbounds"][0]["port"] = port # Add free port to socks protocol
    main_config["inbounds"][1]["port"] = port + 1 # Add different port to http protocol
    async with aiofiles.open("./config.json", "wt") as config_file:
        await config_file.write(dumps(main_config))

def get_free_port() -> int:
    """returns a free port"""
    with socketserver.TCPServer(("localhost", 0), None) as s:
        return s.server_address[1]

async def main(start_line=0):
    scanned_count = start_line
    port = get_free_port()
    # Prestart test with first_test
    try:
        await configer(first_test, port)
        xray = await create_subprocess_exec(
            "./xray.exe",
            stdout=open(devnull, 'wb'),
            stderr=open(devnull, 'wb')
        )
        async with AsyncClient(proxy=f'socks5://127.0.0.1:{port}', timeout=Timeout(get_timeout, connect=connect_timeout)) as client:
            stime = perf_counter()
            req = await client.get(url="https://www.gstatic.com/generate_204")
            etime = perf_counter()
            if req.status_code == 204 or req.status_code == 200:
                latency = etime - stime
                print(f"Prestart test {first_test}: {int(latency * 1000)} ms")
    except Exception as e:
        print(f"Prestart test {first_test} failed: {e}")
    finally:
        xray.terminate()
        await xray.wait()

    async with aiofiles.open(list_file, "rt") as domains_file:
        domains = (await domains_file.read()).splitlines()
    async with aiofiles.open(result_filename, "a+") as result_file:
        if await result_file.tell() == 0:
            await result_file.write("Domain,Delay\r")
    for domain in domains[start_line:]:
        # generate config file
        try:
            await configer(domain.strip(),port)
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

run(main(start_line))
