"""OneDrive upload of the diagnosis history (5.4.0): HistorySync calls "rclone copy" only when rclone, the remote and the internet are there."""
import os
from types import SimpleNamespace

import app_harness as H


class FakeRclone:
    """Stands in for subprocess.run of the rclone binary; records every call."""

    def __init__(self, remotes="agrilens_onedrive:\n", copy_rc=0, copy_err=""):
        self.calls, self.remotes, self.copy_rc, self.copy_err = [], remotes, copy_rc, copy_err

    def __call__(self, cmd, **kw):
        self.calls.append(list(cmd))
        if cmd[1] == "listremotes":
            return SimpleNamespace(returncode=0, stdout=self.remotes, stderr="")
        return SimpleNamespace(returncode=self.copy_rc, stdout="", stderr=self.copy_err)


def _sync(app, tmp_path, monkeypatch, fake, online=True, which="/usr/bin/rclone", **kw):
    src = tmp_path / "AGRILENS_history"
    src.mkdir(exist_ok=True)
    (src / "diagnosis_log.csv").write_text("record_id\n")
    monkeypatch.setattr("shutil.which", lambda name: which if name == "rclone" else None)
    monkeypatch.setattr(app.subprocess, "run", fake)
    s = app.HistorySync(str(src), log_path=str(tmp_path / "sync.log"), **kw)
    monkeypatch.setattr(s, "_online", lambda: online)
    return s


def test_uploads_with_rclone_copy_never_sync(app, tmp_path, monkeypatch):
    fake = FakeRclone()
    s = _sync(app, tmp_path, monkeypatch, fake, remote="agrilens_onedrive", dest_path="OneDrive/Docs/AGRILENS_5.0.0/Kiosk_History")
    st = s.run_once()
    assert st.startswith("uploaded to agrilens_onedrive:OneDrive/Docs/AGRILENS_5.0.0/Kiosk_History")
    copy = fake.calls[-1]
    assert copy[1] == "copy" and copy[2] == str(tmp_path / "AGRILENS_history") and copy[3] == "agrilens_onedrive:OneDrive/Docs/AGRILENS_5.0.0/Kiosk_History"
    assert "sync" not in copy and not any(a.startswith("--delete") for a in copy)   # never deletes anything in OneDrive
    assert "--min-age" in copy                                                        # files still being written are left for the next run
    assert s.last_success and "uploaded" in (tmp_path / "sync.log").read_text()


def test_offline_attempt_is_skipped_without_calling_copy(app, tmp_path, monkeypatch):
    fake = FakeRclone()
    s = _sync(app, tmp_path, monkeypatch, fake, online=False)
    assert s.run_once() == "offline (skipped)"
    assert [c[1] for c in fake.calls] == ["listremotes"]


def test_nothing_happens_without_rclone(app, tmp_path, monkeypatch):
    fake = FakeRclone()
    s = _sync(app, tmp_path, monkeypatch, fake, which=None)
    assert s.run_once() == "rclone not installed" and fake.calls == []


def test_nothing_happens_until_the_remote_is_configured(app, tmp_path, monkeypatch):
    fake = FakeRclone(remotes="other:\n")
    s = _sync(app, tmp_path, monkeypatch, fake)
    assert s.run_once() == "remote 'agrilens_onedrive' not configured"
    assert [c[1] for c in fake.calls] == ["listremotes"]


def test_rclone_failure_is_reported_and_logged(app, tmp_path, monkeypatch):
    fake = FakeRclone(copy_rc=7, copy_err="ERROR : couldn't connect\nFailed to copy: token expired")
    s = _sync(app, tmp_path, monkeypatch, fake)
    st = s.run_once()
    assert st.startswith("rclone failed (exit 7)") and "token expired" in st and not s.last_success
    assert "rclone failed" in (tmp_path / "sync.log").read_text()


def test_disabled_sync_does_nothing(app, tmp_path, monkeypatch):
    fake = FakeRclone()
    s = _sync(app, tmp_path, monkeypatch, fake, enabled=False)
    assert s.run_once() == "disabled" and fake.calls == []


def test_no_history_folder_yet(app, tmp_path, monkeypatch):
    fake = FakeRclone()
    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/rclone")
    monkeypatch.setattr(app.subprocess, "run", fake)
    s = app.HistorySync(str(tmp_path / "missing"), log_path=str(tmp_path / "sync.log"))
    assert s.run_once() == "no history yet" and fake.calls == []


def test_errors_never_raise(app, tmp_path, monkeypatch):
    def boom(*a, **k):
        raise OSError("rclone crashed")
    s = _sync(app, tmp_path, monkeypatch, boom)
    assert s.run_once().startswith("error:")


def test_log_is_trimmed_to_1000_lines(app, tmp_path, monkeypatch):
    log = tmp_path / "sync.log"
    log.write_text("\n".join(f"old {i}" for i in range(1500)) + "\n")
    s = _sync(app, tmp_path, monkeypatch, FakeRclone(), online=False)
    s.run_once()
    lines = log.read_text().splitlines()
    assert len(lines) == 1000 and lines[-1].endswith("offline (skipped)") and lines[0] == "old 501"


def test_interval_has_a_lower_bound(app):
    assert app.HistorySync(minutes=1).minutes == 5 and app.HistorySync(minutes=30).minutes == 30


def test_sync_settings_are_validated_and_saved():
    app = H.load_app()
    c = H.effective_config(app)
    assert (c["history_sync_enabled"], c["history_sync_remote"], c["history_sync_path"], c["history_sync_minutes"]) == (True, "agrilens_onedrive", "AGRILENS_Kiosk_History", 30)
    c = H.effective_config(app, repo_cfg={"history_sync_remote": "bad name; rm", "history_sync_path": "../etc", "history_sync_minutes": 1, "history_sync_enabled": "yes"})
    assert (c["history_sync_remote"], c["history_sync_path"], c["history_sync_minutes"], c["history_sync_enabled"]) == ("agrilens_onedrive", "AGRILENS_Kiosk_History", 5, True)
    c = H.effective_config(app, user_cfg={"history_sync_remote": "my_od:", "history_sync_path": "\\OneDrive\\A B\\Kiosk_History\\", "history_sync_minutes": 99999})
    assert (c["history_sync_remote"], c["history_sync_path"], c["history_sync_minutes"]) == ("my_od", "OneDrive/A B/Kiosk_History", 1440)
    src = open(os.path.join(H.REPO_ROOT, "application", "main.py"), encoding="utf-8").read()
    block = src.split("def _save_current_settings(self):", 1)[1].split("save_kiosk_config(cfg)", 1)[0]
    assert "history_sync_cfg" in block and '"history_sync_path"' in block


def test_the_app_never_stores_onedrive_credentials():
    src = open(os.path.join(H.REPO_ROOT, "application", "main.py"), encoding="utf-8").read().lower()
    for word in ("client_secret", "refresh_token", "access_token", "rclone.conf\", \"w"):
        assert word not in src
