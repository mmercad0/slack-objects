from dataclasses import dataclass
from typing import Optional

from base import SlackObjectBase


@dataclass
class Users(SlackObjectBase):
    user_id: Optional[str] = None

    def with_user(self, user_id: str) -> "Users":
        """
        Convenience method to create a new Users instance bound to a user_id,
        while sharing the same cfg/client/logger/api.
        """
        return Users(cfg=self.cfg, client=self.client, logger=self.logger, api=self.api, user_id=user_id)

    def get_userId_from_email(self, email: str) -> Optional[str]:
        resp = self.api.call(self.client, "users.lookupByEmail", email=email)
        user = resp.get("user")
        if not user:
            return None
        return user.get("id")

    def is_guest(self) -> bool:
        """
        Example: requires self.user_id to be set.
        """
        if not self.user_id:
            raise ValueError("user_id is required for is_guest()")

        resp = self.api.call(self.client, "users.info", user=self.user_id)
        u = resp["user"]
        return bool(u.get("is_restricted") or u.get("is_ultra_restricted"))
