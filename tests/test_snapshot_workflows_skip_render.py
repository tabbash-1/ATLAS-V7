from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"


def test_snapshot_writer_commits_skip_render():
    offenders = []
    checked = 0
    for path in sorted(WORKFLOWS.glob("*.yml")):
        text = path.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), 1):
            stripped = line.strip()
            if not stripped.startswith("git commit") or "[skip ci]" not in stripped:
                continue
            checked += 1
            if "[skip render]" not in stripped:
                rel = path.relative_to(ROOT)
                offenders.append(f"{rel}:{lineno}: {stripped}")
    assert checked > 0, "expected snapshot/status writer commit sites"
    assert not offenders, "snapshot commits can redeploy Render:\n" + "\n".join(offenders)


if __name__ == "__main__":
    test_snapshot_writer_commits_skip_render()
    print("SNAPSHOT_RENDER_SKIP_CONTRACT_OK")
