"""
Run all Users Web / Admin API live integration tests in a deliberate order.

Order: safest (no API calls) → read-only → classification → destructive.

Usage:
    python tests/Users/run_all_users_live_tests.py
    python tests/Users/run_all_users_live_tests.py -v --tb=short
    python tests/Users/run_all_users_live_tests.py --stop-on-fail
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent

# Ordered from safest to most destructive.
# Each file runs as a separate pytest invocation so a failure in one
# does NOT skip remaining files (unless --stop-on-fail is passed).
_TEST_FILES = [
    "test_users_input_validation_live.py",    # no API calls
    "test_users_read_live.py",                # read-only
    "test_users_classification_live.py",      # read-only (refresh + bool checks)
    "test_users_admin_live.py",               # MUTATING (disposable users only)
]


def main() -> int:
    stop_on_fail = "--stop-on-fail" in sys.argv
    extra_args = [a for a in sys.argv[1:] if a != "--stop-on-fail"]

    results: dict[str, int] = {}

    for filename in _TEST_FILES:
        filepath = _HERE / filename
        if not filepath.exists():
            print(f"\n⚠️  Skipping {filename} (file not found)")
            continue

        print(f"\n{'═' * 70}")
        print(f"  Running: {filename}")
        print(f"{'═' * 70}\n")

        rc = subprocess.call(
            [sys.executable, "-m", "pytest", str(filepath)] + extra_args
        )
        results[filename] = rc

        if stop_on_fail and rc != 0:
            print(f"\n❌ {filename} failed (rc={rc}); stopping early.")
            break

    # Summary
    print(f"\n{'═' * 70}")
    print("  SUMMARY")
    print(f"{'═' * 70}")
    for name, rc in results.items():
        icon = "✅" if rc == 0 else "❌"
        print(f"  {icon}  {name}  (rc={rc})")
    print()

    return max(results.values()) if results else 1


if __name__ == "__main__":
    sys.exit(main())