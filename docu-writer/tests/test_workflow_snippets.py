"""template-workflow SKILL.md의 셸 명령을 그대로 꺼내 실행하는 회귀 테스트 (종단 시험 F2).

update 모드에서 ③을 건너뛰면 evidence.yaml이 없는데, 예전 ④ 명령은 실패하면서도
profile.yaml 한 줄짜리 approved.sha256을 남겨 근거가 잠기지 않았습니다.
"""
import re
import subprocess

import pytest

from conftest import ROOT

WORKFLOW = ROOT / "template/skills/template-workflow/SKILL.md"


def approve_snippet() -> str:
    text = WORKFLOW.read_text(encoding="utf-8")
    blocks = re.findall(r"```bash\n(.*?)```", text, re.S)
    found = [b for b in blocks if "approved.sha256" in b and "shasum -a 256 .docu-writer/profile.yaml" in b]
    assert len(found) == 1, "④ 승인 명령 블록을 하나만 찾아야 합니다"
    return found[0]


def run(snippet, cwd):
    return subprocess.run(["bash", "-c", snippet], cwd=cwd, capture_output=True, text=True)


@pytest.fixture
def ws(tmp_path):
    (tmp_path / ".docu-writer").mkdir()
    (tmp_path / ".docu-writer/profile.yaml").write_text("mode: update\n", encoding="utf-8")
    return tmp_path


def test_approve_without_evidence_leaves_no_hash_file(ws):
    proc = run(approve_snippet(), ws)
    assert proc.returncode != 0
    assert not (ws / ".docu-writer/approved.sha256").exists()


def test_approve_locks_both_files(ws):
    (ws / ".docu-writer/evidence.yaml").write_text("sections: []\n", encoding="utf-8")
    assert run(approve_snippet(), ws).returncode == 0
    lines = (ws / ".docu-writer/approved.sha256").read_text(encoding="utf-8").splitlines()
    assert [ln.split()[-1] for ln in lines] == [".docu-writer/profile.yaml", ".docu-writer/evidence.yaml"]
    assert run("shasum -c .docu-writer/approved.sha256", ws).returncode == 0


def test_every_step3_skip_says_who_writes_evidence():
    text = WORKFLOW.read_text(encoding="utf-8")
    rows = [ln for ln in text.splitlines() if ln.startswith("|") and "| ③" in ln]
    assert rows and all("evidence.yaml" in r for r in rows)
