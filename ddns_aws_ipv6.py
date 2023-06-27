#!/usr/bin/env python3

import ipaddress
import argparse
import boto3

class Route53DDNSIPv6:
    def __init__(self, profile, zone_id, hostname):
        self.profile = profile
        self.zone_id = zone_id
        self.hostname = hostname
        self.client = self._get_route53_client()

    def _get_route53_client(self):
        # Initialize the Route 53 client using the specified AWS CLI profile
        session = boto3.Session(profile_name=self.profile)
        return session.client('route53')

    def _get_public_ipv6_addresses(self):
        # Get the IPv6 addresses from eth0 interface
        ipv6_addresses = []

        with open('/proc/net/if_inet6', 'r') as if_inet6:
            for line in if_inet6:
                parts = line.split()
                if parts[5] == 'eth0':
                    ipv6_address = parts[0]

                    if ':' in ipv6_address:
                        # IPv6 address already contains colons, use it as is
                        formatted_ipv6 = ipv6_address
                    else:
                        # Insert colons into the IPv6 address string
                        formatted_ipv6 = ':'.join(
                            ipv6_address[i:i+4] for i in range(0, len(ipv6_address), 4)
                        )

                    try:
                        ip = ipaddress.IPv6Address(formatted_ipv6)
                        if ip.is_global:
                            ipv6_addresses.append(ip)
                    except ipaddress.AddressValueError:
                        # Invalid IPv6 address
                        pass

        return ipv6_addresses

    def _get_existing_aaaa_record_values(self):
        # Get the existing "AAAA" record values from Route 53
        response = self.client.list_resource_record_sets(
            HostedZoneId=self.zone_id,
            StartRecordName=f'{self.hostname}.',
            StartRecordType='AAAA',
            MaxItems='1'
        )

        record_values = []

        if 'ResourceRecordSets' in response:
            record_set = response['ResourceRecordSets'][0]
            if record_set['Name'] == f'{self.hostname}.' and record_set['Type'] == 'AAAA':
                record_values = [record['Value'] for record in record_set['ResourceRecords']]

        return record_values

    def _update_route53_aaaa_record(self, ipv6_addresses):
        # Get the existing "AAAA" record values
        existing_values = self._get_existing_aaaa_record_values()

        # Check if the "AAAA" record exists
        if existing_values:
            # Filter out IPv6 addresses that already exist in Route 53
            new_addresses = [str(addr) for addr in ipv6_addresses if str(addr) not in existing_values]

            if not new_addresses:
                print('Route 53 record is already up to date.')
                return

            # Prepare the changes for the "AAAA" record in Route 53
            changes = []
            for address in new_addresses:
                change = {
                    'Action': 'UPSERT',
                    'ResourceRecordSet': {
                        'Name': f'{self.hostname}.',
                        'Type': 'AAAA',
                        'TTL': 300,
                        'ResourceRecords': [
                            {
                                'Value': address
                            }
                        ]
                    }
                }
                changes.append(change)

        else:
            # Create the "AAAA" record in Route 53
            changes = [
                {
                    'Action': 'CREATE',
                    'ResourceRecordSet': {
                        'Name': f'{self.hostname}.',
                        'Type': 'AAAA',
                        'TTL': 300,
                        'ResourceRecords': [
                            {
                                'Value': str(addr)
                            } for addr in ipv6_addresses
                        ]
                    }
                }
            ]

        # Update the "AAAA" record in Route 53
        response = self.client.change_resource_record_sets(
            HostedZoneId=self.zone_id,
            ChangeBatch={
                'Changes': changes
            }
        )

        print('Route 53 record updated successfully.')

    def update_route53_record(self):
        # Get the public IPv6 addresses from eth0
        public_ipv6_addresses = self._get_public_ipv6_addresses()

        if public_ipv6_addresses:
            # Update the corresponding "AAAA" records in Route 53 if they have changed
            self._update_route53_aaaa_record(public_ipv6_addresses)
        else:
            print('No public IPv6 addresses found on eth0.')

if __name__ == '__main__':
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Update Route 53 AAAA record with public IPv6 addresses.')
    parser.add_argument('-p', '--profile', required=True, help='AWS CLI profile name')
    parser.add_argument('-z', '--zone-id', required=True, help='Route 53 hosted zone ID')
    parser.add_argument('-n', '--hostname', required=True, help='Hostname for the record set')
    args = parser.parse_args()

    # Create an instance of Route53DDNSIPv6
    updater = Route53DDNSIPv6(args.profile, args.zone_id, args.hostname)

    # Update the Route 53 record
    updater.update_route53_record()
