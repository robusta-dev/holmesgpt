import boto3

def get_all_cloudwatch_alarms():
    # Create a CloudWatch client
    client = boto3.client('cloudwatch')

    # Initialize pagination for DescribeAlarms API call
    paginator = client.get_paginator('describe_alarms')
    
    alarms = []
    
    # Paginate through all alarms
    for page in paginator.paginate():
        alarms.extend(page['MetricAlarms'])

    return alarms

if __name__ == "__main__":
    # Get all alarms
    all_alarms = get_all_cloudwatch_alarms()

    # Print alarms
    for alarm in all_alarms:
        print(f"Alarm Name: {alarm['AlarmName']}, State: {alarm['StateValue']}")
