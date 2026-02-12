from __future__ import annotations

"""
Run all slack-objects smoke tests in one command.

Usage:
    python -m tests.run_all_smoke
"""

from tests.users_smoke_test import main as users_main
from tests.messages_smoke_test import main as messages_main
from tests.conversations_smoke_test import main as conversations_main
from tests.files_smoke_test import main as files_main
from tests.idp_groups_smoke_test import main as idp_main
from tests.workspaces_smoke_test import main as workspaces_main
from tests.api_caller_smoke_test import main as api_caller_main
from tests.security_smoke_test import main as security_main


def main() -> None:
    users_main()
    messages_main()
    conversations_main()
    files_main()
    idp_main()
    workspaces_main()
    api_caller_main()
    security_main()
    print("\n✅ All smoke tests completed successfully.")


if __name__ == "__main__":
    main()
