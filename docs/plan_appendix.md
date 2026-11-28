# HADES MVP Master Development Plan — Appendix v1.1

Living document: updated with documents 1–4.

This page records where the plan (document 4) differs from the market requirements (document 1), the PRD (document 2) and the specification (document 3), and what was decided. It does not change the body of [`plan.md`](plan.md), which keeps its original wording. **When v0.1 is carried out and something differs from documents 1, 2 or 3, this page decides.** Where this page and the PRD differ, the PRD decides.

**How to read the status marks.** *Decided* has a recorded source. *Derived* was worked out from `docs/spec.md` and the issues and still needs the Project Owner's confirmation. *TBD* has no ruling yet and is not filled in on purpose.

---

## 1. Differences of scope from documents 1, 2 and 3

### 1.1 What the Core outputs — decided

```text
Plan        Stage 1 task 2 D: actuator_command_spec.md (led_mode / buzzer_mode / laser_on)
            Stage 4 task 2 Actuator Command Mapping; work package J
PRD         The Core ends at the interface and outputs a standardised signal; no payload
v0.1        The PRD asks for two layers: the signal the Core outputs, and the demo reaction
            (LED, buzzer, laser) on the far side of the interface.
Ruling      For the MVP the two are not separated: the main loop drives an alert mock and the
            decision layer later maps a confirmed target to the outputs. This is a recorded
            exception to this item (recorded outside the repository; see decisions 16 and 17).
```

### 1.2 No threat grading in v0.1 — decided

```text
Plan        alert_level in stage 1 and stage 4; the three-level reaction in week 5
PRD         v0.1 only decides "is it a drone"; detection means trigger; grading is v0.2 or later
v0.1        One trigger level: alert_level is 0 or 1. The three-level reaction stays a long-term
            design.
```

### 1.3 Detection targets — decided

```text
Plan        "drone / moving object / person"; the class file of work package C
PRD         v0.1 targets the ordinary consumer-class drone
v0.1        One class, "drone" (contracts.CLASS_NAMES, data/classes.yaml). Persons and moving
            objects are not classes in v0.1.
```

### 1.4 AI model and compute hardware — decided

```text
Plan        YOLOv8n / YOLOv5n on RPi 4B or Jetson Nano
PRD         The hardware was open
v0.1        Raspberry Pi 5 (4 GB) with the AI HAT+ (26 TOPS, Hailo-8); model: Ultralytics YOLOv8,
            YOLOv8n in Stage 2, YOLOv8n against YOLOv8s in Stage 3 (decisions 7 and 9).
            The final camera and lens are chosen after Stage 3 testing.
            The plan text that names RPi 4B and Jetson Nano is superseded by this ruling.
```

### 1.5 The three validation numbers have no stage that measures them — partly decided

```text
Document 1  v0.1 success metrics: end-to-end latency, effective detection range, false alarm
            rate; target TRL 3-4
Plan        No stage or work package measures them
Ruling      Stage 2 measures only the latency from capture to the end of detection
            (BenchmarkReport kind "latency", work package F). Full end-to-end latency
            (capture to command), range and false alarm rate are measured from Stage 4.
Open        The first thresholds and "G. Demo Success Criteria" are TBD; see docs/test-plan.md.
```

### 1.6 Specification and task 2 overlap — decided

```text
Plan        Task 2 lists seven specifications (A-G)
Ruling      They are one document, docs/spec.md, which is the formal definition; the plan points
            to it (decisions 5 and 6). It defines only the packet formats and function signatures
            of each work package; linkage, acceptance tests and behaviour rules are in the issues;
            the standard interface stays in the PRD.
```

## 2. Differences inside the source material

### 2.1 Sound and infrared sensing in v0.1 — decided

```text
P1 M1 and the PRD list a microphone and an IR sensor; the bill of materials has no IR sensor;
the AI selection lists sound and IR as a later option.
Ruling      v0.1 senses with vision only. Sound and IR are not bought or connected in v0.1.
```

## 3. Four-helper arrangement

Applies only if the team grows to four helpers. The three-person arrangement in plan section IX stays the default.

```text
Project Owner   G I
Helper 1        A B H P        input + inference wrapper + error analysis + diagnostic
Helper 2        C D L M        dataset + UI + demo support
Helper 3        E J N R        logging + replay + actuator driver
Helper 4        F K O Q        testing + integration test + stability + config
```

| Work package | Three people | Four people |
|---|---|---|
| F, O, Q | Project Owner | Helper 4 |
| J | Project Owner | Helper 3 |
| K | Helper 1 | Helper 4 |
| R | Helper 1 | Helper 3 |
| E, N | Helper 2 | Helper 3 |
| G, I | Project Owner | unchanged |
| A, B, H, P | Helper 1 | unchanged |
| C, D, L, M | Helper 2 | unchanged |

The rules behind it are unchanged: the Project Owner keeps architecture, decision / state machine and final integration; Helpers 1 and 2 are only reduced from the three-person arrangement; every person has at least one main or continuing work package in every stage.

## 4. Fields marked "TBD" in work packages J–R

Needed before the Stage 4–6 issues are written. **Everything below is *derived* from `docs/spec.md` and still needs the Project Owner's confirmation.** Items with no basis in the spec are TBD.

| Work package | Field | Proposal (derived) |
|---|---|---|
| J | Remaining acceptance | `send()` is idempotent; `alert_level` 0 switches every output off; `status()` reports what the outputs actually do and `healthy` is false if an output fails; the mock and the GPIO driver sit behind the same `Alert` functions; no GPIO library is imported when the module is imported |
| J | Dependency | `actuator_command_spec.md` is now the Decision Layer section of `docs/spec.md`; item 1.1 above is settled |
| K | Remaining deliverables | `run_integration()` in `src/hades/pipeline.py` and tests in `tests/integration/`; the regression checklist |
| K | Remaining acceptance | `run_integration()` returns an `IntegrationResult` (`pass` / `fail`, `run_id`, `source` live or replay); a live run and a replay of the same clip are both checked |
| L | Deliverables | `state_style()` in `src/hades/monitor.py` returning a `StateStyle` (label and hex colour) for all six states |
| L | Acceptance | A bystander who sees the screen knows what is happening without an explanation (plan wording); the label for each state is understandable to someone who does not know the system |
| N | Deliverables | `summarise()` returning a `SessionSummary` (`summary.json`); `export_session()` writing `events.csv` with the fixed columns |
| N | Acceptance | The summary figures can be recomputed from `events.jsonl`; the CSV opens in a spreadsheet and has the fixed header |
| O | Deliverables | `run_stability()` returning a `BenchmarkReport` of kind `stability` with the result fields in `docs/spec.md` |
| O | Acceptance | **TBD**: the run length and the allowed drop in frame rate and growth in memory are not decided; they depend on the first real benchmark and on "G. Demo Success Criteria" |
| R | Subtasks and deliverables | `report_error()` in `src/hades/telemetry.py` writing an `ErrorRecord`; a fixed list of error codes per work package (list **TBD**) |

## 5. Additions in this version

```text
Repository structure   Defined in docs/architecture.md; changes there are changes to this plan.
Virtual hardware       Stage 2 connects no physical device. The Pi camera and the OLED are virtual:
                       the virtual Pi camera loops a fixture video, the virtual OLED prints its
                       eight rows of 21 characters in the terminal (decision 8, decision 23).
Logging module name    telemetry, so that it does not shadow Python's logging (decision 4).
Fixtures               tests/fixtures/ holds three clips (drone_daylight_01, no_drone_01,
                       head_walk_01), sample_packets.jsonl and test_model.pt, all committed by the
                       Project Owner before the work packages start (Issue 0). Stage 3 adds
                       distance-marked clips and clips with distractors.
Work package C         Done by the Project Owner in Stage 2 (tools, tests, guideline) because Helper 2
                       had no time for it; the labelled dataset itself is still to be made.
Ten-week schedule      The ruling on the gap between the ten-week table and the work-package
                       stages is TBD.
Two-person fallback    The arrangement for a two-person team is TBD.
```
