import boto3
import json
from datetime import datetime

def datetime_converter(o):
    if isinstance(o, datetime):
        return o.__str__()

def fetch_event_details(event_id):
    # Initialize a session using Amazon CloudTrail
    client = boto3.client('cloudtrail')

    # Create a paginator to iterate through CloudTrail events
    paginator = client.get_paginator('lookup_events')

    # Define the filter for the specific event ID
    response_iterator = paginator.paginate(
        LookupAttributes=[
            {
                'AttributeKey': 'EventId',
                'AttributeValue': event_id
            },
        ],
        PaginationConfig={
            'PageSize': 1
        }
    )

    events = []
    # Iterate through the pages of results
    for page in response_iterator:
        events.extend(page['Events'])

    return events[0] if events else None

if __name__ == "__main__":
    import sys

    # Ensure the event ID is passed as a command-line argument
    if len(sys.argv) != 2:
        print("Usage: python event_details.py <EventId>")
        sys.exit(1)

    event_id = sys.argv[1]

    # Fetch event details
    event_details = fetch_event_details(event_id)

    if event_details:
        # Write event details to a JSON file
        filename = f"{event_id}_event_details.json"
        with open(filename, 'w') as f:
            json.dump(event_details, f, default=datetime_converter, indent=4)

        print(f"{filename}")
    else:
        print(f"No event found with event ID {event_id}")
