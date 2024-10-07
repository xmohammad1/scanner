from asyncio import create_subprocess_exec, run, Semaphore, gather
from json import loads, dumps
from httpx import AsyncClient, Timeout
from time import perf_counter
from os import devnull, makedirs
import aiofiles
import socketserver
import shutil

# Script config
start_line = 0
first_test = "x.com"
list_file = "./List1.txt"
result_filename = "./result.csv"
get_timeout = 2.0
connect_timeout = 2.0
threads = 6


shutil.rmtree('./configs', ignore_errors=True)
makedirs('./configs')

async def configer(domain, port_socks, port_http, config_index):
    async with aiofiles.open("./main.json", "rt") as main_config_file:
        main_config = loads(await main_config_file.read())
    main_config["outbounds"][0]["streamSettings"]["tcpSettings"]["header"]["request"]["headers"]["Host"] = domain
    main_config["inbounds"][0]["port"] = port_socks  # Set free port for socks protocol
    main_config["inbounds"][1]["port"] = port_http   # Set different free port for http protocol
    config_filename = f"./configs/config{config_index}.json"
    async with aiofiles.open(config_filename, "wt") as config_file:
        await config_file.write(dumps(main_config))
    return config_filename

async def get_unique_ports():
    while True:
        port_socks = get_free_port()
        port_http = get_free_port()
        if port_socks != port_http:
            return port_socks, port_http

def get_free_port() -> int:
    """returns a free port"""
    with socketserver.TCPServer(("localhost", 0), None) as s:
        return s.server_address[1]

async def scan_domain(domain, scanned_count, semaphore, config_index):
    port_socks, port_http = await get_unique_ports()
    async with semaphore:
        try:
            config_filename = await configer(domain.strip(), port_socks, port_http, config_index)
        except:  # noqa: E722
            return

        # run xray with config
        xray = await create_subprocess_exec(
            "./xray.exe",
            "-c", config_filename,
            stdout=open(devnull, 'wb'),
            stderr=open(devnull, 'wb')
        )

        try:
            # httpx client using proxy to xray socks
            async with AsyncClient(proxy=f'socks5://127.0.0.1:{port_socks}', timeout=Timeout(get_timeout, connect=connect_timeout)) as client:
                stime = perf_counter()
                req = await client.get(url="https://www.gstatic.com/generate_204")
                etime = perf_counter()
                if req.status_code == 204 or req.status_code == 200:
                    latency = etime - stime
                    async with aiofiles.open(result_filename, "a") as result_file:
                        await result_file.write(f"{domain},{int(latency * 1000)}\n")
                    print(f"{scanned_count}. {domain}: {int(latency * 1000)}")
        except:  # noqa: E722
            print(f"{scanned_count}. {domain},timeout")
        finally:
            if xray.returncode is None:
                xray.terminate()
                try:
                    await xray.wait()
                except ProcessLookupError:
                    print(f"Process for domain {domain} already terminated.")

async def main(start_line=0):
    scanned_count = start_line
    semaphore = Semaphore(threads)  # Limit the number of concurrent scans
    port_socks, port_http = await get_unique_ports()
    xray = None
    try:
        config_filename = await configer(first_test, port_socks, port_http, "prestart")
        xray = await create_subprocess_exec(
            "./xray.exe",
            "-c", config_filename,
            stdout=open(devnull, 'wb'),
            stderr=open(devnull, 'wb')
        )
        async with AsyncClient(proxy=f'socks5://127.0.0.1:{port_socks}', timeout=Timeout(get_timeout, connect=connect_timeout)) as client:
            stime = perf_counter()
            req = await client.get(url="https://www.gstatic.com/generate_204")
            etime = perf_counter()
            if req.status_code == 204 or req.status_code == 200:
                latency = etime - stime
                print(f"Prestart test {first_test}: {int(latency * 1000)} ms")
    except Exception as e:
        print(f"Prestart test {first_test} failed: {e}")
    finally:
        if xray is not None and xray.returncode is None:
            xray.terminate()
            try:
                await xray.wait()
            except ProcessLookupError:
                print(f"Process for prestart test already terminated.")

    async with aiofiles.open(list_file, "rt") as domains_file:
        domains = (await domains_file.read()).splitlines()
    async with aiofiles.open(result_filename, "a+") as result_file:
        if await result_file.tell() == 0:
            await result_file.write("Domain,Delay\r")

    # Create tasks for each domain
    tasks = [scan_domain(domain, scanned_count + i, semaphore, i) for i, domain in enumerate(domains[start_line:])]
    await gather(*tasks)

run(main(start_line))
