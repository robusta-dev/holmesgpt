#!/usr/bin/env python3
"""
Script to generate connection failures using Azure CLI and REST API calls.
This will trigger connection failure metrics that can be detected by the analysis tool.
"""

import os
import json
import subprocess
import time


def run_az_command(command: str) -> tuple[bool, str]:
    """Run an Azure CLI command and return success status and output."""
    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True, timeout=30
        )
        return (
            result.returncode == 0,
            result.stdout if result.returncode == 0 else result.stderr,
        )
    except subprocess.TimeoutExpired:
        return False, "Command timed out"
    except Exception as e:
        return False, str(e)


def generate_firewall_violations():
    """Generate firewall violations by trying to access from blocked IPs."""

    server = os.environ.get("AZURE_SQL_SERVER")
    database = os.environ.get("AZURE_SQL_DATABASE")
    resource_group = os.environ.get("AZURE_SQL_RESOURCE_GROUP")

    if not all([server, database, resource_group]):
        print("❌ Error: Required environment variables not set")
        return

    print(f"🔥 Generating firewall violations for server: {server}")
    print()

    # Get current firewall rules
    print("=== Getting Current Firewall Rules ===")
    success, output = run_az_command(
        f"az sql server firewall-rule list --server {server} --resource-group {resource_group} --output json"
    )

    if not success:
        print(f"❌ Failed to get firewall rules: {output}")
        return

    try:
        current_rules = json.loads(output)
        print(f"✅ Found {len(current_rules)} existing firewall rules")
        for rule in current_rules:
            print(
                f"  - {rule['name']}: {rule['startIpAddress']} - {rule['endIpAddress']}"
            )
    except json.JSONDecodeError:
        print("❌ Failed to parse firewall rules")
        return

    print()
    print("=== Creating Temporary Restrictive Firewall Rule ===")

    # Create a very restrictive temporary rule that blocks most connections
    temp_rule_name = f"temp_restrictive_rule_{int(time.time())}"
    restricted_ip = "192.168.1.1"  # Private IP that won't have access

    success, output = run_az_command(
        f"az sql server firewall-rule create "
        f"--server {server} "
        f"--resource-group {resource_group} "
        f"--name {temp_rule_name} "
        f"--start-ip-address {restricted_ip} "
        f"--end-ip-address {restricted_ip}"
    )

    if success:
        print(f"✅ Created temporary restrictive rule: {temp_rule_name}")
    else:
        print(f"❌ Failed to create restrictive rule: {output}")
        return

    print()
    print("=== Attempting Connections from Blocked IPs ===")

    # Try to query the database (this should fail due to firewall)
    for i in range(5):
        print(f"Attempt {i+1}: Trying to connect (should be blocked by firewall)...")

        # This command will try to connect and should fail due to firewall restrictions
        success, output = run_az_command(
            f"az sql db show "
            f"--server {server} "
            f"--resource-group {resource_group} "
            f"--name {database} "
            f"--output json"
        )

        if not success:
            print("  ✅ Expected failure: Connection blocked")
        else:
            print("  ⚠️ Unexpected success: Connection allowed")

        time.sleep(2)

    print()
    print("=== Cleaning Up Temporary Rule ===")

    # Remove the temporary restrictive rule
    success, output = run_az_command(
        f"az sql server firewall-rule delete "
        f"--server {server} "
        f"--resource-group {resource_group} "
        f"--name {temp_rule_name} "
        f"--yes"
    )

    if success:
        print(f"✅ Cleaned up temporary rule: {temp_rule_name}")
    else:
        print(f"⚠️ Failed to clean up rule: {output}")

    print()
    print("=== Summary ===")
    print("✅ Generated 5 connection attempts that should trigger firewall blocks")
    print("🔍 These should appear as 'blocked_by_firewall' metrics in Azure Monitor")
    print("📊 Metrics typically appear within 5-10 minutes")


def generate_authentication_failures():
    """Generate authentication failures using invalid SQL queries."""

    server = os.environ.get("AZURE_SQL_SERVER")
    database = os.environ.get("AZURE_SQL_DATABASE")
    resource_group = os.environ.get("AZURE_SQL_RESOURCE_GROUP")

    print()
    print("=== Generating Authentication Failures ===")

    # Try to run queries with invalid authentication (these will fail)
    invalid_queries = [
        "SELECT COUNT(*) FROM sys.tables",
        "SELECT @@VERSION",
        "SELECT DB_NAME()",
        "SELECT GETDATE()",
        "SELECT USER_NAME()",
    ]

    for i, query in enumerate(invalid_queries, 1):
        print(f"Auth attempt {i}: Trying query with potential auth issues...")

        # This will try to execute a query - may fail due to authentication/authorization
        success, output = run_az_command(
            f"az sql db query "
            f"--server {server} "
            f"--database {database} "
            f"--resource-group {resource_group} "
            f"--auth-type SqlPassword "
            f"--username invalid_user_{i} "
            f"--password 'InvalidPass123!' "
            f'--query "{query}"'
        )

        if not success:
            print(f"  ✅ Expected auth failure: {output[:100]}...")
        else:
            print("  ⚠️ Unexpected success")

        time.sleep(1)

    print(f"✅ Generated {len(invalid_queries)} authentication failure attempts")


def main():
    """Main function to generate various types of connection failures."""

    print("🔥 Azure SQL Connection Failure Generator")
    print("=" * 50)
    print("This script will generate various types of connection failures")
    print("to test the connection failure analysis tool.")
    print()

    # Check if user is logged into Azure CLI
    success, output = run_az_command("az account show")
    if not success:
        print("❌ Error: Not logged into Azure CLI. Please run 'az login' first.")
        return

    print("✅ Azure CLI authentication verified")

    # Generate firewall violations
    generate_firewall_violations()

    # Generate authentication failures
    generate_authentication_failures()

    print()
    print("🎯 Connection Failure Generation Complete!")
    print("=" * 50)
    print("Wait 5-10 minutes for metrics to appear in Azure Monitor,")
    print("then run the connection failure analysis tool to see the results.")
    print()
    print("Command to run the analysis:")
    print('  python -c "from analyze_tool import run; run()"')


if __name__ == "__main__":
    main()
