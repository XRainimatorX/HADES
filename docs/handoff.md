# HADES Handoff — How the System Works at the End of Stage 2

Living document: update it whenever the chain, the commands or the maintenance procedures change. A Chinese version is in [`handoff.zh.md`](handoff.zh.md). The review of each Stage 2 work package is in [`phases/stage2_review_for_helpers.md`](phases/stage2_review_for_helpers.md) (frozen).

**Purpose.** To let someone who was not here in Stage 2 run the system, test it, maintain it and start Stage 3. **Stage 2 is not complete** (see section 9): everything here was checked on stand-in footage, not on the real clips, not on GitHub Actions and not on the target hardware.

---

## 1. What exists

```text
Works      A video sources (file, laptop camera, virtual Pi camera)
           B YOLO detector (official YOLOv8n weights, so it finds no drones)
           D virtual OLED in the terminal, web monitor
           E run log (events.jsonl, meta.json) and the replay source
           F benchmark (latency, frame rate, memory) and the shared test fixtures
           A main program that runs all of them on one clip or one camera
Skeleton   tracker (I), the decision layer (the state machine always says SCANNING and never
           sends a command), diagnostics, demo replay, integration check, error log, summary
Not yet    C dataset, G training, H error analysis, the Hailo model, the real Pi camera,
           the real OLED, the LED and buzzer drivers
```

## 2. How a frame travels

```text
A source.read()          FramePacket       frame_id, timestamp (monotonic ns), image, source_id
        |
B detector.detect()      DetectionPacket   same frame_id and timestamp, detections (tuple),
        |                                  inference_ms, t_detect
        |  (no tracker yet: an empty TrackingPacket is handed on)
decision skeleton        StateSnapshot     state SCANNING, no command
        |
E telemetry.record()     events.jsonl      one line per packet: frame, detection, state
D display, monitor       terminal screen and web page show the latest packets

Stage 2 shortcut         When a frame holds a detection, the main loop itself sends the configured
                         alert to the alert mock (LED on); the first empty frame switches it off.
                         Stage 4 moves this into the decision layer (decisions 12, 16, 17).
```

**Packet formats are frozen in `docs/spec.md` and `src/hades/contracts.py` (schema 0.2).** Multi-item fields are tuples; the frame image is read-only; the schema version is always read from `contracts.SCHEMA_VERSION`.

## 3. Modules

| File | Does | Depends on | Threads |
|---|---|---|---|
| `contracts.py` | Packets, state names, interfaces | nothing | none |
| `config.py` | `load_config()`, `validate_config()`, `resolve_path()` | contracts, PyYAML | none |
| `sources.py` | The three sources | contracts, OpenCV | one camera thread per live source |
| `detect.py` | `UltralyticsDetector` | contracts, ultralytics (extra `detect`) | none |
| `decide.py` | State machine skeleton | contracts | none |
| `alert.py` | `format_lines`, `VirtualOledDisplay`, `MockAlert` | contracts | none |
| `monitor.py` | `WebMonitor` | contracts, OpenCV | one server thread |
| `telemetry.py` | `Telemetry`, `ReplaySource`, `file_sha256`, `git_info` | contracts, OpenCV | one writer thread (not a daemon) |
| `pipeline.py` | `run_pipeline()`, `main()` | all of the above | the main thread |
| `bench/benchmark.py` | `run_benchmark()`, `write_report()` | config, sources, detect | none |

**The whole program uses four threads at most** (main, camera, monitor server, log writer), as Issue 0 requires. Time is always `time.monotonic_ns()`, never wall-clock, so latencies are differences of one clock.

## 4. Run it

```bash
python3.11 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,detect]"
git lfs pull --include="tests/fixtures/"
cp configs/default.yaml my.yaml     # then set detector.model_path to tests/fixtures/test_model.pt
hades-run --config my.yaml --clip tests/fixtures/drone_daylight_01.mp4 --max-frames 100
hades-run --config my.yaml --monitor-port 8080     # the configured source; web page on port 8080
```

**`configs/default.yaml` holds a placeholder model path (`models/<model_name>/model.pt`) on purpose:** there is no trained model yet. Copy the file and name a real weights file, as above; the run stops with a message that names the missing file otherwise.

```text
Output   runs/<run_id>/meta.json     git commit and dirty flag, model and config SHA-256, source,
                                     hardware name
         runs/<run_id>/events.jsonl  one JSON line per packet
         The last line printed says how many frames ran and where the log is.
Stop     Ctrl+C: the log is closed first (exit code 130)
Config   configs/default.yaml; the source type is picam | webcam | video; a missing or mistyped
         setting is named in the error message
```

`hades-replay` is declared as an entry point but `replay_main()` is still a skeleton (work package M). `ReplaySource(run_dir)` already plays a recorded run's original video in code.

## 5. Test and measure

```bash
pytest --cov --cov-report=term-missing         # every test; the coverage is reported, not yet enforced
pytest tests/integration -q                     # the whole chain on a clip
python -c "from bench.benchmark import run_benchmark, write_report; \
r = run_benchmark('latency', 'my.yaml', 'tests/fixtures/drone_daylight_01.mp4'); \
print(write_report(r, 'bench/reports/'))"        # kinds: latency | fps | memory
```

```text
What the benchmark kinds report   latency: median, p95 (nearest rank) and max of t_detect - timestamp
                                  fps: average and minimum
                                  memory: resident memory at the start, at the end and at the peak
Every report                      names the hardware (config hardware.name) and the SHA-256 of the model
How to read a figure              Only against the same hardware, model and clip (docs/test-plan.md,
                                  section 9). A figure from a stand-in or from the wrong machine is
                                  not a measurement.
```

**Commit a benchmark report only when it is real:** the real clip, the target hardware named correctly, and the file opened and read.

## 6. Debugging

| Symptom | Likely cause | Look at |
|---|---|---|
| A test says a fixture is missing or is an LFS pointer | The clips or `test_model.pt` were not pulled | `git lfs pull --include="tests/fixtures/"` |
| `ModuleNotFoundError: ultralytics` | The `detect` extra is not installed | `pip install -e ".[dev,detect]"` |
| The process does not exit after a run | `Telemetry.end_run()` was never called, the writer thread waits | The caller must close the log in a `finally` |
| `events.jsonl` has fewer lines than 3 × frames | The run was cut off or a write error occurred | The exit message; `end_run()` reports the first write error |
| Frame rate far below the source rate | Detection is slower than the source; the live sources skip frames on purpose | `inference_ms` in the detection records; `fps` benchmark |
| `RuntimeError` naming the video file | The file path in the configuration is wrong or the file is unreadable | `source.uri`; relative paths resolve from the repository root |
| The web page does not load from another computer | The monitor listens on 127.0.0.1 only | `WebMonitor(host=...)`; do this knowingly |
| Webcam black or missing on Windows | Windows needs the DirectShow backend (set in code, untested) | The camera index; another program using the camera |
| Every detection list is empty | Expected with the official YOLOv8n: no drone class | Not a fault; a trained model is Stage 3 |

## 7. Maintenance

**Daily.** The checks of [`phases/stage2_review_for_helpers.md`](phases/stage2_review_for_helpers.md) section 12 (black, pylint, mypy, bandit, pytest, run from another folder). A red CI run is fixed before anything else is merged.

**Changing a packet format (the contract).** The formats are frozen; a change is a contract change, not a refactor.

```text
1  Write down what changes and why, and who is affected (the table in the review, section 7, is
   the model).
2  Obtain the Project Owner's approval; contracts.py has CODEOWNERS.
3  In one pull request: docs/spec.md, src/hades/contracts.py, configs/default.yaml,
   data/classes.yaml, tests/fixtures/sample_packets.jsonl, tests/test_contracts.py; raise the
   schema version everywhere (it is read from contracts.SCHEMA_VERSION).
4  Tell every work-package owner; the contract tests fail on any disagreement between the files.
```

**Changing the model.** `detector.model_path` names the weights; the run log stores their SHA-256, so every run says which model it used. A model file replaces the old one in `models/<name>/` through Git LFS (never the original videos, decision 2). Re-run the benchmark and keep the old report next to the new one.

**Moving to the Hailo accelerator (Stage 3 and later).** The detector interface is two functions, `load()` and `detect()`, and the tests call only those. A Hailo detector (HEF model, returned boxes converted to `Detection`) is a second class behind the same functions; do not change the packets. Check that the class names match `contracts.CLASS_NAMES`, that boxes are in original-frame pixels, and that `inference_ms` is the accelerator's time. **None of this exists or was tested yet.**

**Dependencies.** Versions are pinned in `pyproject.toml`. Raise them one at a time and run the whole check; the pins were verified on Python 3.11 only.

## 8. Stage 3 — what to build on

| WP | Builds on | Starts from | Counts as done when |
|---|---|---|---|
| G Training | C's `dataset_v1`; `ml/train.py`, `ml/export.py`; the benchmark | An exported model that `UltralyticsDetector` loads | The exported model runs through `hades-run` and `tests/integration`; the benchmark report is real (section 5) |
| H Error analysis | Run logs of labelled clips; `ml/analysis.py` | `events.jsonl` of a run on a labelled clip | False positives and false negatives are listed per frame from the log; **it needs the real clips and labels** |
| I Tracking | `track.py`; `DetectionPacket`; `contracts.TrackingPacket` | The empty `TrackingPacket` the main loop passes today | The main loop passes the tracker's output to the decision skeleton; the tracker is tested with scripted detections; its states obey the confirm/lost frames in the configuration |
| C Dataset | `ml/dataset.py`; the fixtures | Review report, section 5 | Issue C Final Done Criteria; **it blocks G** |

**Before Stage 3 starts** the checklist in section 10 should be ticked.

## 9. What was not verified

```text
Real footage       The three clips are not committed; every result is from stand-in clips and the
                   official YOLOv8n weights
GitHub Actions     tests.yml has never run on GitHub (it runs on pull requests and on pushes to main)
Hardware           No run on the Raspberry Pi 5 with the AI HAT+; the Hailo path does not exist;
                   no real camera, OLED, LED or buzzer
Windows            The DirectShow camera path is written but not run
Webcam             The webcam test is skipped without a camera
Accuracy           Detection accuracy, range and false alarm rate have not been measured
Laptop figures     No benchmark was run on the Project Owner's laptop; the one report made here was
                   on stand-in footage and was not committed
Open decisions     Ten-week schedule gap; the two-person fallback; thresholds of the three numbers
                   and of the stability run; the list of error codes; "G. Demo Success Criteria";
                   Flask or the standard-library server for the monitor
```

## 10. Stage 3 readiness checklist

```text
□ The three clips and test_model.pt are committed through Git LFS (Project Owner)
□ tests.yml has run on GitHub on review_branch and is green with the real fixtures
□ The ten-week gap and the Stage 3 issues (G, H, I) are decided and written
□ Issue 0 addendum approved (the approval channel, the contract-change process, the defaults)
□ WP C is started, because G cannot start without a dataset
□ A real benchmark report on the target hardware exists, or is scheduled with a date
□ Someone who did not write this document can answer "what do I do in Stage 3" from this file,
  the issues and the review alone
```

## 11. In one sentence

> The chain A → B → decision skeleton → E → D runs end to end from one command and writes a complete, replayable log, with the packet formats frozen at schema 0.2 and every part behind the interface its issue names — what Stage 3 needs next is the real fixtures, the dataset, a tracker and a trained model, and what no one has yet checked is the real footage, GitHub Actions and the hardware.
