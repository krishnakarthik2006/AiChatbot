"""Domain objects for the file-backed application store."""
from __future__ import annotations
from dataclasses import dataclass
from flask_login import UserMixin
from werkzeug.security import check_password_hash


@dataclass
class Account(UserMixin):
    id: int
    email: str
    password_hash: str
    display_name: str | None = None
    created_at: str | None = None

    def to_dict(self):
        return {"id": self.id, "email": self.email,
                "display_name": self.display_name or self.email.split("@")[0], "created_at": self.created_at}

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
