"""
Run all SCIM Users live integration tests in a deliberate order.

Order: safest (no API calls) → read-mostly → reversible → destructive.
Excludes IDP Groups tests (test_scim_idp_groups_live.py).

Usage:
    python tests/SCIM/run_all_scim_user_live_tests.py
    python tests/SCIM/run_all_scim_user_live_tests.py -v --tb=short
    python tests/SCIM/run_all_scim_user_live_tests.py --stop-on-fail
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
    "test_scim_users_input_validation_live.py",   # no API calls
    "test_scim_users_reactivate_live.py",          # read-mostly (no-ops on active users)
    "test_scim_users_update_attribute_live.py",    # mutating, reversible
    "test_scim_users_create_live.py",              # self-contained (create + delete)
    "test_scim_users_deactivate_live.py",          # mutating, reversible (strips workspaces)
    "test_scim_users_make_guest_live.py",          # DESTRUCTIVE (disposable users only)
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
            [sys.executable, "-m", "pytest", str(filepath), *extra_args],
            cwd=str(_HERE.parent.parent),  # workspace root
        )
        results[filename] = rc

        if rc != 0 and stop_on_fail:
            print(f"\n🛑  {filename} failed (exit {rc}) — stopping early.")
            break

    # ── Summary ──────────────────────────────────────────────────────
    print(f"\n{'═' * 70}")
    print("  SCIM Live Test Summary")
    print(f"{'═' * 70}")

    for filename, rc in results.items():
        status = "✅ PASSED" if rc == 0 else f"❌ FAILED (exit {rc})"
        print(f"  {status}  {filename}")

    not_run = [f for f in _TEST_FILES if f not in results]
    for filename in not_run:
        print(f"  ⏭️  SKIPPED  {filename}")

    failed = sum(1 for rc in results.values() if rc != 0)
    print(f"\n  {len(results) - failed} passed, {failed} failed, {len(not_run)} skipped")
    print(f"{'═' * 70}\n")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())