import aiofiles
import httpx
import asyncio
from httpx import TimeoutException, ConnectError

# File paths
domain_list = "./Hiddify.txt"
save_to = "./sub_list.txt"

async def retry_request(url, retries=3, delay=3, timeout=10):
    async with httpx.AsyncClient() as client:
        for attempt in range(retries):
            try:
                response = await client.get(url, timeout=timeout)
                if response.status_code == 200:
                    return response
                elif response.status_code == 429:
                    print(f"Rate limit exceeded for {url}. Retrying after {delay * 2} seconds...")
                    await asyncio.sleep(delay * 2)  # Longer wait for rate limit
                else:
                    print(f"Failed to fetch data from {url}, status code: {response.status_code}")
            except TimeoutException:
                print(f"Attempt {attempt + 1} - Timeout occurred for {url}. Retrying...")
            except ConnectError:
                print(f"Attempt {attempt + 1} - Connection error occurred for {url}. Retrying...")
            except httpx.RequestError as e:
                print(f"Attempt {attempt + 1} - An error occurred: {e}")
            await asyncio.sleep(delay)  # Wait before retrying
    return None

async def get_crtsh_subdomains(domain):
    url = f"https://crt.sh/?q=%25.{domain}&output=json"
    response = await retry_request(url)
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

async def get_alienvault_subdomains(domain):
    url = f'https://otx.alienvault.com/api/v1/indicators/domain/{domain}/passive_dns'
    response = await retry_request(url)
    if response:
        try:
            data = response.json()
            passive_dns = data.get('passive_dns', [])
            subdomains = {record.get('hostname') for record in passive_dns if record.get('hostname')}
            return subdomains
        except ValueError:
            print(f"Failed to decode JSON from response for {domain}. Response content: {response.text[:100]}...")
    return set()

async def fetch_subdomains(domain):
    crtsh_subdomains = await get_crtsh_subdomains(domain)
    alienvault_subdomains = await get_alienvault_subdomains(domain)
    return crtsh_subdomains.union(alienvault_subdomains)

async def main():
    try:
        async with aiofiles.open(domain_list, 'r') as domain_file:
            domains = [line.strip() for line in await domain_file.readlines()]

        if not domains:
            print("No domains to process. Please check your domain_list.txt file.")
            return

        all_subdomains = set()

        for domain in domains:
            print(f"Fetching subdomains for {domain}...")
            combined_subdomains = await fetch_subdomains(domain)

            # Write to the file in append mode to ensure data is saved incrementally
            async with aiofiles.open(save_to, 'a') as sub_file:
                for subdomain in sorted(combined_subdomains):
                    if subdomain not in all_subdomains:  # Avoid duplicates in output
                        await sub_file.write(subdomain + "\n")

            all_subdomains.update(combined_subdomains)
            print(f"Found {len(combined_subdomains)} subdomains for {domain}")
            await asyncio.sleep(1)  # Sleep to avoid making requests too quickly

        print("Subdomains saved to sub_list.txt")

    except KeyboardInterrupt:
        print("\nProcess interrupted by user. Exiting...")

if __name__ == "__main__":
    asyncio.run(main())
