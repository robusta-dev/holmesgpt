#!/usr/bin/env python3
"""
Script to generate connection failures for testing the connection failure analysis tool.
This will attempt connections with invalid credentials and from blocked IPs to trigger failures.
"""

import os
import time
import random
import pyodbc
import concurrent.futures


def attempt_invalid_login(server: str, database: str, attempt_num: int) -> str:
    """Attempt connection with invalid credentials to generate login failures."""
    try:
        # Use invalid username/password combinations
        invalid_users = [
            "hacker_user",
            "admin_test",
            "sa_admin",
            "test_user_invalid",
            "unauthorized_user",
        ]

        invalid_passwords = [
            "password123",
            "admin",
            "wrongpass",
            "123456",
            "hacker_pass",
        ]

        user = random.choice(invalid_users)
        password = random.choice(invalid_passwords)

        # Construct connection string
        connection_string = (
            f"DRIVER={{ODBC Driver 17 for SQL Server}};"
            f"SERVER={server}.database.windows.net;"
            f"DATABASE={database};"
            f"UID={user};"
            f"PWD={password};"
            f"Connection Timeout=5;"
        )

        print(f"Attempt {attempt_num}: Trying invalid login with user '{user}'...")

        # This should fail and generate a connection failure metric
        conn = pyodbc.connect(connection_string)
        conn.close()

        return f"Attempt {attempt_num}: UNEXPECTED SUCCESS with {user}"

    except pyodbc.Error as e:
        error_code = e.args[0] if e.args else "Unknown"
        error_msg = e.args[1] if len(e.args) > 1 else str(e)
        return (
            f"Attempt {attempt_num}: Expected failure - {error_code}: {error_msg[:100]}"
        )
    except Exception as e:
        return f"Attempt {attempt_num}: Connection error - {str(e)[:100]}"


def attempt_timeout_connection(server: str, database: str, attempt_num: int) -> str:
    """Attempt connection with very short timeout to generate timeout failures."""
    try:
        # Use valid credentials but extremely short timeout
        connection_string = (
            f"DRIVER={{ODBC Driver 17 for SQL Server}};"
            f"SERVER={server}.database.windows.net;"
            f"DATABASE={database};"
            f"UID={os.environ.get('AZURE_SQL_USER', 'testuser')};"
            f"PWD={os.environ.get('AZURE_SQL_PASSWORD', 'testpass')};"
            f"Connection Timeout=1;"  # Very short timeout
        )

        print(f"Timeout attempt {attempt_num}: Trying connection with 1s timeout...")

        conn = pyodbc.connect(connection_string)
        conn.close()

        return f"Timeout attempt {attempt_num}: UNEXPECTED SUCCESS"

    except pyodbc.Error as e:
        error_code = e.args[0] if e.args else "Unknown"
        error_msg = e.args[1] if len(e.args) > 1 else str(e)
        return f"Timeout attempt {attempt_num}: Expected timeout - {error_code}: {error_msg[:100]}"
    except Exception as e:
        return f"Timeout attempt {attempt_num}: Connection error - {str(e)[:100]}"


def generate_connection_failures():
    """Generate various types of connection failures for testing."""

    server = os.environ.get("AZURE_SQL_SERVER")
    database = os.environ.get("AZURE_SQL_DATABASE")

    if not server or not database:
        print(
            "❌ Error: AZURE_SQL_SERVER and AZURE_SQL_DATABASE environment variables must be set"
        )
        return

    print(
        f"🔥 Generating connection failures for server: {server}, database: {database}"
    )
    print(
        "This will create metrics that can be detected by the connection failure analysis tool"
    )
    print()

    # Generate multiple invalid login attempts
    print("=== Generating Invalid Login Attempts ===")
    login_results = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        # Submit 10 invalid login attempts
        future_to_attempt = {
            executor.submit(attempt_invalid_login, server, database, i): i
            for i in range(1, 11)
        }

        for future in concurrent.futures.as_completed(future_to_attempt):
            attempt_num = future_to_attempt[future]
            try:
                result = future.result()
                login_results.append(result)
                print(result)
            except Exception as e:
                error_msg = f"Attempt {attempt_num}: Exception - {str(e)}"
                login_results.append(error_msg)
                print(error_msg)

            # Small delay between attempts
            time.sleep(0.5)

    print()
    print("=== Generating Timeout Attempts ===")
    timeout_results = []

    # Generate timeout-based failures
    for i in range(1, 6):
        result = attempt_timeout_connection(server, database, i)
        timeout_results.append(result)
        print(result)
        time.sleep(1)

    print()
    print("=== Summary ===")
    print(f"✅ Generated {len(login_results)} invalid login attempts")
    print(f"✅ Generated {len(timeout_results)} timeout attempts")
    print(
        f"🔍 Total connection failure attempts: {len(login_results) + len(timeout_results)}"
    )
    print()
    print(
        "These failures should now be visible in Azure Monitor metrics within 5-10 minutes."
    )
    print("You can run the connection failure analysis tool to see these failures.")
    print()
    print(
        "Note: These are intentional failures for testing purposes and do not indicate"
    )
    print("any actual security issues with your database.")


if __name__ == "__main__":
    generate_connection_failures()
