import requests
import time

domain_list = "domain_list.txt"
save_to = "sub_list.txt"

def get_crtsh_subdomains(domain):
    url = f"https://crt.sh/?q=%25.{domain}&output=json"
    for attempt in range(3):
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                try:
                    data = response.json()
                except ValueError:
                    print(f"Failed to decode JSON from response for {domain}. Response content: {response.text[:100]}...")
                    continue
                subdomains = set()
                for entry in data:
                    names = entry["name_value"].split('\n')
                    subdomains.update(names)
                return subdomains
            else:
                print(f"Failed to fetch data from crt.sh for {domain}, status code: {response.status_code}")
        except requests.RequestException as e:
            print(f"Attempt {attempt + 1} - An error occurred with crt.sh: {e}")
        time.sleep(3)  # Wait before retrying
    return set()

def get_alienvault_subdomains(domain):
    url = f'https://otx.alienvault.com/api/v1/indicators/domain/{domain}/passive_dns'
    for attempt in range(3):
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                try:
                    data = response.json()
                except ValueError:
                    print(f"Failed to decode JSON from response for {domain}. Response content: {response.text[:100]}...")
                    continue
                passive_dns = data.get('passive_dns', [])
                subdomains = {record.get('hostname') for record in passive_dns if record.get('hostname')}
                return subdomains
            else:
                print(f"Failed to fetch data from AlienVault for {domain}, status code: {response.status_code}")
        except requests.RequestException as e:
            print(f"Attempt {attempt + 1} - An error occurred with AlienVault: {e}")
        time.sleep(3)  # Wait before retrying
    return set()

def main():
    with open(domain_list, 'r') as domain_file:
        domains = [line.strip() for line in domain_file]

    all_subdomains = set()
    for domain in domains:
        print(f"Fetching subdomains for {domain}...")
        crtsh_subdomains = get_crtsh_subdomains(domain)
        alienvault_subdomains = get_alienvault_subdomains(domain)
        combined_subdomains = crtsh_subdomains.union(alienvault_subdomains)
        all_subdomains.update(combined_subdomains)
        print(f"Found {len(combined_subdomains)} subdomains for {domain}")
        time.sleep(1)  # Sleep to avoid making requests too quickly

    with open(save_to, 'w') as sub_file:
        for subdomain in sorted(all_subdomains):
            sub_file.write(subdomain + "\n")

    print("Subdomains saved to sub_list.txt")
    print(f"Total subdomains found: {len(all_subdomains)}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nProcess interrupted by user. Exiting...")
