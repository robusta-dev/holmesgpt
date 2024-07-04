import boto3
import json
import csv
from datetime import datetime, timedelta

def datetime_converter(o):
    if isinstance(o, datetime):
        return o.__str__()

def fetch_events(event_name, start_time, end_time):
    # Initialize a session using Amazon CloudTrail
    client = boto3.client('cloudtrail')

    # Create a paginator to iterate through CloudTrail events
    paginator = client.get_paginator('lookup_events')

    # Define the filter for the specific event name
    response_iterator = paginator.paginate(
        LookupAttributes=[
            {
                'AttributeKey': 'EventName',
                'AttributeValue': event_name
            },
        ],
        StartTime=start_time,
        EndTime=end_time,
        PaginationConfig={
            'PageSize': 50
        }
    )

    events = []
    # Iterate through the pages of results
    for page in response_iterator:
        events.extend(page['Events'])

    return events

if __name__ == "__main__":
    import sys

    # Ensure the event name is passed as a command-line argument
    if len(sys.argv) != 2:
        print("Usage: python event_lookup.py <EventName>")
        sys.exit(1)

    event_name = sys.argv[1]

    # Define the time range for the lookup (last 7 days)
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(days=7)

    # Fetch events
    events = fetch_events(event_name, start_time, end_time)

    # Write events to a CSV file
    with open(f'{event_name}_events.csv', 'w', newline='') as csvfile:
        fieldnames = ['EventId', 'EventTime', 'Username', 'AccessKeyId', 'ip', 'userID']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

        writer.writeheader()
        for event in events:
            event_data = json.loads(event['CloudTrailEvent'])
            writer.writerow({
                'EventId': event['EventId'],
                'EventTime': event['EventTime'],
                'Username': event['Username'],
                'AccessKeyId': event['AccessKeyId'],
                'ip': event_data['sourceIPAddress'],
                'userID': event_data['userIdentity'].get('sessionContext', {}).get('sessionIssuer', {}).get('userName', "")
            })

    print(f'{event_name}_events.csv')
