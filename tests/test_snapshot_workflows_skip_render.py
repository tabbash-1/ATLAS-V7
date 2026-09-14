from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_WORKFLOWS = (
    ".github/workflows/atlas-production-snapshot.yml",
    ".github/workflows/atlas-swing-targets.yml",
    ".github/workflows/atlas-canonical-outcome-snapshot.yml",
    ".github/workflows/atlas-adaptive-evidence-outcomes.yml",
    ".github/workflows/atlas-quick-trade-outcomes.yml",
    ".github/workflows/scenario-evidence-pipeline.yml",
    ".github/workflows/atlas-offline-production-path-settlement.yml",
    ".github/workflows/atlas-paper-analyst-forward.yml",
)


def test_snapshot_writer_commits_skip_render():
    offenders = []
    checked = 0
    for rel in SNAPSHOT_WORKFLOWS:
        path = ROOT / rel
        text = path.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), 1):
            if "git commit" not in line or "[skip ci]" not in line:
                continue
            checked += 1
            if "[skip render]" not in line:
                offenders.append(f"{rel}:{lineno}: {line.strip()}")
    assert checked >= 9, f"expected at least 9 snapshot commit sites, found {checked}"
    assert not offenders, "snapshot commits can redeploy Render:\n" + "\n".join(offenders)


if __name__ == "__main__":
    test_snapshot_writer_commits_skip_render()
    print("SNAPSHOT_RENDER_SKIP_CONTRACT_OK")
