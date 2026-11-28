# HADES

Real-time consumer-drone detection and alerting pipeline: video source → detection → tracking → decision → alert outputs, with run logging and replay.

**This file is a signpost, not a manual.** Each section ends by pointing to the document that holds the detail.

---

## Quick start

Python 3.14 or newer. The checks in this repository are run on 3.14.

```bash
git clone https://github.com/XRainimatorX/HADES.git
cd HADES
python3.14 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,detect]"
git lfs install
git lfs pull --include="tests/fixtures/"
pytest
```

Large files (images, videos, model weights) are stored with Git LFS. LFS downloads are skipped by default (`GIT_LFS_SKIP_SMUDGE=1`). Everyone downloads `tests/fixtures/`; only the dataset and training work (C, G, H) also downloads `data/` and `models/`.

**A test that uses a fixture fails with a clear message if the file is missing or is still an LFS pointer.** Run `git lfs pull --include="tests/fixtures/"` and try again.

Run the pipeline (copy `configs/default.yaml` and set `detector.model_path` to a real weights file first; see `docs/handoff.md`):

```bash
hades-run --config my.yaml
hades-run --config my.yaml --clip tests/fixtures/drone_daylight_01.mp4 --max-frames 100
```

---

## Before every pull request

```bash
black --check src ml bench tests         # formatting
pylint src ml bench                      # style and obvious errors
mypy src ml bench                        # types
bandit -q -r src ml bench                # unsafe patterns
pytest --cov --cov-report=term-missing   # tests and coverage
```

All five run in CI on every pull request ([`.github/workflows/tests.yml`](.github/workflows/tests.yml)). **A red check means the pull request is not merged.** All settings are in [`pyproject.toml`](pyproject.toml).

---

## Working on a work package

```text
Branch    wp-<letter>/<short-topic>        e.g. wp-a/webcam-source
Scope     one work package per pull request; edit only the files your issue lists
Contract  never edit docs/spec.md or src/hades/contracts.py — ask the Project Owner
PR        link the issue; tick every item of its section 11 (Final Done Criteria)
Review    the Project Owner runs the integration acceptance and opens the produced
          files before merging
```

The task, the files and the done criteria of each work package are in its GitHub issue. The rules shared by all work packages are in the stage's "Shared Working Baseline" issue (Issue 0).

---

## Where to look

| You want to know | Go to |
|---|---|
| What HADES is and is not | [`docs/PRD.md`](docs/PRD.md) |
| The packet and function formats | [`docs/spec.md`](docs/spec.md) |
| How the system works now | [`docs/architecture.md`](docs/architecture.md) |
| How to take over, maintain and debug it | [`docs/handoff.md`](docs/handoff.md) |
| The project plan and stages | [`docs/plan.md`](docs/plan.md) |
| What each stage delivered and what to fix | [`docs/phases/`](docs/phases/) |
| How the three target numbers are measured | [`docs/test-plan.md`](docs/test-plan.md) |
| Why a decision was made | [`docs/decisions.md`](docs/decisions.md) |
| The development discipline | [`CONTRIBUTING.md`](CONTRIBUTING.md) |

---

## Repository layout

```text
src/hades/    everything that runs on the device; contracts.py is the single source of packet types
ml/           dataset, training, analysis, export (not deployed)
bench/        benchmark and stability runs; reports are written to bench/reports/
data/         classes, annotation guideline, dataset
models/       model weights (Git LFS)
configs/      default.yaml: thresholds, cooldown, model path, hardware
tests/        unit tests, integration/, fixtures/ (Git LFS)
hardware/     wiring diagrams, pin maps, BOM
```

Document templates used in this repository follow the document-system standard: living documents sit in the repository and change with the code; frozen records say so in their first line and point to the living document.
