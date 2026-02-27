from __future__ import annotations

"""
Run all slack-objects smoke tests in one command.

Usage:
    python -m tests.Smoke.run_all_smoke
"""

from tests.Smoke.users_smoke_test import main as users_main
from tests.Smoke.messages_smoke_test import main as messages_main
from tests.Smoke.conversations_smoke_test import main as conversations_main
from tests.Smoke.files_smoke_test import main as files_main
from tests.Smoke.idp_groups_smoke_test import main as idp_main
from tests.Smoke.workspaces_smoke_test import main as workspaces_main
from tests.Smoke.api_caller_smoke_test import main as api_caller_main
from tests.Smoke.security_smoke_test import main as security_main
from tests.Smoke.usergroups_smoke_test import main as usergroups_main


def main() -> None:
    users_main()
    messages_main()
    conversations_main()
    files_main()
    idp_main()
    workspaces_main()
    api_caller_main()
    security_main()
    usergroups_main()
    print("\n✅ All smoke tests completed successfully.")


if __name__ == "__main__":
    main()
