from subprocess import Popen, DEVNULL
from json import loads, dumps
from httpx import Client, Timeout
from time import perf_counter, sleep
import copy
from os import makedirs
import shutil, os, socket, socketserver, threading, platform
from concurrent.futures import ThreadPoolExecutor, as_completed


# Script configuration
start_line = 0                   # The starting line number in the domain list file from which to begin scanning
first_test = "google.com"        # Domain used for an PreStart test to verify setup
list_file = "./List_1.txt"        # File that contains the list of domains to be scanned
result_filename = "./result.csv" # File where scan results will be stored
get_timeout = 1.0                # Timeout duration (in seconds) for GET requests
connect_timeout = 2.0            # Timeout duration (in seconds) for connection attempts
threads = 4                     # Number of threads to use for scanning domains
Main_config_name = "./main.json"
# Auto-detect operating system and set appropriate xray executable name
if platform.system() == "Windows":
    xray_file_name = "./xray.exe"
else:  # Linux/Unix systems including Ubuntu
    xray_file_name = "./xray"

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
def make_xray_executable():
    """Make xray file executable on Linux/Unix systems"""
    if platform.system() != "Windows":
        try:
            os.chmod(xray_file_name, 0o755)
            thread_safe_print(f"Made {xray_file_name} executable")
        except Exception as e:
            thread_safe_print(f"Warning: Could not make {xray_file_name} executable: {e}")
make_xray_executable()
try:
    shutil.rmtree('./configs', ignore_errors=True)
    makedirs('./configs', exist_ok=True)
except Exception as e:
    thread_safe_print(f"Error preparing config directory: {e}")

def load_main_config():
    try:
        with open(Main_config_name, "r", encoding="utf-8") as main_config_file:
            return loads(main_config_file.read())
    except FileNotFoundError:
        thread_safe_print(f"Error: {Main_config_name} not found!")
    except Exception as e:
        thread_safe_print(f"Error reading config file: {e}")
    return None


def configer(domain, port_socks, port_http, config_index, base_config):
    if base_config is None:
        return None
    main_config = copy.deepcopy(base_config)
    main_config["outbounds"][0]["streamSettings"]["tcpSettings"]["header"]["request"]["headers"]["Host"] = domain
    main_config["inbounds"][0]["port"] = port_socks
    main_config["inbounds"][1]["port"] = port_http
    config_filename = f"./configs/config{config_index}.json"
    try:
        with open(config_filename, "w") as config_file:
            config_file.write(dumps(main_config, indent=2))
    except Exception as e:
        thread_safe_print(f"Error writing config file: {e}")
        return None
    return config_filename

def get_unique_ports():
    max_attempts = 10
    attempts = 0
    while attempts < max_attempts:
        try:
            port_socks = get_free_port()
            port_http = get_free_port()
            if port_socks != port_http:
                return port_socks, port_http
        except Exception as e:
            thread_safe_print(f"Error getting unique ports: {e}")
        attempts += 1
    raise Exception("Could not find unique ports after multiple attempts")

def get_free_port() -> int:
    try:
        with socketserver.TCPServer(("localhost", 0), None) as s:
            return s.server_address[1]
    except Exception as e:
        thread_safe_print(f"Error getting free port: {e}")
        raise


def wait_for_port(port, host="127.0.0.1", timeout=5.0):
    """Block until a TCP port on the given host starts accepting connections."""
    deadline = perf_counter() + timeout
    while perf_counter() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return
        except OSError:
            sleep(0.05)
    raise TimeoutError(f"Timeout waiting for port {port}")


def terminate_process(process):
    """Safely terminate a process"""
    if process and process.poll() is None:
        try:
            process.terminate()
            # Give process time to terminate gracefully
            try:
                process.wait(timeout=2)
            except:
                # Force kill if terminate doesn't work
                process.kill()
                process.wait()
        except (ProcessLookupError, OSError):
            # Process already terminated
            pass
def scan_domain(domain, scanned_count, config_index, base_config):
    try:
        port_socks, port_http = get_unique_ports()
    except Exception as e:
        thread_safe_print(f"{scanned_count}. {domain}, failed to acquire ports: {e}")
        return

    config_filename = configer(domain.strip(), port_socks, port_http, config_index, base_config)
    if not config_filename:
        return

    xray = None
    try:
        xray = Popen([xray_file_name, "-c", config_filename], stdout=DEVNULL, stderr=DEVNULL)
        wait_for_port(port_socks)
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
        thread_safe_print(f"{scanned_count}. {domain}, Error: {e}")
    finally:
        terminate_process(xray)

def main(start_line=0):
    scanned_count = start_line
    if not is_file_writable(result_filename):
        print(f"Error: Cannot write to {result_filename}. The file may be opened by another program. Please close it and try again.")
        exit()

    base_config = load_main_config()
    if base_config is None:
        return

    try:
        port_socks, port_http = get_unique_ports()
    except Exception as e:
        thread_safe_print(f"Error obtaining initial ports: {e}")
        return
    xray = None

    # Prestart test
    try:
        config_filename = configer(first_test, port_socks, port_http, "prestart", base_config)
        if not config_filename:
            thread_safe_print(f"Prestart test {first_test} failed: config error")
            return
        xray = Popen([xray_file_name, "-c", config_filename], stdout=DEVNULL, stderr=DEVNULL)
        wait_for_port(port_socks)
        with Client(proxy=f'socks5://127.0.0.1:{port_socks}',
                    timeout=Timeout(get_timeout, connect=connect_timeout)) as client:
            stime = perf_counter()
            req = client.get(url="https://www.google.com/generate_204")
            etime = perf_counter()
            if req.status_code in [200, 204]:
                latency = etime - stime
                thread_safe_print(f"Prestart test {first_test}: {int(latency * 1000)} ms")
    except Exception as e:
        thread_safe_print(f"Prestart test {first_test} failed: {e}")
    finally:
        terminate_process(xray)

    try:
        with open(list_file, "r", encoding="utf-8") as domains_file:
            domains = domains_file.read().splitlines()
    except FileNotFoundError:
        thread_safe_print(f"Error: Domain list file {list_file} not found.")
        return
    except Exception as e:
        thread_safe_print(f"Error reading domain list file: {e}")
        return

    if not os.path.exists(result_filename) or os.path.getsize(result_filename) == 0:
        try:
            with open(result_filename, "a+") as result_file:
                result_file.write("Domain,Delay\n")
        except Exception as e:
            thread_safe_print(f"Error initializing result file: {e}")
            return

    with ThreadPoolExecutor(max_workers=threads) as executor:
        futures = [
            executor.submit(scan_domain, domain, scanned_count + i, i, base_config)
            for i, domain in enumerate(domains[start_line:])
        ]
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                thread_safe_print(f"Error scanning domain: {e}")

if __name__ == "__main__":
    main(start_line)
