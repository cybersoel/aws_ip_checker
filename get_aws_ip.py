import ipaddress
import requests
import json
import sys

def fetch_json(url):
    """Fetches JSON data from a given URL."""
    try:
        response = requests.get(url)
        response.raise_for_status() # Raise an HTTPError for bad responses (4xx or 5xx)
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data from {url}: {e}", file=sys.stderr)
        sys.exit(1)

def get_region_full_name(region_code, regions_data):
    """Looks up the full region name from the regions data."""
    for region in regions_data:
        if region.get('code') == region_code:
            return region.get('full_name', region_code)
    return region_code # Return code if full name not found

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 aws_ip_lookup.py <IP_ADDRESS>", file=sys.stderr)
        print("Example: python3 aws_ip_lookup.py 54.241.40.178", file=sys.stderr)
        print("Example: python3 aws_ip_lookup.py 2620:107:300f::3e35:3", file=sys.stderr)
        sys.exit(1)

    input_ip_str = sys.argv[1]

    AWS_IP_RANGES_URL = "https://ip-ranges.amazonaws.com/ip-ranges.json"
    AWS_REGIONS_URL = "https://raw.githubusercontent.com/jsonmaur/aws-regions/master/regions.json"

    print("Fetching AWS IP ranges...", file=sys.stderr)
    ip_ranges_data = fetch_json(AWS_IP_RANGES_URL)
    print("...done.", file=sys.stderr)

    print("Fetching AWS regions...", file=sys.stderr)
    regions_data = fetch_json(AWS_REGIONS_URL)
    print("...done.", file=sys.stderr)

    # Validate input IP
    try:
        ip_obj = ipaddress.ip_address(input_ip_str)
    except ValueError:
        print(f"Error: '{input_ip_str}' is not a valid IP address.", file=sys.stderr)
        sys.exit(1)

    print(f"Searching for {input_ip_str}...", file=sys.stderr)

    found = False
    result = {}

    # Combine IPv4 and IPv6 prefixes and sort for specificity
    prefixes = ip_ranges_data.get('prefixes', [])
    ipv6_prefixes = ip_ranges_data.get('ipv6_prefixes', [])

    # Sort by prefix length (longer = more specific) then by prefix string
    # Reverse to prioritize more specific (longer) matches first, like in JS example
    all_prefixes_raw = prefixes + ipv6_prefixes
    all_prefixes_sorted = sorted(
        all_prefixes_raw,
        key=lambda p: (
            ipaddress.ip_network(p.get('ip_prefix') or p.get('ipv6_prefix')).prefixlen,
            p.get('ip_prefix') or p.get('ipv6_prefix')
        ),
        reverse=True # Sort longer prefixes first
    )

    for p in all_prefixes_sorted:
        cidr_str = p.get('ip_prefix') or p.get('ipv6_prefix')
        if not cidr_str:
            continue

        try:
            network_obj = ipaddress.ip_network(cidr_str)
            if ip_obj in network_obj:
                result = {
                    "region": p.get('region'),
                    "service": p.get('service'),
                    "subnet": cidr_str,
                    "ip_version": "IPv6" if isinstance(ip_obj, ipaddress.IPv6Address) else "IPv4"
                }
                found = True
                break # Found the most specific match
        except ValueError:
            # Should not happen with valid AWS data, but good practice
            print(f"Warning: Invalid CIDR format in data: {cidr_str}", file=sys.stderr)
            continue

    if found:
        full_region_name = get_region_full_name(result['region'], regions_data)
        print("--- AWS IP Found ---")
        print(f"Region: {full_region_name}")
        print(f"Region code: {result['region']}")
        print(f"Service: {result['service']}")
        print(f"Subnet: {result['subnet']}")
    else:
        print("Not an AWS IP or not found in ranges.")

if __name__ == "__main__":
    # Ensure requests library is installed before main execution
    try:
        import requests
    except ImportError:
        print("Error: The 'requests' library is not installed.", file=sys.stderr)
        print("Please install it: pip install requests", file=sys.stderr)
        sys.exit(1)

    main()
