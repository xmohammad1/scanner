from subprocess import Popen, DEVNULL
from json import loads, dumps
from httpx import Client, Timeout
from time import perf_counter
from os import makedirs
import shutil, os, socketserver, threading
from concurrent.futures import ThreadPoolExecutor, as_completed


# Script configuration
start_line = 0                   # The starting line number in the domain list file from which to begin scanning
first_test = "x.com"             # Domain used for an PreStart test to verify setup
list_file = "./List_1.txt"       # File that contains the list of domains to be scanned
result_filename = "./result.csv" # File where scan results will be stored
get_timeout = 1.0                # Timeout duration (in seconds) for GET requests
connect_timeout = 3.0            # Timeout duration (in seconds) for connection attempts
threads = 10                     # Number of threads to use for scanning domains


# Lock for thread-safe printing to the console and result file
write_lock, print_lock = threading.Lock(), threading.Lock()
# Function for thread-safe printing
def thread_safe_print(*args, **kwargs):
    with print_lock:
        print(*args, **kwargs)
# Function to check if the result file is writable
def is_file_writable(filename):
    try:
        with open(filename, 'a') as f:
            f.write("")
        return True
    except IOError:
        return False
# Clean up existing configuration directory and create a new one
# This ensures that each run starts with a fresh set of configuration files
shutil.rmtree('./configs', ignore_errors=True)
makedirs('./configs')

def configer(domain, port_socks, port_http, config_index):
    # Read the base configuration template
    with open("./main.json", "rt") as main_config_file:
        main_config = loads(main_config_file.read())
    # Update configuration with specific domain and ports
    main_config["outbounds"][0]["streamSettings"]["tcpSettings"]["header"]["request"]["headers"]["Host"] = domain
    main_config["inbounds"][0]["port"] = port_socks
    main_config["inbounds"][1]["port"] = port_http
    # Write updated configuration to a new file
    config_filename = f"./configs/config{config_index}.json"
    with open(config_filename, "wt") as config_file:
        config_file.write(dumps(main_config))
    return config_filename

def get_unique_ports():
    # Generates two unique port numbers to be used for SOCKS and HTTP proxies
    while True:
        port_socks = get_free_port()
        port_http = get_free_port()
        if port_socks != port_http:
            return port_socks, port_http

def get_free_port() -> int:
    # return A free port number that is not currently in use
    with socketserver.TCPServer(("localhost", 0), None) as s:
        return s.server_address[1]

def scan_domain(domain, scanned_count, config_index):
    # Generate unique ports for this scan
    port_socks, port_http = get_unique_ports()
    try:
        # Create a configuration file for xray
        config_filename = configer(domain.strip(), port_socks, port_http, config_index)
    except Exception as e:
        thread_safe_print(f"Error configuring domain {domain}: {e}")
        return
    # Run xray with the generated configuration
    xray = Popen(["./xray.exe", "-c", config_filename], stdout=DEVNULL, stderr=DEVNULL)
    try:
        # Create an HTTP client that uses the xray SOCKS proxy
        with Client(proxies=f'socks5://127.0.0.1:{port_socks}', timeout=Timeout(get_timeout, connect=connect_timeout)) as client:
            # Measure latency for the GET request
            stime = perf_counter()
            req = client.get(url="https://www.gstatic.com/generate_204")
            etime = perf_counter()
            # Check response and record latency if successful
            if req.status_code in [200, 204]:
                latency = etime - stime
                # Write the result to the output file
                with write_lock:
                    with open(result_filename, "a") as result_file:
                        result_file.write(f"{domain},{int(latency * 1000)}\n")
                thread_safe_print(f"{scanned_count}. {domain}: {int(latency * 1000)} ms")
    except Exception as e:
        # Handle timeout or other errors
        thread_safe_print(f"{scanned_count}. {domain}, TimeOut")
    finally:
        # Ensure that the xray process is terminated to free resources
        if xray.poll() is None:
            try:
                xray.terminate()
                xray.wait()
            except ProcessLookupError:
                thread_safe_print(f"Process for domain {domain} already terminated.")

def main(start_line=0):
    scanned_count = start_line
    # Check if the result file is writable
    if not is_file_writable(result_filename):
        print(f"Error: Cannot write to {result_filename}. The file may be opened by another program. Please close it and try again.")
        exit()
    # Generate ports for the initial test
    port_socks, port_http = get_unique_ports()
    xray = None

    # Perform an initial test to verify that xray and proxy configuration are working correctly
    try:
        config_filename = configer(first_test, port_socks, port_http, "prestart")
        xray = Popen(["./xray.exe", "-c", config_filename], stdout=DEVNULL, stderr=DEVNULL)
        with Client(proxies=f'socks5://127.0.0.1:{port_socks}', timeout=Timeout(get_timeout, connect=connect_timeout)) as client:
            stime = perf_counter()
            req = client.get(url="https://www.gstatic.com/generate_204")
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

    # Read domains from the input file
    with open(list_file, "rt") as domains_file:
        domains = domains_file.read().splitlines()

    # Initialize result file if it does not exist or is empty
    if not os.path.exists(result_filename) or os.path.getsize(result_filename) == 0:
        with open(result_filename, "a+") as result_file:
            result_file.write("Domain,Delay\r")

    # Start scanning domains using a thread pool for concurrent execution
    with ThreadPoolExecutor(max_workers=threads) as executor:
        futures = [executor.submit(scan_domain, domain, scanned_count + i, i) for i, domain in enumerate(domains[start_line:])]
        for future in as_completed(futures):
            future.result()

if __name__ == "__main__":
    main(start_line)
