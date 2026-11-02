import re
from pathlib import Path

from django.conf import settings
from django.core.management import call_command


CODE_RE = re.compile(r'"code"\s*:\s*"([A-Z0-9_]+)"')


def project_path(*parts):
    return Path(settings.BASE_DIR).parent.joinpath(*parts)


def test_openapi_schema_matches_committed_file(tmp_path):
    generated = tmp_path / "openapi.yaml"
    call_command("spectacular", "--file", str(generated))

    committed = project_path("docs", "openapi.yaml")
    assert generated.read_text() == committed.read_text()


def test_every_view_error_code_is_documented():
    view_codes = set()
    for view_path in Path(settings.BASE_DIR).rglob("views.py"):
        if "__pycache__" in view_path.parts:
            continue
        view_codes.update(CODE_RE.findall(view_path.read_text()))

    docs = project_path("docs", "api.md").read_text()
    missing = sorted(code for code in view_codes if code not in docs)

    assert missing == []
