"""
Shared pytest configuration for the whole test suite.

The suite has two tiers:

	Offline tier  - tests/UnitTests/*  (fakes only, no network, no credentials)
	Live tier     - tests/**/*_live.py (real Azure Key Vault tokens + real Slack API calls)

Every live test file follows the '*_live.py' naming convention, so instead of
decorating hundreds of tests by hand, this hook marks them automatically at
collection time.

pytest.ini deselects the 'live' marker by default, which makes a bare 'pytest'
run safe: it collects only the offline tier. The live tier is opt-in, since some
of it (notably tests/SCIM) performs mutating operations against real users.

To run the live tier explicitly:

	pytest -m live tests/Users/test_users_read_live.py
	python tests/Users/run_all_users_live_tests.py
"""

import pytest


def pytest_collection_modifyitems(config, items):
	"""Automatically apply the 'live' marker to tests in *_live.py files."""
	for item in items:
		# item.path is the file the test was collected from.
		if item.path is not None and item.path.name.endswith("_live.py"):
			item.add_marker(pytest.mark.live)
