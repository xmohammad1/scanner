import aiofiles
import httpx
import asyncio

# File paths
domain_list = "./domain_list.txt"
save_to = "./sub_list.txt"

async def retry_request(url, retries=8, delay=3, timeout=10):
    async with httpx.AsyncClient() as client:
        for attempt in range(1, retries + 1):
            try:
                response = await client.get(url, timeout=timeout)
                if response.status_code == 200:
                    return response
                else:
                    await asyncio.sleep(delay * 2)
            except (httpx.TimeoutException, httpx.ConnectError, httpx.RequestError, httpx.TransportError) as e:
                print(f"Attempt {attempt} - Error occurred for {url}: {e}. Retrying in {delay} seconds...")
                await asyncio.sleep(delay)
                continue  # Continue the retry loop
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
        # Read domains from domain_list.txt
        async with aiofiles.open(domain_list, 'r') as domain_file:
            domains = [line.strip() for line in await domain_file.readlines()]

        if not domains:
            print("No domains to process. Please check your domain_list.txt file.")
            return
        # Read existing subdomains from sub_list.txt
        try:
            async with aiofiles.open(save_to, 'r') as sub_file:
                existing_subdomains = set(line.strip() for line in await sub_file.readlines())
        except FileNotFoundError:
            existing_subdomains = set()

        for domain in domains:
            print(f"Fetching subdomains for {domain}...")
            combined_subdomains = await fetch_subdomains(domain)
            new_subdomains = set()
            for subdomain in combined_subdomains:
                subdomain = subdomain.lstrip("*.").lower()
                if subdomain not in existing_subdomains:
                    new_subdomains.add(subdomain)
                    existing_subdomains.add(subdomain)  # Update the set to prevent duplicates in the same run
                    # Write the new subdomain to the file immediately
                    async with aiofiles.open(save_to, 'a') as sub_file:
                        await sub_file.write(subdomain + "\n")

            print(f"Found {len(combined_subdomains)} subdomains for {domain}, {len(new_subdomains)} new.")
            await asyncio.sleep(1)  # Sleep to avoid making requests too quickly

        print("Subdomains saved to sub_list.txt")

    except KeyboardInterrupt:
        print("\nProcess interrupted by user. Exiting...")

if __name__ == "__main__":
    asyncio.run(main())
