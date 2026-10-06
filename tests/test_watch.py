"""Tests for the folder watch (api/watch.py): new files, growing files, safety.

Runs the real router on a minimal FastAPI app; SHARE_PATH points to a temp folder.
"""

import os
import tempfile

# Session storage must not land in the default /tmp location: set before importing config.
os.environ.setdefault("UPLOAD_DIR", tempfile.mkdtemp(prefix="plotter-test-"))

import pytest  # noqa: E402
from api import watch  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

HEADER = "Time (min),Stress (MPa)\n"


@pytest.fixture
def share(tmp_path, monkeypatch):
    (tmp_path / "bench").mkdir()
    monkeypatch.setattr(watch, "SHARE_PATH", str(tmp_path))
    return tmp_path


@pytest.fixture
def client(request):
    app = FastAPI()
    app.include_router(watch.router, prefix="/api")
    c = TestClient(app)
    c.headers["X-Session-Id"] = f"test-{request.node.name}"
    return c


def poll(client, folder="bench"):
    res = client.post("/api/watch/poll", json={"folder": folder})
    assert res.status_code == 200, res.text
    return res.json()


def test_lists_subfolders(share, client):
    folders = client.get("/api/watch/folders").json()["folders"]
    assert folders == ["", "bench"]


def test_new_file_is_loaded_once(share, client):
    (share / "bench" / "run_01.csv").write_text(HEADER + "0,35\n1,30\n")
    first = poll(client)
    assert [f["filename"] for f in first["added"]] == ["run_01.csv"]
    assert first["added"][0]["row_count"] == 2
    second = poll(client)
    assert second["added"] == [] and second["updated"] == []


def test_growing_file_is_reloaded_in_place(share, client):
    path = share / "bench" / "live.csv"
    path.write_text(HEADER + "0,35\n")
    file_id = poll(client)["added"][0]["file_id"]

    # Acquisition still writing: the last row is incomplete and must be ignored.
    with open(path, "a") as f:
        f.write("1,30\n2,2")
    os.utime(path, (1, 1))  # force a new mtime even on coarse file systems
    updated = poll(client)["updated"]
    assert updated[0]["file_id"] == file_id, "same id → colour, legend, checkbox kept"
    assert updated[0]["row_count"] == 2

    with open(path, "a") as f:
        f.write("5\n")
    os.utime(path, (2, 2))
    assert poll(client)["updated"][0]["row_count"] == 3


def test_non_data_files_are_ignored(share, client):
    (share / "bench" / "capture.png").write_bytes(b"\x89PNG")
    (share / "bench" / "~$book.xlsx").write_bytes(b"lock")
    assert poll(client)["files_in_folder"] == 0


def test_folder_outside_share_is_refused(share, client):
    res = client.post("/api/watch/poll", json={"folder": "../"})
    assert res.status_code == 400


def test_read_complete_keeps_whole_lines(tmp_path):
    p = tmp_path / "a.csv"
    p.write_bytes(b"x,y\n1,2\n3,")
    assert watch.read_complete(str(p)) == b"x,y\n1,2\n"
