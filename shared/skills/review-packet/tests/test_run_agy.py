"""run_agy.sh 테스트 — 가짜 agy 실행 파일로 인자 순서와 종료 코드를 검증한다."""
import os
import pathlib
import subprocess

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "run_agy.sh"


def make_fake_agy(bindir: pathlib.Path, log: pathlib.Path, output: str, exit_code: int) -> None:
    agy = bindir / "agy"
    agy.write_text(
        "#!/bin/sh\n"
        ": > \"$FAKE_AGY_LOG\"\n"
        "for a in \"$@\"; do printf '%s\\n' \"$a\" >> \"$FAKE_AGY_LOG\"; done\n"
        f"printf '{output}'\n"
        f"exit {exit_code}\n",
    )
    agy.chmod(0o755)


def run_agy(bindir: pathlib.Path, repo, packet, out, log: pathlib.Path,
            cwd=None, env_extra: dict | None = None) -> subprocess.CompletedProcess:
    env = {**os.environ, "PATH": f"{bindir}{os.pathsep}{os.environ['PATH']}",
           "FAKE_AGY_LOG": str(log)}
    for key, value in (env_extra or {}).items():
        if value is None:  # 값이 None이면 그 환경 변수를 지운다(기본값 동작 확인용)
            env.pop(key, None)
        else:
            env[key] = value
    return subprocess.run(["bash", str(SCRIPT), str(repo), str(packet), str(out)],
                          capture_output=True, text=True, env=env, timeout=30, cwd=cwd)


def setup(tmp_path: pathlib.Path):
    bindir = tmp_path / "bin"
    bindir.mkdir()
    repo = tmp_path / "repo"
    repo.mkdir()
    packet = tmp_path / "packet.md"
    packet.write_text("꾸러미 첫 줄\n꾸러미 둘째 줄\n")
    return bindir, repo, packet, tmp_path / "args.log", tmp_path / "result.md"


def test_argument_order(tmp_path):
    """인자 순서가 --sandbox --mode plan --print <꾸러미 내용>인지 (--print가 맨 뒤, 지시문이 바로 뒤)."""
    bindir, repo, packet, log, out = setup(tmp_path)
    make_fake_agy(bindir, log, output="FAKE RESULT\\n", exit_code=0)
    result = run_agy(bindir, repo, packet, out, log)
    assert result.returncode == 0, result.stderr
    lines = log.read_text().splitlines()
    assert lines[:4] == ["--sandbox", "--mode", "plan", "--print"]
    assert lines[4:] == ["꾸러미 첫 줄", "꾸러미 둘째 줄"]
    assert out.read_text() == "FAKE RESULT\n"


def test_empty_output_exits_2(tmp_path):
    """agy가 아무것도 출력하지 않으면(성공해도) 종료 코드 2."""
    bindir, repo, packet, log, out = setup(tmp_path)
    make_fake_agy(bindir, log, output="", exit_code=0)
    result = run_agy(bindir, repo, packet, out, log)
    assert result.returncode == 2
    assert "비어" in result.stderr


def test_agy_exit_code_passes_through(tmp_path):
    """agy의 종료 코드를 그대로 돌려주는지."""
    bindir, repo, packet, log, out = setup(tmp_path)
    make_fake_agy(bindir, log, output="partial\\n", exit_code=3)
    result = run_agy(bindir, repo, packet, out, log)
    assert result.returncode == 3


def test_runs_inside_repo(tmp_path):
    """cd <저장소> 안에서 agy를 부르는지."""
    bindir, repo, packet, log, out = setup(tmp_path)
    marker = repo / "here.txt"
    marker.write_text("repo marker\n")
    agy = bindir / "agy"
    agy.write_text(
        "#!/bin/sh\n"
        "for a in \"$@\"; do :; done\n"
        "if [ -f here.txt ]; then printf 'IN-REPO\\n'; fi\n"
        "exit 0\n",
    )
    agy.chmod(0o755)
    result = run_agy(bindir, repo, packet, out, log)
    assert result.returncode == 0, result.stderr
    assert out.read_text() == "IN-REPO\n"


def test_relative_paths_resolve_from_caller(tmp_path):
    """호출 위치 ≠ 저장소일 때 상대 경로 꾸러미·결과가 호출 위치 기준으로 풀리는지."""
    bindir, repo, packet, log, out = setup(tmp_path)
    make_fake_agy(bindir, log, output="REL OK\\n", exit_code=0)
    caller = tmp_path / "caller"   # 꾸러미·결과는 여기에, 저장소는 다른 곳에
    caller.mkdir()
    (caller / "packet.md").write_text("상대 꾸러미\n")
    result = run_agy(bindir, repo, "packet.md", "result.md", log, cwd=caller)
    assert result.returncode == 0, result.stderr
    assert (caller / "result.md").read_text() == "REL OK\n"
    assert not (repo / "result.md").exists()          # 저장소 안에 생기지 않음
    assert "상대 꾸러미" in log.read_text()             # 꾸러미 내용이 그대로 전달됨


def test_relative_out_in_missing_dir_exits_2(tmp_path):
    """결과 파일의 디렉터리가 없으면 종료 코드 2."""
    bindir, repo, packet, log, out = setup(tmp_path)
    caller = tmp_path / "caller"
    caller.mkdir()
    (caller / "packet.md").write_text("꾸러미\n")
    result = run_agy(bindir, repo, "packet.md", "no-such-dir/result.md", log, cwd=caller)
    assert result.returncode == 2
    assert "디렉터리" in result.stderr


def test_packet_over_env_limit_exits_2(tmp_path):
    """꾸러미가 AGY_MAX_PACKET_BYTES를 넘으면 agy를 부르지 않고 종료 코드 2."""
    bindir, repo, packet, log, out = setup(tmp_path)
    packet.write_text("x" * 300 + "\n")
    result = run_agy(bindir, repo, packet, out, log, env_extra={"AGY_MAX_PACKET_BYTES": "200"})
    assert result.returncode == 2
    assert "상한" in result.stderr
    assert not log.exists()                            # agy는 호출되지 않았다


def test_default_limit_is_200000(tmp_path):
    """환경 변수가 없으면 기본 상한 200000바이트."""
    bindir, repo, packet, log, out = setup(tmp_path)
    packet.write_text("x" * 200_001)
    result = run_agy(bindir, repo, packet, out, log, env_extra={"AGY_MAX_PACKET_BYTES": None})
    assert result.returncode == 2
    assert "200000" in result.stderr
