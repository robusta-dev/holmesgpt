import mysql.connector
from mysql.connector import Error
import boto3
from datetime import datetime, timedelta

# Database connection details
db_config = {
    'database': 'new_database',
    'user': 'admin',
    'password': 'secret99',
    'host': 'test-mysql-instance.cp8rwothwarq.us-east-2.rds.amazonaws.com',
    'port': '3306'
}

# AWS CloudWatch client
cloudwatch = boto3.client('cloudwatch', region_name='us-east-2')

def connect_to_db(config):
    try:
        conn = mysql.connector.connect(**config)
        return conn
    except Error as e:
        print(f"Error connecting to database: {e}")
        return None

def get_total_connections(conn):
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM information_schema.processlist;")
        result = cursor.fetchone()
        cursor.close()
        return result[0]
    except Error as e:
        print(f"Error fetching total connections: {e}")
        return None

def get_connections_by_state(conn):
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT state, COUNT(*) FROM information_schema.processlist GROUP BY state;")
        result = cursor.fetchall()
        cursor.close()
        return result
    except Error as e:
        print(f"Error fetching connections by state: {e}")
        return None

def get_blocked_connections(conn):
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(DISTINCT requesting_trx_id) FROM information_schema.innodb_lock_waits;")
        result = cursor.fetchone()
        cursor.close()
        return result[0]
    except Error as e:
        print(f"Error fetching blocked connections: {e}")
        return None

def get_max_transaction_age(conn):
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT MAX(TIMESTAMPDIFF(SECOND, trx_started, NOW())) FROM information_schema.innodb_trx;")
        result = cursor.fetchone()
        cursor.close()
        return result[0]
    except Error as e:
        print(f"Error fetching max transaction age: {e}")
        return None

def get_query_execution_time(conn):
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DIGEST_TEXT AS event_name, 
                   COUNT_STAR AS count, 
                   SUM_TIMER_WAIT / 1000000000 AS total_time_ms,
                   AVG_TIMER_WAIT / 1000000 AS avg_time_ms
            FROM performance_schema.events_statements_summary_by_digest
            ORDER BY SUM_TIMER_WAIT DESC
            LIMIT 5;
        """)
        result = cursor.fetchall()
        cursor.close()
        return result
    except Error as e:
        print(f"Error fetching query execution time: {e}")
        return None

def get_checkpoint_interval(conn):
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT VARIABLE_VALUE
            FROM performance_schema.global_status
            WHERE VARIABLE_NAME = 'Innodb_checkpoint_age';
        """)
        result = cursor.fetchone()
        cursor.close()
        return result[0] if result else None
    except Error as e:
        print(f"Error fetching checkpoint interval: {e}")
        return None

def get_rds_disk_space():
    try:
        response = cloudwatch.get_metric_statistics(
            Namespace='AWS/RDS',
            MetricName='FreeStorageSpace',
            Dimensions=[
                {
                    'Name': 'DBInstanceIdentifier',
                    'Value': 'your-rds-instance-identifier'
                },
            ],
            StartTime=datetime.utcnow() - timedelta(hours=1),
            EndTime=datetime.utcnow(),
            Period=3600,
            Statistics=['Average']
        )
        if response['Datapoints']:
            free_storage_space = response['Datapoints'][0]['Average']
            return free_storage_space
        else:
            print("No datapoints found for FreeStorageSpace metric.")
            return None
    except Exception as e:
        print(f"Error fetching RDS disk space: {e}")
        return None


def get_cpu_usage(conn):
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT AVG(TIMER_WAIT) / 1000000 AS avg_cpu_time, MAX(TIMER_WAIT) / 1000000 AS max_cpu_time
            FROM performance_schema.events_waits_summary_global_by_event_name
            WHERE EVENT_NAME LIKE 'wait/io/%'
            AND EVENT_NAME NOT LIKE 'wait/io/file/%'
            AND EVENT_NAME NOT LIKE 'wait/io/socket/%'
        """)
        result = cursor.fetchone()
        cursor.close()
        return result
    except Error as e:
        print(f"Error fetching CPU usage: {e}")
        return None

def get_io_usage(conn):
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT AVG(TIMER_WAIT) / 1000000 AS avg_io_time, MAX(TIMER_WAIT) / 1000000 AS max_io_time
            FROM performance_schema.events_waits_summary_global_by_event_name
            WHERE EVENT_NAME LIKE 'wait/io/file/%'
        """)
        result = cursor.fetchone()
        cursor.close()
        return result
    except Error as e:
        print(f"Error fetching I/O usage: {e}")
        return None

def print_system_factors(conn):
    rds_disk_space = get_rds_disk_space()
    cpu_usage = get_cpu_usage(conn)
    io_usage = get_io_usage(conn)

    print("System Factors:")
    if rds_disk_space is not None:
        print(f"1. RDS Disk Space: {rds_disk_space:.2f} bytes free space")
    else:
        print("1. RDS Disk Space: Unable to retrieve")

    if cpu_usage:
        avg_cpu, max_cpu = cpu_usage
        print(f"2. CPU Usage: Average - {avg_cpu} ms, Maximum - {max_cpu} ms in the last hour")
    else:
        print("2. CPU Usage: Unable to retrieve")

    if io_usage:
        avg_io, max_io = io_usage
        print(f"3. I/O Usage: Average - {avg_io} ms, Maximum - {max_io} ms in the last hour")
    else:
        print("3. I/O Usage: Unable to retrieve")


def print_mysql_factors(conn):
    print("MySQL Factors:")
    print(f"1. Total Number of Connections: {get_total_connections(conn)}")
    print("2. Number of Connections by State:")
    for state, count in get_connections_by_state(conn):
        print(f"   - {state}: {count}")
    print(f"3. Connections Waiting for a Lock: {get_blocked_connections(conn)}")
    max_transaction_age = get_max_transaction_age(conn)
    print(f"4. Maximum Transaction Age: {max_transaction_age if max_transaction_age else 'N/A'}")
    checkpoint_interval = get_checkpoint_interval(conn)
    print(f"5. Checkpoint Interval: {checkpoint_interval if checkpoint_interval else 'N/A'}")
    print("6. Query Execution Time:")
    query_times = get_query_execution_time(conn)
    if query_times:
        for event_name, count, total_time, avg_time in query_times:
            print(f"   - {event_name}: Executed {count} times, Total Time: {total_time} ms, Avg Time: {avg_time} ms")

def main():
    conn = connect_to_db(db_config)
    if conn:
        print_system_factors(conn)
        print_mysql_factors(conn)
        conn.close()
    else:
        print("Failed to connect to the database.")

if __name__ == "__main__":
    main()
