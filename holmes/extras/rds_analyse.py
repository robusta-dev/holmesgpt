import boto3
from datetime import datetime, timedelta
import re

def fetch_and_analyze_slow_query_log(db_instance_identifier, start_time, end_time):
    client = boto3.client('rds', region_name="us-east-2")
    
    log_files = client.describe_db_log_files(
        DBInstanceIdentifier=db_instance_identifier,
        FilenameContains='slowquery'
    )['DescribeDBLogFiles']
    
    logs_content = ""
    for log_file in log_files:
        log_response = client.download_db_log_file_portion(
            DBInstanceIdentifier=db_instance_identifier,
            LogFileName=log_file['LogFileName'],
            Marker='0'
        )
        logs_content += log_response['LogFileData']
    
    # Analyze logs content
    slow_queries = []
    log_lines = logs_content.split('\n')
    for line in log_lines:
        if "Query_time" in line:
            match = re.search(r'(\d+:\d+:\d+)\s+\[Note\]\s+Query_time:\s+(\d+.\d+)', line)
            if match:
                time = match.group(1)
                query_time = float(match.group(2))
                slow_queries.append((time, query_time))
    
    # Find the most time-consuming queries
    slow_queries.sort(key=lambda x: x[1], reverse=True)
    return slow_queries[:10]

def get_db_connections_count(db_instance_identifier, start_time, end_time):
    client = boto3.client('cloudwatch', region_name="us-east-2")
    
    response = client.get_metric_statistics(
        Namespace='AWS/RDS',
        MetricName='DatabaseConnections',
        Dimensions=[
            {'Name': 'DBInstanceIdentifier', 'Value': db_instance_identifier}
        ],
        StartTime=start_time,
        EndTime=end_time,
        Period=300,
        Statistics=['Average']
    )
    
    return response['Datapoints']


def get_client_identity():
    sts_client = boto3.client('sts', region_name="us-east-2")
    identity = sts_client.get_caller_identity()
    return identity

def get_rds_cpu_utilization(db_instance_identifier):
    client = boto3.client('cloudwatch', region_name="us-east-2")
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(hours=1)
    
    response = client.get_metric_statistics(
        Namespace='AWS/RDS',
        MetricName='CPUUtilization',
        Dimensions=[
            {'Name': 'DBInstanceIdentifier', 'Value': db_instance_identifier}
        ],
        StartTime=start_time,
        EndTime=end_time,
        Period=300,
        Statistics=['Average']
    )
    
    return response['Datapoints']

def get_performance_insights_metrics(db_instance_identifier):
    client = boto3.client('rds', region_name="us-east-2")
    
    response = client.describe_db_instances(
        DBInstanceIdentifier=db_instance_identifier
    )
    
    db_instances = response['DBInstances']
    for db_instance in db_instances:
        cpu_utilization = db_instance['DBInstanceStatus']
        endpoint = db_instance['Endpoint']
        engine = db_instance['Engine']
        
        print(f"DB Instance Status: {cpu_utilization}")
        print(f"DB Instance Endpoint: {endpoint}")
        print(f"DB Engine: {engine}")
    
    return db_instances


def get_rds_logs(db_instance_identifier, log_file_name):
    client = boto3.client('rds', region_name="us-east-2")
    
    response = client.download_db_log_file_portion(
        DBInstanceIdentifier=db_instance_identifier,
        LogFileName=log_file_name,
        Marker='0',
        NumberOfLines=100
    )
    lines_to_print = 2 # just noise in our example
    return '\n'.join(response['LogFileData'].splitlines()[:lines_to_print])

if __name__ == "__main__":
    db_instance_identifier = 'promotions-db'

    # Step 1: Fetch CPU utilization
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(hours=1)
    
    # Step 1: Fetch CPU utilization
    print("Fetching CPU utilization data...")
    cpu_data = get_rds_cpu_utilization(db_instance_identifier)
    for data_point in cpu_data:
        print(f"Timestamp: {data_point['Timestamp']}, CPU Utilization: {data_point['Average']}%")
    
    # Step 2: Fetch and analyze slow query log
    print("\nFetching and analyzing slow query log...")
    slow_queries = fetch_and_analyze_slow_query_log(db_instance_identifier, start_time, end_time)
    for query in slow_queries:
        print(f"Time: {query[0]}, Query Time: {query[1]} seconds")
    
    # Step 3: Fetch the number of database connections
    print("\nFetching number of database connections...")
    connections = get_db_connections_count(db_instance_identifier, start_time, end_time)
    for connection in connections:
        print(f"Timestamp: {connection['Timestamp']}, Average Connections: {connection['Average']}")
    
    #Step 2: Analyze database load
    print("\nFetching Performance Insights data...")
    performance_metrics = get_performance_insights_metrics(db_instance_identifier)
    for metric in performance_metrics:
        print(f"DB Instance: {metric['DBInstanceIdentifier']}, Status: {metric['DBInstanceStatus']}")
    
    # Step 3: Check RDS logs
    print("\nFetching RDS logs...")
    log_file_name = 'error/mysql-error.log'  # Modify according to your DB engine
    logs = get_rds_logs(db_instance_identifier, log_file_name)
    print(logs)
