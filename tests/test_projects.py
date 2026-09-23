import json
import re
from pathlib import Path

import pytest

from local_ocr.common import AppError, Cancelled
from local_ocr.projects import (
    ProjectOptions,
    checked_text,
    estimate_tokens,
    export_project,
    fenced_code,
    read_source,
    scan_project,
    secret_reason,
    split_context,
)


def put(root, path, text="print('hola')\n"):
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    return target


def test_scan_filters_dependencies_secrets_and_respects_nested_gitignore(tmp_path):
    put(tmp_path, "src/main.py")
    put(tmp_path, "src/.gitignore", "*.tmp\n!keep.tmp\n!allowed.txt\n")
    put(tmp_path, ".gitignore", "*.txt\nignored/\n")
    for path in (
        "src/gone.tmp",
        "notes.txt",
        "ignored/a.py",
        "node_modules/a.js",
        "bin/test.cs",
        "vendor/a.php",
        ".env",
        "keys/private.pem",
        "yarn.lock",
        ".git/config",
    ):
        put(tmp_path, path)
    put(tmp_path, "src/keep.tmp")
    put(tmp_path, "src/allowed.txt")
    put(tmp_path, "config.py", 'password = "real-looking-secret"')
    result = scan_project(tmp_path)
    paths = {f["path"] for f in result["files"]}
    assert paths == {".gitignore", "src/.gitignore", "src/main.py", "src/keep.tmp", "src/allowed.txt"}
    assert any(f["path"] == "config.py" for f in result["excluded"])


def test_empty_project(tmp_path):
    scan = scan_project(tmp_path)
    assert scan["files"] == []
    with pytest.raises(AppError):
        export_project(scan, [], tmp_path / "out")


def test_lockfiles_opt_in_and_custom_exclusions(tmp_path):
    put(tmp_path, "package-lock.json", "{}")
    put(tmp_path, "src/main.js")
    result = scan_project(tmp_path, ProjectOptions(include_locks=True, extra_excludes="src/"))
    assert [f["path"] for f in result["files"]] == ["package-lock.json"]


@pytest.mark.parametrize(
    "text",
    [
        'API_KEY = "sk-proj-' + "a" * 32 + '"',
        'connection = "postgresql://user:password@localhost/db"',
        '{"ClientSecret": "not-a-placeholder-secret"}',
        '"Server=localhost;Password=secret123;Database=test"',
        "-----BEGIN PRIVATE KEY-----\nEXAMPLE NOT REAL\n-----END PRIVATE KEY-----",
    ],
)
def test_secret_detection(text):
    assert secret_reason(text)


def test_placeholder_credentials_allowed():
    assert secret_reason('api_key = "YOUR_KEY_HERE"') is None


def test_unicode_utf16_and_binary(tmp_path):
    path = tmp_path / "código.cs"
    path.write_bytes('public string año = "El Salvador";'.encode("utf-16"))
    assert "año" in read_source(path, 1024)[0]
    bad = tmp_path / "data.txt"
    bad.write_bytes(b"abc\0def")
    with pytest.raises(AppError, match="binario"):
        read_source(bad, 1024)


def test_file_size_limit(tmp_path):
    put(tmp_path, "big.py", "a" * 1200)
    result = scan_project(tmp_path, ProjectOptions(max_file_bytes=1024))
    assert not result["files"]
    assert "tamaño" in result["excluded"][0]["reason"]


def test_changed_source_not_exported(tmp_path):
    root = tmp_path / "project"
    put(root, "main.py")
    result = scan_project(root)
    put(root, "main.py", "changed = True")
    with pytest.raises(AppError, match="Cambió"):
        export_project(result, ["main.py"], tmp_path / "out")
    assert not (tmp_path / "out").exists()


def test_traversal_and_symlinks_rejected(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    outside = put(tmp_path, "outside.py")
    with pytest.raises(AppError, match="Ruta"):
        checked_text(root, {"path": "../outside.py"}, ProjectOptions())
    try:
        (root / "linked.py").symlink_to(outside)
    except OSError:
        pytest.skip("No hay permiso de symlink en este sistema")
    scan = scan_project(root)
    assert scan["files"] == []
    assert "Enlace" in scan["excluded"][0]["reason"]


def test_cancel_propagates_from_nested_walk(tmp_path):
    root = tmp_path / "project"
    for i in range(5):
        put(root, f"nested/{i}.py")
    cancel = tmp_path / "stop.cancel"

    def progress(_):
        cancel.touch()

    with pytest.raises(Cancelled):
        scan_project(root, progress=progress, cancel_file=cancel)


def test_fence_and_chunk_budget_preserve_source():
    content = "```python\n" + "ábc😀 = 1\n" * 3000 + "```\n"
    assert fenced_code(content).startswith("````text\n")
    files = [({"path": "src/ñ.py", "language": "python"}, content)]
    chunks = split_context(files, 1000)
    assert len(chunks) > 2
    recovered, offset = "", 0
    for part in chunks:
        assert estimate_tokens(part) <= 1000
        match = re.search(r"Caracteres (\d+) a (\d+)", part)
        start, end = map(int, match.groups())
        assert start == offset
        body = part.split("(fin exclusivo).\n\n", 1)[1]
        body = body.split("\n", 1)[1]
        recovered += body[: end - start]
        offset = end
    assert recovered == content


def test_export_atomic_unique_and_no_source_changes(tmp_path):
    root = tmp_path / "project"
    path = put(root, "main.py")
    original = path.read_bytes()
    scan = scan_project(root)
    one = export_project(scan, ["main.py"], tmp_path / "out")
    two = export_project(scan, ["main.py"], tmp_path / "out")
    assert one["output"] != two["output"]
    output = Path(one["output"])
    assert "print('hola')" in (output / "proyecto_completo.md").read_text(encoding="utf-8")
    assert (output / "resumen_proyecto.md").is_file()
    assert json.loads((output / "informe.json").read_text())["files"][0]["path"] == "main.py"
    assert path.read_bytes() == original
    assert not list((tmp_path / "out").glob(".localocr-*"))


def test_output_folder_is_excluded(tmp_path):
    put(tmp_path, "main.py")
    put(tmp_path, "results/old.md", "Generated output")
    result = scan_project(tmp_path, exclude_roots=[tmp_path / "results"])
    assert [f["path"] for f in result["files"]] == ["main.py"]


def test_selection_injection_rejected(tmp_path):
    put(tmp_path, "main.py")
    scan = scan_project(tmp_path)
    with pytest.raises(AppError, match="selección"):
        export_project(scan, ["unknown.py"], tmp_path / "out")


def test_empty_source_gets_exported():
    chunks = split_context([({"path": "empty.py", "language": "python"}, "")], 1000)
    assert "empty.py" in chunks[0]


def test_exclude_root_cannot_swallow_project(tmp_path):
    with pytest.raises(AppError, match="salida"):
        scan_project(tmp_path, exclude_roots=[tmp_path])
