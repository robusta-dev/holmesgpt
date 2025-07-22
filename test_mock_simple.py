#!/usr/bin/env python3
"""Simple test to verify mock system behavior."""

import os
import subprocess
from pathlib import Path

# Test directory
test_dir = Path("tests/llm/fixtures/test_ask_holmes/01_how_many_pods")


def run_test(env=None, args=""):
    """Run test with environment and arguments."""
    cmd = f"poetry run pytest tests/llm/test_ask_holmes.py -k '01_how_many_pods' -xvs --tb=short --no-cov {args}"

    full_env = os.environ.copy()
    if env:
        full_env.update(env)

    result = subprocess.run(
        cmd, shell=True, capture_output=True, text=True, env=full_env, timeout=30
    )

    return result


def check_mock_files():
    """Check what mock files exist."""
    return list(test_dir.glob("*.txt"))


def clear_mocks():
    """Clear all mock files."""
    for f in test_dir.glob("*.txt"):
        f.unlink()


print("=== Mock System Test Summary ===\n")

# Test 1: Default mode without mocks (should fail with MockDataError)
print("1. Default mode without mocks:")
clear_mocks()
result = run_test()
if "MockDataError" in result.stdout or "MockDataNotFoundError" in result.stdout:
    print("✓ Correctly failed with MockDataError")
else:
    print("✗ Did not fail with MockDataError as expected")

# Test 2: Generate mocks
print("\n2. Generate mocks mode:")
clear_mocks()
result = run_test(args="--generate-mocks")
mocks = check_mock_files()
if mocks:
    print(f"✓ Generated {len(mocks)} mock file(s)")
    for m in mocks:
        print(f"  - {m.name}")
else:
    print("✗ No mock files generated")

# Test 3: Use existing mocks
print("\n3. Use existing mocks:")
if mocks:
    result = run_test()
    if "MockDataError" not in result.stdout:
        print("✓ Successfully used existing mocks")
    else:
        print("✗ Failed to use existing mocks")
else:
    print("⚠ Skipped - no mocks available")

# Test 4: Regenerate all mocks
print("\n4. Regenerate all mocks:")
result = run_test(args="--regenerate-all-mocks")
if "Cleared existing mocks" in result.stdout and "Generated" in result.stdout:
    print("✓ Cleared and regenerated mocks")
else:
    print("✗ Did not clear/regenerate properly")

# Test 5: Live mode (brief test)
print("\n5. Live mode:")
result = run_test(env={"RUN_LIVE": "true"})
if "MockDataError" not in result.stdout[:1000]:  # Check first 1000 chars
    print("✓ No MockDataError in live mode (as expected)")
else:
    print("✗ Got MockDataError in live mode (unexpected)")

# Test 6: Summary table check
print("\n6. Summary table:")
clear_mocks()
result = run_test()
if "MOCK FAILURE" in result.stdout:
    print("✓ Shows MOCK FAILURE status in summary")
else:
    print("✗ Does not show MOCK FAILURE status")

print("\n=== Complete ===")
