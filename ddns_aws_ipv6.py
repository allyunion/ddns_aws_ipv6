#!/usr/bin/env python3

import ipaddress
import argparse
import boto3

class Route53DDNSIPv6:
    def __init__(self, profile):
        self.profile = profile
        self.client = self._get_route53_client()

    def _get_route53_client(self):
        # Initialize the Route 53 client using the specified AWS CLI profile
        session = boto3.Session(profile_name=self.profile)
        return session.client('route53')

    def _get_public_ipv6_address(self):
        # Get the IPv6 addresses from eth0 interface
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
                            return ip
                    except ipaddress.AddressValueError:
                        # Invalid IPv6 address
                        pass

        return None

    def _get_existing_aaaa_record_value(self):
        # Get the existing "AAAA" record value from Route 53
        response = self.client.list_resource_record_sets(
            HostedZoneId='YOUR_HOSTED_ZONE_ID',
            StartRecordName='example.com.',
            StartRecordType='AAAA',
            MaxItems='1'
        )

        if 'ResourceRecordSets' in response:
            record_set = response['ResourceRecordSets'][0]
            if record_set['Name'] == 'example.com.' and record_set['Type'] == 'AAAA':
                return record_set['ResourceRecords'][0]['Value']

        return None

    def _update_route53_aaaa_record(self, ipv6_address):
        # Get the existing "AAAA" record value
        existing_value = self._get_existing_aaaa_record_value()

        # Check if the record already exists and has the same value
        if existing_value == str(ipv6_address):
            print('Route 53 record is already up to date.')
            return

        # Update the "AAAA" record in Route 53
        response = self.client.change_resource_record_sets(
            HostedZoneId='YOUR_HOSTED_ZONE_ID',
            ChangeBatch={
                'Changes': [
                    {
                        'Action': 'UPSERT',
                        'ResourceRecordSet': {
                            'Name': 'example.com.',
                            'Type': 'AAAA',
                            'TTL': 300,
                            'ResourceRecords': [
                                {
                                    'Value': str(ipv6_address)
                                }
                            ]
                        }
                    }
                ]
            }
        )

        print('Route 53 record updated successfully.')

    def update_route53_record(self):
        # Get the public IPv6 address from eth0
        public_ipv6 = self._get_public_ipv6_address()

        if public_ipv6 is not None:
            # Update the corresponding "AAAA" record in Route 53 if it has changed
            self._update_route53_aaaa_record(public_ipv6)
        else:
            print('No public IPv6 address found on eth0.')

if __name__ == '__main__':
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Update Route 53 AAAA record with public IPv6 address')
    parser.add_argument('-p', '--profile', required=True, help='AWS CLI profile name')
    args = parser.parse_args()

    # Create an instance of the Route53DDNSIPv6 class and update the Route 53 record
    updater = Route53DDNSIPv6(args.profile)
    updater.update_route53_record()
