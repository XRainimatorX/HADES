# HADES Test Plan

Test Plan v1.0. It sets **what is tested, how, and what does not count as tested or measured**, including how the three target numbers are measured.

Living document: updated as the test infrastructure changes.

---

## 1. What this document governs

```text
Governs   what is tested, the duty of each layer, the minimum for each layer, what is forbidden,
          what makes a test valid, and how the three target numbers are measured
Does not  how an individual test is written; that is in the Tests section of each issue
```

**Any dispute about testing is decided by this document;** the test requirements in an issue may not contradict it.

## 2. Test functions, not products

```python
# Wrong: tests what happens to be on disk
def test_something():
    with open("runs/x/events.jsonl") as f:
        assert "frame" in f.read()

# Right: tests your program
def test_something(tmp_path):
    run_dir, records = write_run(tmp_path, metadata, packets)   # calls the code
    assert records[0]["type"] == "frame"
```

**A test that reads a file passes falsely when a leftover file exists and fails falsely when the file is overwritten; in both cases the program under test was not run.** Tests write into a temporary folder and read back what they wrote.

Self-check, also run in CI:

```bash
grep -rn "open(" tests/ | grep -E "runs/|bench/reports"   # a match means a test reads an output folder
```

## 3. Layers and duties

| Layer | Where | Tests what | Does not test | Runs |
|---|---|---|---|---|
| Unit | `tests/test_*.py` | One function's return value | Interaction between modules | Every push |
| Contract | `tests/test_contracts.py`, `tests/test_config.py` | `docs/spec.md`, `contracts.py`, `configs/default.yaml` and `data/classes.yaml` agree | Business logic | Every push |
| Integration | `tests/integration/` | The whole chain runs on a fixture clip and the files it writes are correct | Speed | Every push |
| Benchmark | `bench/benchmark.py` | Latency, frame rate, memory on a fixed clip | Correctness | On demand; reports in `bench/reports/` |
| End to end | Stage 4 onward | The demo path with the real outputs | Internals | Before a merge to a release |

**The contract layer is the one most often missed, and it is the only insurance for parallel work.** Without it every team's data matches but the interfaces do not.

## 4. Minimum for each layer

```text
Unit         Every public function: a normal case and a boundary case; every error the function
             documents is raised
Contract     Every frozen field is asserted to exist, in the order of docs/spec.md; every function
             signature is called; multi-item fields are tuples
Integration  Run the whole chain, then open the files it wrote and compare their contents with
             what was fed in
Benchmark    A report is produced for each kind; the figures are checked against known timings
```

## 5. Forbidden

```text
❌ A test may not read runs/ or bench/reports/
❌ A test may not depend on what a previous test left behind
❌ A test may not depend on the order of execution
❌ A test may not check only structure where a value can be checked (section 6)
❌ A test may not do I/O when its module is imported
❌ A test may not use sample data of its own where a shared fixture exists (section 7)
```

## 6. Values, not only structure

A test that only looks for a keyword cannot catch a wrong number:

```python
# Not enough: structure only
assert "latency" in report

# Needed: the value, against a known timing
assert report.result == {"median_ms": 10.5, "p95_ms": 19.0, "max_ms": 20.0}
```

**The criterion: would this test fail on defective code?** A test that cannot fail is a test that passes, not a valid test. Check by breaking the code on purpose (change a constant, remove a line) and confirming a test fails.

## 7. Fixtures

```text
Path      tests/fixtures/
Files     drone_daylight_01.mp4   a short clip with one drone in view
          no_drone_01.mp4         a short clip of empty sky
          head_walk_01.mp4        a short clip filmed from a helmet while walking
          sample_packets.jsonl    one example of each Stage 2 packet, in the run-log format
          test_model.pt           the official YOLOv8n weights (no drone class)
When      Committed by the Project Owner before the work packages start
Storage   Git LFS for the clips and the weights; sample_packets.jsonl is an ordinary file
Rule      A test that uses a fixture first checks the file is real and not an LFS pointer
          (conftest.require_real_video / require_real_file) and fails with a clear message
```

**Letting each team write its own sample inside its tests means there is no shared contract.** The fixtures change with the contract, in the same pull request.

## 8. The three target numbers

| Number | What it is | How it is measured | From | Threshold |
|---|---|---|---|---|
| End-to-end latency | Time from capture of a frame to the command that reacts to it | `t_command − timestamp` of the `ActuatorCommand`; median, 95th percentile and maximum over a fixed clip | Stage 4 | TBD |
| Effective detection range | The greatest distance at which a drone is detected steadily on a £2,000-class camera | Clips with the distance marked; the largest marked distance at which the drone is detected steadily (the number of frames that count as "steadily" is TBD); `BenchmarkReport` kind `range` | Stage 4 | TBD |
| False alarm rate | How often HADES alerts when no drone is there, close up and with distractors (birds, backlight, branches) | Alerts per minute of footage with no drone; `BenchmarkReport` kind `false_alarm` | Stage 4 | TBD |

**What Stage 2 measures:** only the time from capture to the end of detection (`t_detect − timestamp`), frame rate and memory, because the decision and alert stages do not exist yet. These are `BenchmarkReport` kinds `latency`, `fps` and `memory` (work package F). They are the first honest figures, not the target numbers.

**The first thresholds are not set.** They are set from the first benchmark run on the target hardware (Raspberry Pi 5 with the AI HAT+) on real footage, and from "G. Demo Success Criteria", which is not yet defined (see `docs/plan_appendix.md`, item 1.5).

## 9. What does not count as measured

```text
❌ A figure from a stand-in source, a stand-in detector or a synthetic clip
❌ A figure from a clip that is not the fixed clip named in the report
❌ A figure measured on other hardware than the one named in the report's "hardware" field
❌ A figure from the cloud environment or a development laptop presented as the target hardware
❌ A report that has no hardware name or no model fingerprint (model_sha256)
❌ A run that was not opened and read: a report file that merely exists proves nothing
❌ "No detections" from the official YOLOv8n weights, which have no drone class: it proves the
   chain runs and the log is complete, not that drones are detected
```

Results are only comparable on the same hardware, the same model and the same clip.

## 10. Coverage

```text
Whole project      at least 90 % (CONTRIBUTING, Step 4); reported on every run
New code           must not lower the coverage of the project
```

Coverage is reported in CI. The 90 % gate is **not yet enforced** (`--cov-fail-under=90` is not set); enabling it is proposed for the end of Stage 2. Exceptions are written in `pyproject.toml` with the reason.

## 11. When a thing counts as tested

```text
1. The test calls the function; it does not read a file
2. The test fails on defective code (checked by breaking the code)
3. The test does not depend on execution order or on leftover state
4. It passes in a clean environment (the CI container)
5. It passes when run from another working directory
```

Check for 5:

```bash
cd /tmp && pytest <repository>/tests
```

## 12. Status at the end of Stage 2

| Part | Tested by | Real fixtures needed |
|---|---|---|
| Contract (spec, contracts, config, classes) | `tests/test_contracts.py`, `tests/test_config.py` | No |
| A video sources | `tests/test_sources.py` (the webcam test is skipped without a camera; the camera thread is tested with a fake capture) | Yes, the three clips |
| B detector | `tests/test_detect.py` (real YOLOv8n on the clips; scripted fake YOLO for filtering) | Yes, the clips and `test_model.pt` |
| C dataset | **Not tested: not started** | — |
| D screen and monitor | `tests/test_alert.py`, `tests/test_monitor.py` | Yes, one clip |
| E run log and replay | `tests/test_telemetry.py` | Yes, one clip |
| F benchmark | `tests/test_benchmark.py` | No (stand-ins); acceptance needs the clips |
| Decision skeleton | `tests/test_decide.py` | No |
| Main program | `tests/test_pipeline.py`, `tests/integration/` | Integration: yes |

Tests that need a real fixture fail with a clear message until the Project Owner commits the file. **The detection accuracy, range and false alarm rate are not measured at all yet.**

## 13. In one sentence

> Test functions rather than products, check values rather than structure, and have the fixtures ready before the work starts — without all three, integration produces "every part passed its own check and the whole is broken"; in Stage 2 the chain runs and logs completely on stand-in footage, while the three target numbers have no thresholds and no real measurement yet.
