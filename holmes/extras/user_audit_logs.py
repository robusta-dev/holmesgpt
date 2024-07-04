import boto3
import json
import csv
from datetime import datetime, timedelta

def datetime_converter(o):
    if isinstance(o, datetime):
        return o.__str__()

def fetch_audit_logs_for_user(username, start_time, end_time):
    # Initialize a session using Amazon CloudTrail
    client = boto3.client('cloudtrail')

    # Create a paginator to iterate through CloudTrail events
    paginator = client.get_paginator('lookup_events')

    # Define the filter for the specific username
    response_iterator = paginator.paginate(
        LookupAttributes=[
            {
                'AttributeKey': 'Username',
                'AttributeValue': username
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

    # Ensure the username and hours back are passed as command-line arguments
    if len(sys.argv) != 3:
        print("Usage: python user_audit_logs.py <Username> <HoursBack>")
        sys.exit(1)

    username = sys.argv[1]
    hours_back = int(sys.argv[2])

    # Define the time range for the lookup (past specified number of hours)
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(hours=hours_back)

    # Fetch audit logs for the user
    audit_logs = fetch_audit_logs_for_user(username, start_time, end_time)

    # Write events to a CSV file
    filename = f"{username}_audit_logs.csv"
    with open(filename, 'w', newline='') as csvfile:
        fieldnames = ['EventName','EventSource', 'EventId', 'EventTime', 'Username', 'AccessKeyId', 'ip', 'userID']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

        writer.writeheader()
        for event in audit_logs:
            event_data = json.loads(event['CloudTrailEvent'])
            writer.writerow({
                'EventName': event['EventName'],
                'EventSource': event['EventSource'],
                'EventId': event['EventId'],
                'EventTime': event['EventTime'],
                'Username': event['Username'],
                'AccessKeyId': event['AccessKeyId'],
                'ip': event_data['sourceIPAddress'],
                'userID': event_data['userIdentity']['sessionContext']['sessionIssuer']['userName']
            })

    print(f"{filename}")

