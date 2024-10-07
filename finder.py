import requests
import time
from requests.exceptions import Timeout, ConnectionError

# File paths
domain_list = "domain_list.txt"
save_to = "sub_list.txt"

def retry_request(url, retries=3, delay=3, timeout=10):
    for attempt in range(retries):
        try:
            response = requests.get(url, timeout=timeout)
            if response.status_code == 200:
                return response
            elif response.status_code == 429:
                print(f"Rate limit exceeded for {url}. Retrying after {delay * 2} seconds...")
                time.sleep(delay * 2)  # Longer wait for rate limit
            else:
                print(f"Failed to fetch data from {url}, status code: {response.status_code}")
        except Timeout:
            print(f"Attempt {attempt + 1} - Timeout occurred for {url}. Retrying...")
        except ConnectionError:
            print(f"Attempt {attempt + 1} - Connection error occurred for {url}. Retrying...")
        except requests.RequestException as e:
            print(f"Attempt {attempt + 1} - An error occurred: {e}")
        time.sleep(delay)  # Wait before retrying
    return None

def get_crtsh_subdomains(domain):
    url = f"https://crt.sh/?q=%25.{domain}&output=json"
    response = retry_request(url)
    if response:
        try:
            data = response.json()
            if not isinstance(data, list):
                print(f"Unexpected data format for crt.sh response for {domain}")
                return set()
            subdomains = set()
            for entry in data:
                names = entry["name_value"].split('\n')
                subdomains.update(names)
            return subdomains
        except ValueError:
            print(f"Failed to decode JSON from response for {domain}. Response content: {response.text[:100]}...")
    return set()

def get_alienvault_subdomains(domain):
    url = f'https://otx.alienvault.com/api/v1/indicators/domain/{domain}/passive_dns'
    response = retry_request(url)
    if response:
        try:
            data = response.json()
            passive_dns = data.get('passive_dns', [])
            subdomains = {record.get('hostname') for record in passive_dns if record.get('hostname')}
            return subdomains
        except ValueError:
            print(f"Failed to decode JSON from response for {domain}. Response content: {response.text[:100]}...")
    return set()

def main():
    try:
        with open(domain_list, 'r') as domain_file:
            domains = [line.strip() for line in domain_file]

        if not domains:
            print("No domains to process. Please check your domain_list.txt file.")
            return

        all_subdomains = set()
        for domain in domains:
            print(f"Fetching subdomains for {domain}...")
            crtsh_subdomains = get_crtsh_subdomains(domain)
            alienvault_subdomains = get_alienvault_subdomains(domain)
            combined_subdomains = crtsh_subdomains.union(alienvault_subdomains)
            all_subdomains.update(combined_subdomains)
            print(f"Found {len(combined_subdomains)} subdomains for {domain}")
            time.sleep(1)  # Sleep to avoid making requests too quickly

        try:
            with open(save_to, 'w') as sub_file:
                for subdomain in sorted(all_subdomains):
                    sub_file.write(subdomain + "\n")
        except IOError as e:
            print(f"Failed to write to {save_to}: {e}")

        print("Subdomains saved to sub_list.txt")
        print(f"Total subdomains found: {len(all_subdomains)}")

    except KeyboardInterrupt:
        print("\nProcess interrupted by user. Exiting...")

if __name__ == "__main__":
    main()
