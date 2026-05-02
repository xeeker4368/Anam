import importlib
import types
from types import SimpleNamespace
from unittest.mock import patch

import pytest


class FakePasswordHasher:
    def hash(self, password):
        return f"hashed:{password}"


@pytest.fixture()
def temp_admin(tmp_path):
    with patch("tir.config.DATA_DIR", tmp_path), \
         patch("tir.config.ARCHIVE_DB", tmp_path / "archive.db"), \
         patch("tir.config.WORKING_DB", tmp_path / "working.db"):
        import tir.memory.db as db_mod
        import tir.admin as admin_mod

        importlib.reload(db_mod)
        importlib.reload(admin_mod)
        db_mod.init_databases()
        yield db_mod, admin_mod


def test_set_password_creates_web_channel_row_when_absent(temp_admin, capsys):
    db_mod, admin_mod = temp_admin
    user = db_mod.create_user("Lyle")
    fake_argon2 = types.SimpleNamespace(PasswordHasher=FakePasswordHasher)

    with patch.dict("sys.modules", {"argon2": fake_argon2}), \
         patch("tir.admin.getpass.getpass", side_effect=["secret", "secret"]):
        admin_mod.cmd_set_password(SimpleNamespace(user="Lyle"))

    output = capsys.readouterr().out
    assert "Password set for Lyle (web channel)" in output

    with db_mod.get_connection() as conn:
        rows = conn.execute(
            """SELECT * FROM main.channel_identifiers
               WHERE channel = 'web' AND identifier = 'lyle'"""
        ).fetchall()

    assert len(rows) == 1
    assert rows[0]["user_id"] == user["id"]
    assert rows[0]["auth_material"] == "hashed:secret"
    assert rows[0]["verified"] == 1


def test_set_password_updates_existing_web_channel_without_duplicate(temp_admin, capsys):
    db_mod, admin_mod = temp_admin
    user = db_mod.create_user("Lyle")
    existing = db_mod.add_channel_identifier(
        user_id=user["id"],
        channel="web",
        identifier="lyle",
        auth_material="old-hash",
        verified=False,
    )
    fake_argon2 = types.SimpleNamespace(PasswordHasher=FakePasswordHasher)

    with patch.dict("sys.modules", {"argon2": fake_argon2}), \
         patch("tir.admin.getpass.getpass", side_effect=["new-secret", "new-secret"]):
        admin_mod.cmd_set_password(SimpleNamespace(user="Lyle"))

    output = capsys.readouterr().out
    assert "Password set for Lyle (web channel)" in output

    with db_mod.get_connection() as conn:
        rows = conn.execute(
            """SELECT * FROM main.channel_identifiers
               WHERE channel = 'web' AND identifier = 'lyle'"""
        ).fetchall()

    assert len(rows) == 1
    assert rows[0]["id"] == existing["id"]
    assert rows[0]["auth_material"] == "hashed:new-secret"
    assert rows[0]["verified"] == 1
