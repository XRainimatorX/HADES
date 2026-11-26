# Stage 2 — Review of the Work Packages, for the Helpers

Stage 2 review report. **This document is the frozen record of the Stage 2 review; it is not updated after this version.** How the system works now is in [`../architecture.md`](../architecture.md) and [`../handoff.md`](../handoff.md). A Chinese version is in [`stage2_review_for_helpers.zh.md`](stage2_review_for_helpers.zh.md).

**Status: Stage 2 is not complete.** Work packages A, B, D, E and F have code and tests that pass on stand-in footage; work package C has not started; the real fixtures (the three clips and the model file) are not yet committed, so no work package has been accepted against them.

**What this report is for.** Each section below is about one work package. It says what was delivered, checks it against the issue's Final Done Criteria item by item, says what was good, what was missing, **what the integration changed in your files and why**, and what is left for you. Read your own section and then section 6 (common problems) and section 12 (the checklist before every pull request). This report reviews the work and the process, not the people.

---

## 1. Stage 2 at a glance

| WP | Owner | Issue | State before the integration | State now | Left |
|---|---|---|---|---|---|
| A Video input | dougleungch | [#3](https://github.com/XRainimatorX/HADES/issues/3) | Code did not match the issue; no tests | Matches the issue; 25 tests (1 skipped without a camera) | Real-camera check, real-clip acceptance |
| B Detection | dougleungch | [#4](https://github.com/XRainimatorX/HADES/issues/4) | Code matched the issue; no tests | 48 tests, 99 % coverage | Accuracy (Stage 3), real-clip acceptance |
| C Dataset | Greencslethan | [#5](https://github.com/XRainimatorX/HADES/issues/5) | **Not started** | Not started | Everything |
| D Screen and monitor | Greencslethan | [#6](https://github.com/XRainimatorX/HADES/issues/6) | Worked; extra files and window code; tests could not run | Matches the issue; 23 + 14 tests | Real-clip acceptance, Flask question |
| E Run log and replay | Greencslethan | [#7](https://github.com/XRainimatorX/HADES/issues/7) | Good design; tests could not run | Matches the issue; 45 tests | Real-clip acceptance |
| F Test harness and benchmark | Project Owner | [#8](https://github.com/XRainimatorX/HADES/issues/8) | Not started | Done; 100 % coverage | Acceptance on real clips |

## 2. How this review was done

```text
Source            the helper branches doug and Greencslethan, as pushed (11/15 to 11/22), and the
                  merged review_branch
CI history        4 helper pushes, all 4 failed at the first check (black --check); pylint, mypy,
                  bandit and pytest were skipped, so no helper test had ever run in CI
Checks on the     black --check, pylint, mypy, bandit and pytest with coverage, on Python 3.11,
whole project     all five pass after the integration (pytest: 305 passed, 1 skipped (no camera), 1 expected failure, 94 % coverage)
Test validity     each fixed or new test was checked by breaking the code on purpose (docs/test-plan.md,
                  section 6): a test that did not fail got a better test
Footage           the three clips and the model are not committed. Everything was checked with the
                  official YOLOv8n weights and synthetic stand-in clips kept outside git. Results
                  that depend on real footage are marked "re-run on the real clip".
```

**Nothing in this report is a measurement of detection accuracy, range or false alarm rate.** None of those exist yet.

---

## 3. WP A — Video input (dougleungch, Issue #3)

### What was delivered

`src/hades/sources.py` with `VideoFileSource(video_path)`, `WebcamSource(camera_index)` and `VirtualPiCamSource(video_path)`; no tests; commits on 11/15.

### Done criteria of the issue

| # | Criterion | Before | Now |
|---|---|---|---|
| 1 | `frame_id` starts at 0, rises by 1 per delivered frame | Correct, not tested | Correct; `test_frame_id_starts_at_zero_and_rises_by_one` |
| 2 | `timestamp` from `time.monotonic_ns()` immediately after the image is obtained | Correct (taken after the read) | Correct; checked against the clock |
| 3 | Every image is height × width × 3, uint8, BGR | Correct for files; no resizing | Correct; the virtual camera resizes to the requested size |
| 4 | Webcam reports `"webcam"` and returns only the newest frame | Type correct; **no camera thread, so not newest-only**; constructor was `camera_index` only | Camera thread keeps only the newest frame; `WebcamSource(device, width, height, fps)` |
| 5 | File source reports `"video"`; `realtime=True` releases at the file's rate and returns the newest, `realtime=False` returns every frame | **No `realtime` argument** | `VideoFileSource(path, realtime=True)`; a slow reader skips ahead |
| 6 | Virtual Pi camera: `"picam"`, requested size and rate, newest frame only, loops, never ends | Type correct; **no size, rate, loop or thread**; constructor was `video_path` only | `VirtualPiCamSource(path, width=1280, height=720, fps=30.0)` with all of them |
| 7 | `read()` returns None at the end or on a failed read | Correct | Correct |
| 8 | `open()` raises `RuntimeError` with a clear message | Raised, but the message did not name the file | The message names the file |
| 9 | `close()` can be called twice and stops the camera thread | Idempotent (no thread existed) | Idempotent; the thread is joined |
| — | `tests/test_sources.py` (Issue A section 8, items 1–10) | **Missing** | 25 tests; the webcam test is skipped without a camera |
| — | Every public class and function has a docstring | Most had none | All have one |

### What was good

The packet construction was already right: the counter, the monotonic timestamp taken after the read, the read-only image and the clean error on a missing file. The structure (one class per source behind one base) was kept.

### Problems

```text
1  Constructors did not match the issue (device, width, height, fps; realtime; width, height, fps).
   Other work packages and the benchmark call the issue's signatures, so a mismatch is an
   integration failure even if the class works on its own.
2  No camera thread: webcam and virtual Pi camera could not return "only the newest frame".
3  The virtual Pi camera did not loop, resize or pace itself, so it did not behave like the real
   camera it stands in for.
4  No tests; no docstrings.
5  Comments that state doubt rather than reason ("idk how does the simulation work") and typos.
   A comment should say why the code is the way it is.
6  Unused imports (dataclasses.replace) and imports in the wrong order; black failed.
```

### What the integration changed, and why

`src/hades/sources.py` was rewritten (172 → 334 lines) to follow the issue; `tests/test_sources.py` is new.

```text
Constructors      As in Issue A.
Camera thread     One thread per live source (webcam, virtual Pi camera), holding only the newest
                  frame, started by open() and joined by close().
File pacing       realtime=True: frames are released at the file's rate; a reader that is slower
                  skips frames instead of queuing them. frame_id still rises by 1 per delivered
                  frame, so a skip does not leave a gap in the numbering.
Virtual Pi cam    Loops the file, resizes to the requested size, paces at the requested rate.
After close       read() returns None ("the input has stopped"). Before open() it raises
                  RuntimeError (a mistake in the caller). Decision 20.
source_id         Every packet carries source_id "cam0" (contract 0.2).
```

### What is left for you

```text
1  Run the webcam test on a laptop with a camera (it is skipped in CI and here).
2  Re-run tests/test_sources.py on the real clips when they are committed.
3  The Windows path (cv2.CAP_DSHOW for the webcam) is written but was not run.
4  Integration acceptance (Issue A, section 11, items 6 and 7): the Project Owner runs it.
```

### Check yourself

```bash
pytest tests/test_sources.py -q --cov=hades.sources --cov-report=term-missing
black --check src tests && pylint src/hades/sources.py && mypy src/hades/sources.py
```

---

## 4. WP B — Detection (dougleungch, Issue #4)

### What was delivered

`src/hades/detect.py` with `UltralyticsDetector(min_confidence, input_size)`, `load()` and `detect()`; no tests; commits on 11/22.

### Done criteria of the issue

| # | Criterion | Before | Now |
|---|---|---|---|
| 1 | `load()` loads once and runs one warm-up | Correct | Correct; `test_load_runs_exactly_one_warm_up_and_loads_the_model_once` |
| 2 | One packet per frame, an empty tuple when nothing is found | Correct (tuple); `contracts.py` said list (see section 7) | Correct, and `contracts.py` now says tuple |
| 3 | `frame_id` and `timestamp` copied unchanged | Correct | Correct |
| 4 | `t_detect` from `time.monotonic_ns()` as the last step | Correct | Correct; checked |
| 5 | `inference_ms` is the model's own time (`results[0].speed["inference"]`) | Correct | Correct; checked against a scripted value |
| 6 | Every box is in original-frame pixels and inside the image | Correct (clamped, empty boxes dropped) | Correct; 7 kinds of unusable box tested |
| 7 | All values are plain Python numbers | Correct | Correct; `type() is float` is used on purpose, because `np.float64` is a subclass of `float` |
| 8 | `class_name` from the model; only classes in `classes.yaml` kept | Correct | Now from `contracts.CLASS_NAMES` (decision 15); a test compares it with `classes.yaml` |
| 9 | The same frame gives the same detections | Correct | Correct; tested twice on one frame |
| — | `tests/test_detect.py` (Issue B section 8, items 1–11) | **Missing** | 48 tests |

### What was good

This is careful work: the constructor rejects bad values, `load()` checks the weights file, the model class names and the schema version before it loads anything, `detect()` refuses a bad image and a result with more than one entry, and a model that reports no usable inference time is an error rather than a silent zero. The code **wrote down the tuple-versus-list discrepancy in a comment instead of silently choosing**; that is the right habit, and it is why the discrepancy was fixed in the contract (section 7).

### Problems

```text
1  No tests (eleven are required).
2  pylint: detect() was too long (22 local variables, a condition with 6 parts); imports in the
   wrong order. mypy: 2 errors (the YOLO import, an unused ignore).
3  Class names were read from classes.yaml inside load(), so there were two lists of classes.
```

### What the integration changed, and why

`src/hades/detect.py` (173 → 178 lines) with no change of behaviour; `tests/test_detect.py` is new.

```text
Structure         detect() split into _is_valid_image(), _clamp_box() and _convert(); the checks and
                  error messages are the same.
Class names       contracts.CLASS_NAMES instead of reading classes.yaml.
Types             The mypy errors fixed.
Tests             Real YOLOv8n on the clips for the format, the timing and one packet per frame;
                  a scripted fake YOLO for the filtering rules, because the official model has no
                  drone class and returns nothing.
```

### What is left for you

```text
1  Accuracy is Stage 3 (training). Nothing here says drones are detected.
2  Re-run on the real clips and the committed test_model.pt.
3  The Hailo path (HEF model) is a later implementation of the same two functions.
```

### Check yourself

```bash
pytest tests/test_detect.py -q --cov=hades.detect --cov-report=term-missing
pylint src/hades/detect.py && mypy src/hades/detect.py
```

---

## 5. WP C — Dataset (Greencslethan, Issue #5)

### What was delivered

**Nothing.** There is no commit that touches a work package C file.

```text
ml/dataset.py                        three functions, all still "raise NotImplementedError"
data/annotation_guideline.md         5 lines: a placeholder
data/dataset_v1/                     0 images, 0 label files
data/dataset_v1/split_manifest.csv   the header row only, 0 rows
tests/test_dataset.py                does not exist
```

### Done criteria of the issue

| # | Criterion | State |
|---|---|---|
| 1 | `extract_frames()` names files `<clip>_<6 digits>.jpg` and returns their paths | Not done |
| 2 | `build_split()` keeps each source clip in one split and writes the manifest | Not done |
| 3 | The same seed gives the same split | Not done |
| 4 | `validate_dataset()` reports the six listed problems | Not done |
| 5 | `validate_dataset()` returns an empty list for a valid dataset | Not done |
| — | `classes.yaml` with exactly one class | Done (it was in the repository already) |
| — | Annotation guideline covering six cases, each with an example | Not done |
| — | `dataset_v1` valid, every split with and without drones, no clip in two splits | Not done |

### Feedback

Stage 3 training has nothing to train on until this exists, so this is the work package that most affects the schedule. **You can start without any real footage:** the three functions work on folders and on the fixture clips, so they can be written and tested first.

```text
Suggested order   1  validate_dataset()   a pure function that reads a folder: the easiest to test
                  2  extract_frames()     one clip in, numbered .jpg files out
                  3  build_split()        whole clips go to one split; seeded, so repeatable
                  4  the guideline        written before anyone labels
                  5  the labelled data    needs the footage and the labelling tool
Tests             tests/test_dataset.py: the nine tests of Issue C section 8, on a temporary folder
                  built from the fixture clips, never inside data/
```

Questions the issue leaves open and that need an answer from the Project Owner before step 5: where the footage comes from and whether its licence allows use; which labelling tool (the issue says one that exports the YOLO format, agreed with the Project Owner); and that original source videos are never committed (decision 2).

### What is left for you

Everything. If something blocks you, say so in the issue early; the earlier it is known, the cheaper it is to fix.

---

## 6. Common problems (all work packages)

```text
1  Formatting          All 4 helper pushes failed CI at black --check, so pylint, mypy, bandit and
                       pytest never ran on them. Run the five checks of section 12 before pushing.
2  Files that do not   poetry.lock (4,589 lines; the project builds with setuptools and has no
   belong              poetry section), demo_oled.py, oled.png, .vscode/settings.json. Removed.
3  Shared files        tests/conftest.py belongs to work package F (Issue 0, rule 8: nobody edits
                       another package's files). A second conftest.py conflicts with it. The fixtures
                       the D and E tests needed (packets, states, detection_packet, make_frame) are
                       now in the shared one, in the real format.
4  Guessed formats     The sample-packet format was guessed ({"type": "DetectionPacket", "data":
                       {...}}). The real format is the run-log format: a lower-case type
                       ("frame", "detection", "state") and the packet's fields at the top level.
5  Tests that cannot   The E tests used four fixtures that exist nowhere (load_contract_packets,
   run                 expected_event_type, frame_packet, packet); the D tests needed Pillow and a
                       conftest that did not match. A test that cannot run proves nothing.
6  Commented-out code  About 160 lines in alert.py, 65 in telemetry.py, 30 in monitor.py, plus
                       duplicate module docstrings. Version control keeps the old code; delete it.
7  sys.path changes    alert.py, monitor.py and telemetry.py edited sys.path to find the package.
                       The package is installed with pip install -e, so this is not needed and
                       hides import errors.
8  Dependencies        Pillow was used but is not a declared dependency. Declare what you import,
                       or use what is already declared (OpenCV was).
9  Tests that always   A test is only useful if it fails when the code is wrong. Break the code on
   pass                purpose once (docs/test-plan.md, section 6).
```

## 7. Contract 0.2 — what changed and what it means for your work package

The packet format moved from 0.1 to 0.2 in one change (decision 13). It is in `docs/spec.md` and `src/hades/contracts.py`.

| Change | Affects |
|---|---|
| `FramePacket.source_id`, always `"cam0"` (default, so existing calls still work) | A (every packet), E (frame records), D (none), tests that build frames |
| Multi-item fields are tuples; an empty result is an empty tuple, never a list | B (`detections`), I (`targets`), E (writes tuples as JSON arrays), tests |
| The frame image is read-only and left out of packet comparison | A, D (draw on a copy), B (works on a copy) |
| `source.width`, `source.height`, `source.fps` in the configuration | A (constructor arguments), the main program |
| `ErrorRecord.package` is any upper-case string | R |
| `contracts.CLASS_NAMES` is the only list of class names | B, C (`classes.yaml` is checked against it), H |
| Schema version `"0.2"`: take it from `contracts.SCHEMA_VERSION`, never write it in code | E (had its own `"0.1"`), all tests |

## 8. WP D — Screen and monitor (Greencslethan, Issue #6)

### What was delivered

`VirtualOledDisplay` and `format_lines()` in `alert.py`; `WebMonitor` in `monitor.py`; three tests files; two commits, 11/15 and 11/20.

### Done criteria of the issue

| # | Criterion | Before | Now |
|---|---|---|---|
| A1 | At most eight lines of at most 21 characters | Correct | Correct; also tested with an over-long frame number |
| A2 | The state is shown as given in the packet | Correct | Correct, for every state |
| A3 | Frame rate to one decimal | Correct | Correct (24.84 → 24.8, 24.86 → 24.9) |
| A4 | No hardware library imported | The default path was clean, **but** an optional Tk window and Pillow were in the same file and wrote `oled.png` to the working folder | Clean; tested in the source and at run time (hardware, `tkinter` and `PIL` are not loaded) |
| B1 | The server runs in one background thread | Correct (plain `HTTPServer`) | Correct; requests do not add threads |
| B2 | `publish()` only stores the latest of its type and returns | Correct | Correct; unknown types are ignored |
| B3 | Boxes only for the detection with the same `frame_id` | Correct | Correct |
| B4 | The frame's image is never changed | Correct (copied first) | Correct; the image is also read-only |
| B5 | `/status.json` reflects the latest state and detections | Correct | Correct; frame rate tested |
| — | `tests/test_alert.py`, `tests/test_monitor.py` using the shared fixtures | Existed but depended on a guessed conftest and Pillow | 23 and 14 tests on the shared fixtures |

### What was good

The monitor design is sound: one server thread, the latest message of each type held behind a lock, the picture cached until the frame or detection changes, and the frame copied before anything is drawn. That is exactly what the issue asked for.

### Problems

```text
1  The virtual OLED could open a Tk window and write oled.png into the working folder. The issue
   says the screen is shown in the terminal; Issue 0 says files are written only by program entry
   points and by Telemetry, and that windows are shown only from the main loop.
2  The monitor listened on 0.0.0.0, which offers the page to the whole network. Bandit flagged it
   (B104). A development page should listen on this computer only unless asked otherwise.
3  Pillow was used for drawing and JPEG encoding but is not a declared dependency; the issue lists
   OpenCV.
4  About 160 lines of old code in comments, a repeated module docstring, a sys.path change.
5  The tests belonged partly to another package (a test of the LFS-pointer check is a test of
   conftest, which is work package F's).
```

### What the integration changed, and why

```text
alert.py     284 → 91 lines. The Tk window, Pillow, oled.png, the comments and the sys.path change
             removed; format_lines() and VirtualOledDisplay kept as they were. The minimal MockAlert
             (J) was added so the Stage 2 main program can show "target seen, LED on" (decision 17).
monitor.py   230 → 213 lines. Drawing and JPEG encoding use OpenCV; the host is a constructor
             argument that defaults to 127.0.0.1; typed; the comments removed. The logic is yours.
tests        Rewritten on the shared fixtures, in the real packet format and without Pillow; new
             tests for "writes no file and opens no window", the local-only listener, the frame
             rate, the 503 and 404 answers and the picture cache.
```

### What is left for you

```text
1  A question for the Project Owner: Issue D lists Flask as the tool. The standard-library server
   satisfies the one-thread rule and needs no dependency. Keep it, unless the Project Owner
   wants Flask.
2  Re-run on the real clip. The Project Owner watches the page and the screen during the
   integration run (Issue D, section 11, items 6 and 7).
3  State colours and labels are work package L (Stage 4); state_style() is still a skeleton.
```

### Check yourself

```bash
pytest tests/test_alert.py tests/test_monitor.py -q --cov=hades.alert --cov=hades.monitor
pylint src/hades/alert.py src/hades/monitor.py && mypy src/hades/alert.py src/hades/monitor.py
```

---

## 9. WP E — Run log and replay (Greencslethan, Issue #7)

### What was delivered

`Telemetry`, `ReplaySource`, `file_sha256()` and `git_info()` in `telemetry.py`; a test file; commit 11/20.

### Done criteria of the issue

| # | Criterion | Before | Now |
|---|---|---|---|
| 1 | `start_run()` creates the run folder and `meta.json` | Correct | Correct; every field compared |
| 2 | `record()` only queues and returns | Correct | Correct; tested with a writer that needs 50 ms per line |
| 3 | The writer writes one JSON line per packet: right type, every field, plain JSON | Correct | Correct; a bad packet is skipped and the run goes on |
| 4 | Frame records hold `height` and `width`, not the image | Correct | Correct; `dataclasses.asdict` is proved not to be used |
| 5 | `end_run()` writes everything still queued; the program calls it on Ctrl+C | Correct in `end_run()`; nothing called it on Ctrl+C | The main program closes the log in a `finally`; tested |
| 6 | `file_sha256()` reads in chunks | Correct | Correct; a 2.5 MB file, and the known hash of "abc" |
| 7 | `git_info()` returns `("unknown", False)` without git | Correct | Correct; also for a failing and a hanging git; the dirty flag is tested both ways |
| 8 | `ReplaySource` plays the original video as a live source | Played as fast as possible by default | Default is live (`realtime=True`); tests pass `realtime=False` for speed |
| 9 | `ReplaySource` raises `RuntimeError` for a non-video run | Correct | Correct, with a message that names the problem |
| — | `tests/test_telemetry.py` using the shared fixtures | Four fixtures it used existed nowhere | 45 tests that run |

### What was good

This is the strongest design of the three: one writer thread fed by a queue; the closing marker put on the queue under the same lock that `record()` uses, so **no accepted record can end up behind it**; `dataclasses.asdict` deliberately avoided with a comment saying why (it would copy every image); a write error is kept and reported by `end_run()` rather than lost.

### Problems

```text
1  The tests could not run (section 6, item 5), so nothing proved the design worked.
2  The module had its own SCHEMA_VERSION = "0.1" instead of the contract's.
3  About 65 lines of old code in comments, a sys.path change, 12 mypy errors, pylint findings.
4  ReplaySource read() reopened the video after close(), so a stopped replay silently restarted.
```

### What the integration changed, and why

```text
telemetry.py   494 → 425 lines. Same design; the schema version comes from contracts; ReplaySource is
               live by default and stays stopped after close(); git is called through one small
               function with a fixed argument list (Issue 0, rule 27) and the bandit notes are
               marked; typed; comments and the sys.path change removed.
tests          Rewritten: 45 tests covering all eleven items of Issue E, section 8, plus the error
               paths (disk error, bad packet, second run, reused folder, broken meta.json).
```

### What is left for you

```text
1  The writer thread is not a daemon: if a program forgets to call end_run(), the process cannot
   exit. That is on purpose (no record is lost); the main program always closes the log.
2  summarise(), export_session(), report_error() and replay_main() belong to N, R and M and are
   still skeletons.
3  ReplaySource and VideoFileSource overlap; merging them is deferred to Stage 4 (decision 19).
4  Re-run on the real clip.
```

### Check yourself

```bash
pytest tests/test_telemetry.py -q --cov=hades.telemetry --cov-report=term-missing
pylint src/hades/telemetry.py && mypy src/hades/telemetry.py && bandit -q src/hades/telemetry.py
```

---

## 10. WP F — Test harness and benchmark (Project Owner, Issue #8)

Delivered: `bench/benchmark.py` (`run_benchmark()` for latency, fps and memory; `write_report()`), `tests/conftest.py`, `tests/test_benchmark.py` (43 tests), `.github/workflows/tests.yml`, `pyproject.toml` settings.

```text
Criteria     All seven of Issue F section 7B are met and tested; benchmark.py has 100 % coverage.
Found        write_report(report, "bench/reports") wrote a file named "reports" when the folder did
             not exist yet; fixed and tested.
Acceptance   Issue F section 11, items 6 and 7, was run through the real A and B on a stand-in clip
             and the three reports were opened and checked (median <= p95 <= max, fps_min <= fps_avg,
             model hash equal to the file's, the hardware named). They are not committed: they
             are not real figures (docs/test-plan.md, section 9).
Left         Run on the real clips and on the target hardware.
Not yet      tests.yml has never run on GitHub: it only runs on pull requests and on pushes to main.
```

## 11. Process review of Stage 2

This section reviews the process; it names no person.

**What worked.** Each issue had numbered Final Done Criteria, which made this review mechanical: every item above is a line of an issue. The frozen interface in Issue 0 meant the packages fitted together once the formats agreed. The helpers' code was mostly sound; the problems were around it (tests, formatting, interfaces) rather than in its logic.

**What went wrong, and why.**

```text
1  Issue 0 promised that the fixtures and the contract would be committed before work started.
   The three clips and the model were not, and the contract as committed did not match what the
   issues said (lists instead of tuples, no source_id, no source.width). Helpers had to guess, and
   guesses (the sample-packet format, the conftest) did not match each other.
2  The style checks ran only in CI. All four pushes failed at the first check, and the later
   checks, which would have shown the real problems, never ran.
3  The issues used names (VideoFileSource, UltralyticsDetector, VirtualOledDisplay) that the
   repository's skeletons did not have (VideoSource, ModelDetector). A helper reading the
   skeleton and a helper reading the issue built different interfaces.
4  Nobody owned the assembled program, so no real end-to-end run existed until the integration:
   each package passed its own checks and the whole was unproven.
```

**What changes for Stage 3.**

```text
1  The fixtures and the contract are committed before the Stage 3 issues are opened.
2  Every pull request starts from the checklist in section 12; the CI run is the confirmation, not
   the first time the checks run.
3  Skeleton names are made to match the issues when the issues are written.
4  tests/integration/test_pipeline_smoke.py exists from now on: a change that breaks the chain
   fails that test.
```

## 12. Checklist before every pull request

```bash
git fetch origin && git rebase origin/main            # start from the latest main
black --check src ml bench tests                      # formatting
pylint src ml bench                                   # style and obvious errors
mypy src ml bench                                     # types
bandit -q -r src ml bench                             # unsafe patterns
pytest --cov --cov-report=term-missing                # tests and coverage
cd /tmp && pytest "<repository>/tests"                # also passes from another folder
grep -rn --include='*.py' "open(" tests/ | grep -E "runs/|bench/reports"   # no test reads an output folder
```

```text
□ Only the files your issue lists are changed; no one else's file, not docs/spec.md, not contracts.py
□ No commented-out code, no sys.path change, no file that is not used
□ Every public class and function has a docstring
□ Every dependency you import is declared in pyproject.toml
□ You broke your code on purpose once and a test failed
□ Every item of the issue's section 11 is ticked in the pull request, with how it was checked
```

## 13. Known limitations and what was not verified

```text
Not verified    Real footage (the three clips): every result is from stand-in clips
                The webcam on real hardware; the Windows camera path
                GitHub Actions: tests.yml has not run on GitHub
                The target hardware (Raspberry Pi 5 with the AI HAT+) and the Hailo model path
                Detection accuracy, range and false alarm rate: not measured (docs/test-plan.md)
Not committed   tests/fixtures/test_model.pt and the three clips: the Project Owner commits them
                (decision 22). Until then, tests that need them fail with a message that says so.
Open            WP C is not started. Flask or the standard-library server for D. The first
                thresholds and "G. Demo Success Criteria".
```

## 14. In one sentence

> Stage 2 produced working, tested A, B, D, E and F and a main program that runs the whole chain and logs every frame — but the tests passed on stand-in footage and the fixtures are not yet committed, the dataset (C) has not started, and no detection accuracy has been measured, so Stage 2 is not complete until the real clips are in and C is done.
