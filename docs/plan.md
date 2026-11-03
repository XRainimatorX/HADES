# HADES MVP Master Development Plan

Living document: updated as the development phases progress.

For differences in scope from Documents 1/2/3, see the separate notes page.

---

Bring HADES **fully back to its primary goal**:

> **Build an MVP that works at public demonstrations and startup competitions, and looks like a product rather than a student toy.**

This is not a vague "project breakdown," but rather:

> **Split each development stage of the HADES MVP into parallel-capable coding / AI work packages, so others can develop simultaneously and truly speed up overall progress.**

---

## I. First, Define What "First MVP Complete" Looks Like

If you don't define the endpoint first, engineering will grow out of control.

### MVP Completion Criteria

When the first goal is finished, HADES must do 5 things:

**1. See the target**
The camera feed runs continuously and performs basic recognition on targets.

**2. React after judgment**
Once trigger conditions are met, it can activate audio-visual alerts:

```text
buzzer
LED
laser pointer
```

This is exactly the demo response layer defined in the P1 document.

**3. Humans can understand the results**
The OLED or app can show at least one of the following:

```text
detected / not detected
confidence
reaction time
```

This is also the display and sync direction already reserved in the P1 document.

**4. Wearing it makes a complete system, not a pile of parts**
It needs a helmet structure, mounts, counterweight, and module placement logic.

**5. Can fully perform a 60–120 second demo**
Judges can understand at a glance what it does, rather than needing the Project Owner to talk for 10 minutes before they get it.

---

## II. The HADES MVP Is Divided Into 5 Major Blocks

### 1. Product Definition / Scope

**Mainly handled by the Project Owner.**

Contents include:

```text
what the MVP does
what it does not do
what must be proven during the demo
target categories: drone / moving object / person, which ones
boundaries of non-destructive response
```

This part comes first in time.
AI/code must wait until this is defined, otherwise no one knows what they are writing.

### 2. AI / Code Core System

It includes:

```text
Video Input
Detection
Dataset
Training
Tracking / Filtering
Decision / State Machine
Actuator Mock / Driver
UI / Monitoring
Logging / Replay
Benchmark / Diagnostic / Config
```

That is, the earlier:

```text
Work Packages A–R
```

This part is the core software line of the entire MVP.
It should be mostly completed before physical helmet integration.

### 3. Electronics and Hardware Wiring

Including:

```text
RPi / Jetson setup
PiCam wiring
OLED wiring
LED / buzzer / laser module wiring
power bank and power arrangements
GPIO hands-on testing
```

Related work packages:

```text
J: Actuator Mock / Driver Layer
P: Diagnostic Mode
Q: Quick Config Tool
R: Error Logging Improvement
```

### 4. Helmet / 3D / Structural Integration

Including:

```text
3D-printed shell
counterweight
cable management
wear testing
```

### 5. Demo / Pitch / Presentation Flow

Including:

```text
presentation story
on-site flow
filming arrangements
competition talking points
live demo control
```

Related work packages:

```text
M: Replay Demo Support
N: Final Log / Telemetry Cleanup
D / L: UI display and integration
E: Logging / Replay
```

---

## III. The Position of AI/Code in the Overall MVP Timeline

Without specific dates, only the order matters. It should look like this:

```text
product definition
→ AI/code parallel development
→ desktop system runs end to end
→ hardware wiring tests
→ helmet structure integration
→ demo freeze
→ demonstration / pitch
```

AI/code is mainly in the early-to-middle stages, and must be substantially finished before full physical integration.

---

## IV. Six-Stage Development

It is recommended to split the entire coding / AI development into **6 stages**.
Within each stage, further split into parallelizable work packages.

### Stage 2: Core Module Parallel Build

#### Which segment of the overall MVP does this belong to?

It belongs to the **initial formation period of the software core**.

#### Role of AI/code

Build the main software skeleton:

```text
A: Video Input Layer
B: Detection Layer
C: Dataset Pipeline
D: UI / Monitoring Layer
E: Logging / Replay Layer
F: Test Harness / Benchmark Layer
```

#### What else can be done at this time?

Can be prepared in parallel:

```text
component procurement
RPi / Jetson environment
camera / OLED / LED / buzzer / laser modules
helmet and installation position concepts
```

But don't lock down the structure too early, since the software interfaces are not yet stable.

#### Work Content

This stage is where true parallel progress begins.
It is also the segment most suitable for division of labor.

This can be split into **6 coding work packages**, starting simultaneously.

**Work Package A: Video Input Layer**

```text
Task content:
  Unify different image sources into the same input format.

Subtasks:
  PiCam / camera input
  webcam input
  playback video input
  frame timestamp
  FPS counter
  frame resize / basic preprocess hook

Deliverables:
  camera_source.py
  webcam_source.py
  playback_source.py
  video_input_test.py

Acceptance criteria:
  Outputs a unified FramePacket format
  Both live and playback can run
  Basic frame rate statistics available
```

**Work Package B: Detection Layer**

```text
Task content:
  Wrap model inference.

Subtasks:
  model loader
  preprocess
  inference
  postprocess
  bbox / class / confidence standardization
  inference time output

Deliverables:
  detector_base.py
  detector_yolo.py
  inference_runner.py
  detection_unit_test.py

Acceptance criteria:
  Takes FramePacket
  Outputs DetectionPacket
  Can run an existing baseline model
  Can output inference_ms
```

**Work Package C: Dataset Pipeline**

```text
Task content:
  Handles the AI data workflow. This is not odd work; it is one of the main tasks.

Subtasks:
  collect demo footage
  split frames
  dataset folder structure
  annotation guideline
  bounding box labeling
  train / val / test split
  class yaml definition

Deliverables:
  dataset_v1/
  classes.yaml
  annotation_guideline.md
  split_manifest.csv

Acceptance criteria:
  Dataset can be used directly for training
  Labeling rules are consistent
  Splits are clear and traceable
```

**Work Package D: UI / Monitoring Layer**

```text
Task content:
  Display the system state.

Subtasks:
  OLED text state
  basic web status page
  detection overlay
  confidence display
  reaction state display
  current mode display

Deliverables:
  oled_ui.py
  web_ui.py
  ui_state_map.md

Acceptance criteria:
  Can read the system state
  Can display detection / alert status
  Display is clear; does not need to be fancy
```

**Work Package E: Logging / Replay Layer**

```text
Task content:
  Handles data recording and playback.

Subtasks:
  event log
  detection log
  actuator log
  JSONL / CSV export
  replay mode
  session playback script

Deliverables:
  logger.py
  replay_engine.py
  export_session.py
  log_schema.md

Acceptance criteria:
  Every run has a log
  A session can be replayed
  Available as fallback for later debugging / demo
```

**Work Package F: Test Harness / Benchmark Layer**

```text
Task content:
  Handles the test framework and benchmarks.

Subtasks:
  FPS test
  inference latency test
  memory usage test
  playback regression
  detection output validation
  actuator mock test

Deliverables:
  benchmark.py
  test_cases.md
  latency_report_template.md

Acceptance criteria:
  Repeatable tests
  Fixed test inputs
  Can compare performance across versions
```

**What the Project Owner does personally in this stage**

In this stage, the Project Owner should not help others write all the code.
The Project Owner only does:

```text
review interfaces
merge branches
decide coding rules
build the decision module skeleton
daily integration smoke test
```

**Outcomes of this stage**

By the end, there should be:

```text
6 modules that each run independently
interfaces that match up
ready to move into AI usability and system integration
```

**Time estimate:** 1–2 weeks

#### Personnel Division

| Person | Work Packages |
|---|---|
| **Project Owner** | **F** |
| **Helper 1** | **A, B** |
| **Helper 2** | **C, D, E** |

---

### Stage 3: AI Usability Stage

#### Which segment of the overall MVP does this belong to?

It belongs to **making AI go from "it runs" to "it's usable."**

#### Role of AI/code

This is the most core stage for AI/code:

```text
G: Training / Fine-tuning Pipeline
H: False Positive / False Negative Analysis
I: Tracking / Filtering Layer
```

#### Impact of this stage on the overall MVP

This stage determines:

```text
whether the target can be detected stably
whether false alarms are too frequent
whether it can proceed to a live demo
whether the system looks like it "has judgment" or just "yells randomly"
```

This is where the Project Owner says they will personally do training, which makes sense,
because it directly affects the later decision / state machine.

#### Work Content

This stage focuses on turning detection from "it runs" into "it's good enough."

This stage can also proceed in parallel, and the division of labor is very valuable here.

**Work Package G: Training / Fine-tuning Pipeline**

```text
Task content:
  Handles training and experiment management.

Subtasks:
  train script
  config
  checkpoint save
  experiment naming
  evaluation
  best model export

Deliverables:
  train.py
  eval.py
  experiments/
  model_selection_report.md

Acceptance criteria:
  At least one baseline model and 1–2 fine-tuned versions
  Basic precision / recall / confusion summary
  Able to select the best model for the demo
```

**Work Package H: False Positive / False Negative Analysis**

```text
Task content:
  Specifically analyzes situations prone to misjudgment.

Subtasks:
  collect false-alarm frames
  collect missed-detection frames
  classify failure causes
  propose threshold / filtering suggestions

Deliverables:
  error_case_report.md
  fp_fn_samples/
  threshold_suggestion.md

Acceptance criteria:
  Clear understanding of which scenarios are most likely to fail
  Not just "it feels inaccurate," but organized case records
```

**Work Package I: Tracking / Filtering Layer**

```text
Task content:
  Prevent detections from jumping randomly frame by frame.

Subtasks:
  confidence smoothing
  temporal confirmation
  target persistence
  false positive suppression
  preprocessing for cooldown logic

Deliverables:
  tracker.py
  filter_engine.py
  tracking_test.py

Acceptance criteria:
  Detection output is more stable after tracking
  The same target does not trigger infinitely and repeatedly
  Usable by the decision layer
```

**What the Project Owner does personally in this stage**

The Project Owner mainly handles:

```text
deciding the class scope for the first version
deciding which model to accept
deciding threshold principles
deciding which tracking behaviors fit the HADES style
```

**Outcomes**

At the end of this stage, there should be:

```text
a usable demo model
a more stable detection → tracking output
an understanding of failure cases
```

**Time estimate:** about 1 week

#### Personnel Division

| Person | Work Packages |
|---|---|
| **Project Owner** | **G, I** |
| **Helper 1** | **H** |
| **Helper 2** | continues **C**, updates dataset / annotation |

This stage is the core:
**The Project Owner personally trains the model, Helper 1 finds errors, and Helper 2 supplements the data.**

---

### Stage 4: Decision & System Integration

#### Which segment of the overall MVP does this belong to?

It belongs to **the desktop system running end to end → preparing to connect physical hardware**.

#### Role of AI/code

Connect all modules into one complete chain:

```text
camera
→ detection
→ tracking
→ decision
→ actuator
→ UI
→ logging
```

Corresponding to:

```text
Decision Layer
Actuator Command Mapping
J: Actuator Mock / Driver Layer
K: Integration Test Support
L: UI integration support
```

#### What does it mean when this stage is complete?

It means HADES's "brain and nerves" can already run on the desktop.
Only then is it appropriate to move into heavier hardware and helmet integration.

#### Work Content

**Mainly led by the Project Owner in this stage**

It is best for the Project Owner to personally write the core, while others assist with testing and interface connections.

Task 1: Decision Layer

Contents include:

```text
threshold logic
multi-frame confirmation
alert level
cooldown
state transition
```

Task 2: Actuator Command Mapping

Convert confirmed targets into:

```text
LED mode
buzzer mode
laser on/off
```

Task 3: Integrate UI / logging / replay

Synchronize the decision state outward.

**Auxiliary work that can still be delegated in this stage**

**Work Package J: Actuator Mock / Driver Layer**

```text
Task content:
  Provide the actuator mock and GPIO driver;
  final command mapping is decided by the Project Owner.

Subtasks:
  actuator mock
  GPIO driver
  driver test

Deliverables:
  mock_actuator.py
  gpio_driver.py
  driver_test.py

Acceptance criteria:
  GPIO / actuator mock succeeds
  (remaining items TBD)
```

**Work Package K: Integration Test Support**

```text
Task content:
  Assist with integration testing and regression.

Subtasks:
  combined testing
  regression checklist
  live vs playback comparison testing

Deliverables:
  regression checklist
  (remaining items TBD)

Acceptance criteria:
  The entire pipeline runs through (input → detection → tracking → decision
    → actuator → UI → logging)
  Both playback mode and live mode work
```

**Work Package L: UI integration support**

```text
Task content:
  Sync decision state to the UI.

Subtasks:
  state label
  alert colors
  overlay details

Deliverables:
  (TBD)

Acceptance criteria:
  Even without the Project Owner explaining, a bystander looking at the screen knows what is happening
```

**Outcomes of this stage**

```text
The entire pipeline runs through:
  input
  detection
  tracking
  decision
  actuator
  UI
  logging
Both playback mode and live mode work
```

**Time estimate:** 1 week

#### Personnel Division

| Person | Work Packages / Tasks |
|---|---|
| **Project Owner** | Decision Layer, Actuator Command Mapping, **J** |
| **Helper 1** | **K** |
| **Helper 2** | **L** |

---

### Stage 5: Demo Freeze

#### Which segment of the overall MVP does this belong to?

It belongs to **software freeze → transition into physical demonstration integration**.

#### Role of AI/code

No more major feature changes; only stabilization:

```text
M: Replay Demo Support
N: Final Log / Telemetry Cleanup
O: Benchmark & Stability Run
```

#### Non-coding work becomes heavier at this point

Starting from this stage, non-coding workload increases significantly:

```text
helmet fixing
cable management
power testing
live hardware testing
demo flow design
```

So the AI/code team should no longer introduce new requirements at this point, but focus on stabilizing the program.

#### Work Content

This stage consolidates the coding portion into a stable version ready for physical integration.

**Coding work packages that can be divided**

**Work Package M: Replay Demo Support**

```text
Task content:
  Ensure there is a replay fallback during the demo.

Subtasks:
  organize demo playback clips
  ensure fallback mode runs

Deliverables:
  fallback replay mode

Acceptance criteria:
  Playback mode works as a fallback
```

**Work Package N: Final Log / Telemetry Cleanup**

```text
Task content:
  Final telemetry cleanup.

Subtasks:
  unify log keys
  session export
  basic result summary

Deliverables:
  (TBD)

Acceptance criteria:
  (TBD)
```

**Work Package O: Benchmark & Stability Run**

```text
Task content:
  No more major feature changes; only stability.

Subtasks:
  latency stress testing
  long-duration run test
  memory usage check

Deliverables:
  (TBD)

Acceptance criteria:
  (TBD)
```

**Led by the Project Owner**

```text
final parameter freeze
deciding which version goes into the full machine
deciding demo mode / live mode switching rules
deciding which bugs can be left unfixed for the stage, and which must be fixed
```

**Outcomes**

```text
freeze branch
final model
final config
fallback replay mode
ready for physical demo integration
```

**Time estimate:** 3–5 days

#### Personnel Division

| Person | Work Packages |
|---|---|
| **Project Owner** | **O** |
| **Helper 1** | continues **K**, assists with regression |
| **Helper 2** | **M, N** |

---

### Stage 6: Coding Support Tail Stage Before the Full Machine

#### Which segment of the overall MVP does this belong to?

It belongs to **the physical integration support period**.

#### Role of AI/code

Not developing new features, but reducing pain during full-machine integration:

```text
P: Diagnostic Mode
Q: Quick Config Tool
R: Error Logging Improvement
```

#### Why this stage matters most

Because physical integration comes next, coding must provide tools:

```text
you can see at a glance where something is broken
thresholds can be changed without editing code
model paths don't need to be rewritten
playback mode can serve as a fallback
error logs can pinpoint problems
```

The AI/code in this stage is the "logistics tool" that supports completing the full machine.

#### Work Content

This stage is no longer main development, but support for the subsequent physical integration work.

So what the coding team needs to do in this stage is **reduce the pain of later physical integration**.

**Tail-stage work packages**

**Work Package P: Diagnostic Mode**

```text
Task content:
  Build a simple diagnostic page or console mode.

Subtasks (display items):
  camera alive
  model loaded
  current FPS
  current state
  actuator status

Deliverables:
  diagnostic page or console mode

Acceptance criteria:
  You can see at a glance what is broken
```

**Work Package Q: Quick Config Tool**

```text
Task content:
  Build a config file or simple settings tool, so the Project Owner can change parameters later
  without editing a lot of code.

Subtasks (configurable items):
  threshold
  cooldown
  UI text
  model path
  playback path

Deliverables:
  config file or simple settings tool

Acceptance criteria:
  Thresholds can be changed without editing code
  Model path doesn't need to be rewritten
```

**Work Package R: Error Logging Improvement**

```text
Task content:
  Make errors during full-machine integration quickly locatable, without guessing.

Subtasks:
  (TBD)

Deliverables:
  (TBD)

Acceptance criteria:
  Error logs can locate the problem
```

#### Personnel Division

| Person | Work Packages |
|---|---|
| **Project Owner** | **Q** |
| **Helper 1** | **P, R** |
| **Helper 2** | continues **M, N**, fixes demo / log details |

---

## V. Relationship Between AI/Code and Non-Coding Work

It can be viewed this way:

```text
Non-coding work: housing, power, wiring, helmet, demonstration
AI/code work: vision, judgment, response, display, recording, diagnostics
```

They do not run in parallel until they meet at the end; instead they should hand off like this:

```text
AI/code runs on the desktop
→ GPIO / actuator mock succeeds
→ physical LED / buzzer / laser connected
→ UI / log / diagnostic usable
→ helmet packaging
→ demo freeze
```

In other words:

> **First make the software come alive on the desktop, then bring it into hardware, and only finally seal it into the helmet.**

Don't do it the other way around, making the helmet look amazing first and only later discovering the code is unstable. That would be very painful.

---

## VI. Full Timeline: 10-Week Version

It is recommended to use **10 weeks** for the first complete MVP cycle.
This pace is fast enough to avoid letting the project rot.

### Weeks 1–2: Desktop Prototype Period (Breadboard Alpha)

```text
Goal:
  Don't touch the helmet yet; first make the core flow come alive on the bench.

Tasks:
  Purchase or confirm components:
    RPi 4B
    PiCam V2
    OLED
    LED
    buzzer
    laser module
    power bank
  Build a minimal program chain:
    camera input
    detection pipeline
    GPIO output
    basic display
  Desktop testing:
    camera runs
    LED lights up when a target is present
    buzzer sounds
    OLED shows status

Outputs:
  GPIO pin map
  minimal executable program

Success criteria:
  camera → detection → reaction
  This chain must be connected first.

Essence of this period:
  Not making a product; first proving that the "nervous system" has life.
```

### Weeks 3–4: AI Detection Usability Period (Detection Alpha)

```text
Goal:
  Upgrade from "it moves" to "it recognizes."

Tasks:
  Choose a detection approach
    For the first version, choose only one path, for example:
      an existing object detection model
      recognize one or two classes first: drone / person / moving target
  Build a demo dataset
    No need to be large and comprehensive at first
    Collect usable data targeted at the demo scenario
  Set trigger logic
    confidence threshold
    persistence threshold
    false alarm suppression

Outputs:
  Detection demo
  basic confusion notes
  threshold settings table

Success criteria:
  Stably captures targets at least in controlled environments
  False alarm rate is acceptable in the demo scenario
  Reaction time is fast enough to feel "real-time"

Note:
  Don't pursue military-grade accuracy in this stage.
  Only pursue: stability in the demo scenario.
```

### Week 5: Reaction Module Integration (Reaction Integration)

```text
Goal:
  Turn detection results into a "dramatic reaction that judges can perceive."

Tasks:
  Design a three-level response:
    low: LED
    medium: LED + buzzer
    high: LED + buzzer + laser
  Adjust response rhythm
    flashing frequency
    sound duration
    laser activation conditions
  Avoid accidental triggering
    add cooldown
    add confirmation window

Outputs:
  threat reaction state machine
  reaction timing table
  a complete demo recording

Success criteria:
  The reaction is not "the whole device convulses as soon as something is detected," but has layers.
```

### Week 6: Display and User Interface (UX Layer)

```text
Goal:
  Let people know at a glance what the system is doing.

Tasks:
  OLED display design
    scan
    target detected
    confidence
    reaction time
  Decide whether to also build a simple app / laptop window demo
  Unify state names and UI copy

Outputs:
  UI state chart
  OLED screen style
  demo display logic

Success criteria:
  Even without the Project Owner explaining, a bystander looking at the screen knows what is happening.
```

### Weeks 7–8: Helmet Integration and Appearance Forming (Packaging Alpha)

```text
Goal:
  Turn the desktop nervous system into a prototype product that can truly be worn.

Tasks:
  Do the first assembly, then complete:
    counterweight balance
    cable management
    switch position
    mount strength
    basic shell finishing

Outputs:
  3D sketch / mounting position diagram
  first full-machine photos
  wearing test records

Success criteria:
  Can be worn for 5–10 minutes without it being too uncomfortable
  Does not come loose when moving
  Does not look like exposed development boards tied together haphazardly
```

This step is critical, because the P1 document has already listed **3D modeling sketches and module position diagrams** as the top priority for the next step.

### Week 9: Demo Script and Filming (Demo Beta)

```text
Goal:
  Turn the engineering prototype into a demo that can be presented, shown, and pitched.

Tasks:
  Design a 60–120 second demo script
  Set a single clear scenario
    for example:
      a patrol officer detects an approaching small aerial target
  Shoot two videos:
    engineering version: shows how the system works
    competition version: shows problem → detection → reaction → value

Outputs:
  Demo script
  Shot list
  Beta video

Success criteria:
  When an outsider watches it for the first time, they understand within 30 seconds:
    what it is
    what it does
    why it is worth existing
```

This is also the work the P1 document has explicitly listed.

### Week 10: Freeze and Pre-Stage Refinement (MVP Freeze)

```text
Goal:
  No more casual changes to core functions; only fix stability and presentation quality.

Tasks:
  fix bugs
  fix cables
  fix appearance
  fix UI copy
  complete the pitch deck and one-page explanation
  do at least 3 full rehearsals

Outputs:
  MVP freeze version
  final BOM
  demo checklist
  pitch support material

Success criteria:
  By the end of this week, the Project Owner has in hand not a concept, but:
  a HADES MVP ready to present on stage.
```

---

## VII. How the "Innovation Maturity" Climbs

In addition to the timeline, an innovation stage framework is needed.
Translated into a more engineering-oriented maturity ladder:

```text
Level 1: Concept-valid
  You can clearly explain what it is and how the modules are divided.
  The P1 report has already achieved this level.

Level 2: Function-valid
  The desktop system runs, and detection and response are connected.

Level 3: System-valid
  Sensing, AI, response, and display operate stably together.

Level 4: Form-valid
  The system is successfully installed in the helmet, with wearability.

Level 5: Demo-valid
  A single scenario can be fully demonstrated without relying on lots of verbal patching.

Level 6: Pitch-valid
  Outsiders see it as an "early-stage product," not an "engineering class project."
```

The goal of the first milestone is to go from Level 1 to Level 6.
**Not to rush toward future platformization.**

---

## VIII. Actual Flow Diagram of the Full MVP

The first goal can be condensed into this line:

```text
task freeze
→ desktop connected
→ AI usable
→ response integrated
→ UX display
→ helmet packaging
→ demo script
→ freeze and take to stage
```

Within this line, there are only 4 real critical path items:

```text
Camera
→ AI detection
→ GPIO reaction
→ Wearable packaging
```

As long as these four are not connected, everything else is decoration.

---

## IX. Roles and Staffing

### Revised Three-Person Division

**Project Owner: 6 work packages**

```text
F, G, I, J, O, Q
```

| Work Package | Content |
|---|---|
| **F** | Test Harness / Benchmark Layer |
| **G** | Training / Fine-tuning Pipeline |
| **I** | Tracking / Filtering Layer |
| **J** | Actuator Mock / Driver Layer |
| **O** | Benchmark & Stability Run |
| **Q** | Quick Config Tool |

Project Owner role:

> **training owner + decision owner + final integration owner**

**Helper 1: 6 work packages**

```text
A, B, H, K, P, R
```

| Work Package | Content |
|---|---|
| **A** | Video Input Layer |
| **B** | Detection Layer |
| **H** | False Positive / False Negative Analysis |
| **K** | Integration Test Support |
| **P** | Diagnostic Mode |
| **R** | Error Logging Improvement |

Helper 1 role:

> **input + inference wrapper + reliability support**

He is responsible for packaging the image and model inference, and assisting the Project Owner with error case analysis, but **does not lead training direction**.

**Helper 2: 6 work packages**

```text
C, D, E, L, M, N
```

| Work Package | Content |
|---|---|
| **C** | Dataset Pipeline |
| **D** | UI / Monitoring Layer |
| **E** | Logging / Replay Layer |
| **L** | UI integration support |
| **M** | Replay Demo Support |
| **N** | Final Log / Telemetry Cleanup |

Helper 2 role:

> **dataset + UI + logging + demo support**

He is responsible for the data and demo support, but how the model is trained and which model is chosen is still decided by the Project Owner.

### Final Version

```text
Project Owner: F G I J O Q
Helper 1: A B H K P R
Helper 2: C D E L M N
```

### Explanation of Division for Helpers

When explaining the division of labor to Helpers, you can say: the HADES MVP's goal is to build a **demonstration prototype** that can complete the main chain of "automatic recognition → non-destructive audio-visual response → display of results." The P1 document also explicitly lists the AI core, demo response, and display modules as core modules.

> Our three-person coding division is roughly this:
>
> **Helper 1 is mainly responsible for the "seeing, detecting, testing, diagnosing" part of HADES.**
> That means you will be responsible for reading camera / video frames into the system, connecting YOLO detection, outputting bbox, class, and confidence, and then helping with FP/FN error analysis, integration testing, diagnostic mode, and error logging.
>
> Your work packages are:
> **A: Video Input Layer**
> **B: Detection Layer**
> **H: False Positive / False Negative Analysis**
> **K: Integration Test Support**
> **P: Diagnostic Mode**
> **R: Error Logging Improvement**
>
> In short: you make sure HADES can "see targets, output detection results, and let us find the cause when something goes wrong."
>
> ---
>
> **Helper 2 is mainly responsible for the "data, UI, records, replay, demo support" part of HADES.**
> That means you will be responsible for dataset organization, labeling data, UI / monitoring display, logging / replay, demo fallback, and the final telemetry cleanup.
>
> Your work packages are:
> **C: Dataset Pipeline**
> **D: UI / Monitoring Layer**
> **E: Logging / Replay Layer**
> **L: UI integration support**
> **M: Replay Demo Support**
> **N: Final Log / Telemetry Cleanup**
>
> In short: you make sure HADES has clean data, can display status, can record results, and can replay as a fallback during demos.
>
> ---
>
> I will handle the overall architecture, AI training, decision / state machine, and final integration.
> So you are not here to "do odd jobs"; each of you owns a truly important main line in the HADES coding system.

**Shortest spoken version:**

> **Helper 1: camera, AI detection, testing, debugging.**
> **Helper 2: dataset, UI, logging, replay.**
> **Project Owner: architecture, training, decision, final integration.**

---

## X. One-Sentence Summary

Put as plainly as possible:

> **The first HADES MVP is not meant to prove that it will one day shoot down all drones; it is meant to prove that a wearable, recognizing, responding, and demonstrable HADES Core can be built today.**

What is needed now is not a bigger ambition, but this very practical path:

> **Within 10 weeks, turn the concept into a full machine ready to present on stage.**
