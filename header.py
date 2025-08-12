from subprocess import Popen, DEVNULL
from json import loads, dumps
from httpx import Client, Timeout
from time import perf_counter
from os import makedirs
import shutil, os, socketserver, threading
from concurrent.futures import ThreadPoolExecutor, as_completed


# Script configuration
start_line = 0                   # The starting line number in the domain list file from which to begin scanning
first_test = "google.com"        # Domain used for an PreStart test to verify setup
list_file = "./List_1.txt"        # File that contains the list of domains to be scanned
result_filename = "./result.csv" # File where scan results will be stored
get_timeout = 1.0                # Timeout duration (in seconds) for GET requests
connect_timeout = 2.0            # Timeout duration (in seconds) for connection attempts
threads = 1                     # Number of threads to use for scanning domains
Main_config_name = "./main.json"
xray_file_name = "./xray.exe"

# Lock for thread-safe printing to the console and result file
write_lock, print_lock = threading.Lock(), threading.Lock()

def thread_safe_print(*args, **kwargs):
    with print_lock:
        print(*args, **kwargs)

def is_file_writable(filename):
    try:
        with open(filename, 'a') as f:
            f.write("")
        return True
    except IOError:
        return False

shutil.rmtree('./configs', ignore_errors=True)
makedirs('./configs')

def configer(domain, port_socks, port_http, config_index):
    try:
        with open(Main_config_name, "r", encoding="utf-8") as main_config_file:
            main_config = loads(main_config_file.read())
    except FileNotFoundError:
        thread_safe_print(f"Error: {Main_config_name} not found!")
        return None
    except Exception as e:
        thread_safe_print(f"Error reading config file: {e}")
        return None
    main_config["outbounds"][0]["streamSettings"]["tcpSettings"]["header"]["request"]["headers"]["Host"] = domain
    main_config["inbounds"][0]["port"] = port_socks
    main_config["inbounds"][1]["port"] = port_http
    config_filename = f"./configs/config{config_index}.json"
    try:
        with open(config_filename, "wt") as config_file:
            config_file.write(dumps(main_config, indent=2))
    except Exception as e:
        thread_safe_print(f"Error writing config file: {e}")
        return None
    return config_filename

def get_unique_ports():
    while True:
        port_socks = get_free_port()
        port_http = get_free_port()
        if port_socks != port_http:
            return port_socks, port_http

def get_free_port() -> int:
    try:
        with socketserver.TCPServer(("localhost", 0), None) as s:
            return s.server_address[1]
    except Exception as e:
        thread_safe_print(f"Error getting free port: {e}")
        raise

def scan_domain(domain, scanned_count, config_index):
    port_socks, port_http = get_unique_ports()
    try:
        config_filename = configer(domain.strip(), port_socks, port_http, config_index)
    except Exception as e:
        thread_safe_print(f"Error configuring domain {domain}: {e}")
        return

    xray = Popen([xray_file_name, "-c", config_filename], stdout=DEVNULL, stderr=DEVNULL)
    try:
        with Client(proxy=f'socks5://127.0.0.1:{port_socks}',
                    timeout=Timeout(get_timeout, connect=connect_timeout)) as client:
            stime = perf_counter()
            req = client.get(url="https://www.google.com/generate_204")
            etime = perf_counter()
            if req.status_code in [200, 204]:
                latency = etime - stime
                with write_lock:
                    with open(result_filename, "a") as result_file:
                        result_file.write(f"{domain},{int(latency * 1000)}\n")
                thread_safe_print(f"{scanned_count}. {domain}: {int(latency * 1000)} ms")
    except Exception as e:
        thread_safe_print(f"{scanned_count}. {domain}, TimeOut")
    finally:
        if xray.poll() is None:
            try:
                xray.terminate()
                xray.wait()
            except ProcessLookupError:
                thread_safe_print(f"Process for domain {domain} already terminated.")

def main(start_line=0):
    scanned_count = start_line
    if not is_file_writable(result_filename):
        print(f"Error: Cannot write to {result_filename}. The file may be opened by another program. Please close it and try again.")
        exit()

    port_socks, port_http = get_unique_ports()
    xray = None

    # Prestart test
    try:
        config_filename = configer(first_test, port_socks, port_http, "prestart")
        xray = Popen([xray_file_name, "-c", config_filename], stdout=DEVNULL, stderr=DEVNULL)
        with Client(proxy=f'socks5://127.0.0.1:{port_socks}',
                    timeout=Timeout(get_timeout, connect=connect_timeout)) as client:
            stime = perf_counter()
            req = client.get(url="https://www.google.com/generate_204")
            etime = perf_counter()
            if req.status_code in [200, 204]:
                latency = etime - stime
                thread_safe_print(f"Prestart test {first_test}: {int(latency * 1000)} ms")
    except Exception as e:
        thread_safe_print(f"Prestart test {first_test} TimeOut")
    finally:
        if xray is not None and xray.poll() is None:
            try:
                xray.terminate()
                xray.wait()
            except ProcessLookupError:
                thread_safe_print(f"Process for prestart test already terminated.")

    with open(list_file, "r", encoding="utf-8") as domains_file:
        domains = domains_file.read().splitlines()

    if not os.path.exists(result_filename) or os.path.getsize(result_filename) == 0:
        with open(result_filename, "a+") as result_file:
            result_file.write("Domain,Delay\r")

    with ThreadPoolExecutor(max_workers=threads) as executor:
        futures = [executor.submit(scan_domain, domain, scanned_count + i, i) for i, domain in enumerate(domains[start_line:])]
        for future in as_completed(futures):
            future.result()

if __name__ == "__main__":
    main(start_line)
