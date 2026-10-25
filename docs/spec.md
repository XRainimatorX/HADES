# HADES Packet Specification

`docs/spec.md` — Living document. Format version **0.1**.

For every work package, this document lists the packets it produces, the exact format of each packet, the meaning of every field, and the functions that produce them. The types and signatures here are implemented in `src/hades/contracts.py`; any change requires the Project Owner's approval and must update both files together.

**Notation used in format blocks:** `int`, `float`, `bool`, `str`; `list[X]` is a list of X; `X | null` means the value may be empty; `"a" | "b"` lists the only allowed values; `# ns` marks nanoseconds from the monotonic clock.

---

### A — Video Input

**Packet: FramePacket**

One packet per frame delivered by the camera or video file. It is the starting point of every detection: all later runtime packets trace back to one FramePacket.

```text
FramePacket {
  frame_id:        int
  timestamp:       int                          # ns
  image:           ndarray[height, width, 3]    uint8, BGR
  source_type:     "picam" | "webcam" | "video"
  schema_version:  str                          "0.1"
}
```

| Data | Expected format | Description and meaning |
|---|---|---|
| `frame_id` | Integer; starts at 0, +1 per frame | Identifies the frame within a run. Every later packet derived from this frame carries the same ID, so results can be traced back to the exact image. |
| `timestamp` | Integer, nanoseconds, monotonic clock | The moment the image was obtained. End-to-end latency is measured from this time, so it must be recorded as early as possible. |
| `image` | Array, height × width × 3, 8-bit, BGR | The picture itself, in the colour order used by OpenCV. |
| `source_type` | String: `picam`, `webcam`, or `video` | Where the frame came from. Lets later analysis separate live results from replayed ones. |
| `schema_version` | String, e.g. `"0.1"` | Version of this packet format. A reader checks it before interpreting the packet. |

**Function signatures**

```text
Source.open()  -> None
Source.read()  -> FramePacket | None
Source.close() -> None
```

| Function | Description and meaning |
|---|---|
| `open()` | Connects to the camera or opens the video file. Must be called before reading. |
| `read()` | Returns the newest frame. Returns nothing when the video ends or the camera is lost, so the system knows the input has stopped. |
| `close()` | Releases the camera or file. Safe to call more than once. |

---

### B — Detection

**Packet: DetectionPacket**

One packet per frame, containing everything the model found in that frame. A frame with nothing found still produces a packet with an empty list, so every frame has a matching result.

```text
DetectionPacket {
  frame_id:        int
  detections:      list[Detection]      may be empty
  inference_ms:    float
  timestamp:       int                  # ns
  t_detect:        int                  # ns
  schema_version:  str                  "0.1"
}

Detection {
  bbox:            [float, float, float, float]    x1, y1, x2, y2 in pixels
  class_name:      "drone"
  confidence:      float                           0.0–1.0
}
```

| Data | Expected format | Description and meaning |
|---|---|---|
| `frame_id` | Integer | The frame these detections belong to. |
| `detections` | List of Detection; may be empty | Every object the model found above the minimum confidence. |
| `inference_ms` | Decimal, milliseconds | Time spent running the model alone, excluding preparation and post-processing. Shows how fast the model is on the current hardware. |
| `timestamp` | Integer, nanoseconds | Copied unchanged from the frame, so latency can still be measured from the original capture. |
| `t_detect` | Integer, nanoseconds, monotonic clock | When this stage finished. Compared with `timestamp`, shows how much delay the detection stage adds. |
| `schema_version` | String | Version of this packet format. |
| `bbox` | Four decimals `[x1, y1, x2, y2]`, pixels, origin top-left | The box around the object, in the original frame's coordinates even if the model resized the image internally. |
| `class_name` | String; v0.1 always `drone` | What the object is. v0.1 recognises only consumer drones. |
| `confidence` | Decimal, 0.0–1.0 | How sure the model is. Higher means more certain. |

**Function signatures**

```text
Detector.load(model_path: str)       -> None
Detector.detect(frame: FramePacket)  -> DetectionPacket
```

| Function | Description and meaning |
|---|---|
| `load()` | Loads the model file once before detection starts. |
| `detect()` | Runs the model on one frame. The same frame always gives the same result, so results can be reproduced. |

---

### C — Dataset

**Packet: Dataset package**

The training data, stored under `data/`. It is a set of files rather than a runtime message.

```text
data/
├── classes.yaml
├── annotation_guideline.md
└── dataset_v1/
    ├── images/{train,val,test}/<name>.jpg
    ├── labels/{train,val,test}/<name>.txt
    └── split_manifest.csv
```

`labels/.../<name>.txt` — one line per object; empty file if the image has no drone:

```text
<class_id> <x_center> <y_center> <width> <height>
0 0.4953 0.3125 0.0336 0.0396
```

`classes.yaml`:

```yaml
schema_version: "0.1"
names:
  0: drone
```

`split_manifest.csv`:

```text
image,split,source_clip,frame_index,num_objects
images/train/clip03_000120.jpg,train,clip03.mp4,120,1
```

| Data | Expected format | Description and meaning |
|---|---|---|
| Images | JPEG files | The pictures used to train and test the model. |
| Label line | `class_id x_center y_center width height`; `class_id` integer, the rest decimals 0.0–1.0 relative to image size | Where each drone is in the image, in the standard YOLO format. An empty file teaches the model what is not a drone. |
| `names` | Mapping, integer to string | Translates class numbers in label files into names. |
| `image` | String, path relative to `dataset_v1/` | The image this row describes. |
| `split` | String: `train`, `val`, `test` | Whether the image is used for training, tuning, or final testing. |
| `source_clip` | String, video file name | The video the frame came from. Frames from the same video must stay in the same split, or test results will look better than reality. |
| `frame_index` | Integer | Frame number within the source video. |
| `num_objects` | Integer | Number of drones labelled in the image. |
| Annotation guideline | Markdown file | The rules annotators follow, so every label is drawn the same way. |

**Function signatures**

```text
extract_frames(video_path: str, out_dir: str, every_n: int)            -> list[str]
build_split(dataset_dir: str, ratios: tuple[float, float, float],
            seed: int)                                                -> str
validate_dataset(dataset_dir: str)                                    -> list[str]
```

| Function | Description and meaning |
|---|---|
| `extract_frames()` | Saves every n-th frame of a video as an image and returns the saved paths. |
| `build_split()` | Assigns images to train, validation, and test by source video, writes the split manifest, and returns its path. A fixed seed makes the split repeatable. |
| `validate_dataset()` | Checks that every image has a label file, every label line is valid, and the manifest matches the files. Returns a list of problems; empty means the dataset is valid. |

---

### D — UI / Monitoring

**Packets: none.**
D only displays information on the OLED screen and the web monitor; it produces no data for other packages.

**Function signatures**

```text
OledDisplay.update(state: SystemState, fps: float)  -> None
WebMonitor.start(port: int)                         -> None
WebMonitor.publish(message: object)                 -> None
```

| Function | Description and meaning |
|---|---|
| `OledDisplay.update()` | Shows the current system state and frame rate on the helmet screen. |
| `WebMonitor.start()` | Starts the development web page on the given port. |
| `WebMonitor.publish()` | Pushes any runtime packet to the web page for live viewing. |

---

### E — Logging / Replay

**Packet: Run log**

One folder per run, outside the repository.

```text
runs/<run_id>/
├── meta.json
└── events.jsonl
```

`meta.json`:

```text
RunMetadata {
  run_id:          str      UUID
  started_at:      str      ISO 8601, UTC
  git_commit:      str
  git_dirty:       bool
  model_path:      str
  model_sha256:    str
  config_sha256:   str
  hardware:        str
  source_type:     "picam" | "webcam" | "video"
  source_uri:      str
  schema_version:  str      "0.1"
}
```

`events.jsonl` — one JSON object per line, in the order recorded:

```text
EventRecord {
  type:            "frame" | "detection" | "tracking" | "state"
                   | "command" | "status" | "error"
  ...              all fields of that packet, except image
  schema_version:  str      "0.1"
}
```

```json
{"type": "frame", "frame_id": 1042, "timestamp": 58213377001200, "source_type": "webcam", "height": 720, "width": 1280, "schema_version": "0.1"}
```

| Data | Expected format | Description and meaning |
|---|---|---|
| `run_id` | String, UUID | Unique name of this run; links every report back to its log. |
| `started_at` | String, ISO 8601, UTC | When the run began, in real-world time. |
| `git_commit` | String, commit hash | Which version of the code ran. |
| `git_dirty` | True / false | Whether the code had unsaved changes, which would make the run impossible to reproduce exactly. |
| `model_path` | String | Which model file was used. |
| `model_sha256` | String, SHA-256 | Fingerprint of the model file, proving exactly which model ran. |
| `config_sha256` | String, SHA-256 | Fingerprint of the settings used. |
| `hardware` | String | Name of the hardware setup, from the configuration. |
| `source_type` | String | Camera or video. |
| `source_uri` | String | Camera ID or video file path. |
| `type` | String, one of the listed record types | Says which packet this line holds. |
| Packet fields | As defined in that packet's section | The full packet, so the run can be analysed or replayed later. Images are replaced by `height` and `width`. |
| `schema_version` | String | Version of the format. |

**Packet: FramePacket (replay)**

During replay, E produces FramePackets in exactly the format defined in section A, with `source_type` set to `video`.

**Function signatures**

```text
Telemetry.start_run(meta: RunMetadata)  -> None
Telemetry.record(message: object)       -> None
Telemetry.end_run()                     -> None
ReplaySource.read()                     -> FramePacket | None
```

| Function | Description and meaning |
|---|---|
| `start_run()` | Creates the run folder and writes `meta.json`. |
| `record()` | Adds one packet to `events.jsonl`. It must not slow the system down while writing. |
| `end_run()` | Finishes writing and closes the log. |
| `ReplaySource.read()` | Plays back a recorded video as if it were live, so a run can be repeated exactly. |

---

### F — Test Harness / Benchmark

**Packet: Benchmark report**

One JSON file per measurement: `bench/reports/<run_id>.json`.

```text
BenchmarkReport {
  run_id:          str
  kind:            "latency" | "fps" | "memory" | "range"
                   | "false_alarm" | "stability"
  hardware:        str
  model_sha256:    str
  samples:         int
  result:          { <name>: float, ... }
  schema_version:  str      "0.1"
}
```

```json
{"run_id": "3f2c9a1e-...", "kind": "latency", "hardware": "dev-laptop",
 "model_sha256": "9b1e...", "samples": 40,
 "result": {"median_ms": 31.2, "p95_ms": 48.7}, "schema_version": "0.1"}
```

| Data | Expected format | Description and meaning |
|---|---|---|
| `run_id` | String | The run that was measured; points to its log. |
| `kind` | String, one of the listed kinds | What was measured. |
| `hardware` | String | Hardware the measurement ran on. Results are only comparable on the same hardware. |
| `model_sha256` | String, SHA-256 | Model that was measured. |
| `samples` | Integer | How many measurements the result is based on. |
| `result` | Map of name to decimal | The measured values. Typical and worst-case values are both reported. |
| `schema_version` | String | Version of this file format. |

**Function signatures**

```text
run_benchmark(kind: str, config_path: str, clip: str)  -> BenchmarkReport
write_report(report: BenchmarkReport, path: str)       -> None
```

| Function | Description and meaning |
|---|---|
| `run_benchmark()` | Runs one kind of measurement on a fixed test clip with the given settings. |
| `write_report()` | Saves the report so different versions can be compared later. |

---

### G — Training / Fine-tuning

**Packet: Model artifact**

One folder per trained model.

```text
models/<model_name>/
├── model.<pt | onnx | hef | engine>
└── model.yaml
```

`model.yaml`:

```yaml
schema_version: "0.1"
name: yolov8n-drone
version: "0.1.3"
format: pt                      # pt | onnx | hef | engine
input_size: [640, 640]          # [width, height]
classes:
  0: drone
dataset: dataset_v1
sha256: 9b1e...
metrics:
  precision: 0.88
  recall: 0.81
  map50: 0.85
```

| Data | Expected format | Description and meaning |
|---|---|---|
| Model file | `.pt`, `.onnx`, `.hef`, or `.engine` | The trained model in the format the hardware needs. |
| `name` | String | Human-readable model name. |
| `version` | String, e.g. `0.1.3` | Distinguishes successive training results. |
| `format` | String: `pt`, `onnx`, `hef`, `engine` | Which file format the model file is. |
| `input_size` | Two integers `[width, height]` | Image size the model expects. |
| `classes` | Mapping, integer to string | Must match `data/classes.yaml`, otherwise detections are labelled wrongly. |
| `dataset` | String, e.g. `dataset_v1` | Which dataset version trained it. |
| `sha256` | String, SHA-256 | Fingerprint of the model file. |
| `metrics` | `precision`, `recall`, `map50`, decimals 0.0–1.0 | Accuracy on the test split. Used to choose the demo model. |
| `schema_version` | String | Version of the model card format. |

**Packet: Prediction file**

`predictions.jsonl`, one line per evaluated image.

```text
Prediction {
  image:           str               path within dataset_v1/
  model:           str               name and version
  detections:      list[Detection]   as in section B
  schema_version:  str               "0.1"
}
```

| Data | Expected format | Description and meaning |
|---|---|---|
| `image` | String, path | The image that was evaluated. |
| `model` | String | The model that produced the result. |
| `detections` | List of Detection | What the model found. Compared with the label file to find mistakes. |
| `schema_version` | String | Version of this file format. |

**Function signatures**

```text
train(config_path: str)                       -> str
evaluate(model_dir: str, split: str)          -> str
export(model_dir: str, target_format: str)    -> str
```

| Function | Description and meaning |
|---|---|
| `train()` | Trains a model with the given settings and returns the new model folder. |
| `evaluate()` | Runs the model on a dataset split, writes the prediction file and metrics, and returns the prediction file path. |
| `export()` | Converts a trained model into a hardware-specific format and returns the new file path. |

---

### H — False Positive / False Negative Analysis

**Packet: Error case report**

`error_case_report.json`.

```text
ErrorCaseReport {
  model:           str
  conf:            float              confidence level analysed
  cases:           list[ErrorCase]
  schema_version:  str                "0.1"
}

ErrorCase {
  image:           str
  case_type:       "false_positive" | "false_negative"
  cause:           str                e.g. "bird", "small_target", "backlight",
                                      "blur", "occlusion"
  confidence:      float | null
  note:            str
}
```

| Data | Expected format | Description and meaning |
|---|---|---|
| `model` | String | The model analysed. |
| `conf` | Decimal, 0.0–1.0 | The confidence level at which mistakes were counted. |
| `image` | String, path | The image where the mistake happened. |
| `case_type` | String: `false_positive` or `false_negative` | False positive: the model found a drone that is not there. False negative: the model missed a real drone. |
| `cause` | String, short lower-case tag | Why the mistake happened, grouped so patterns become visible. |
| `confidence` | Decimal 0.0–1.0, or empty | The model's confidence for the mistaken detection; empty for a miss with no detection. |
| `note` | String | Free comment from the analyst. |
| `schema_version` | String | Version of this file format. |

**Packet: Threshold suggestion**

`threshold_suggestion.yaml`.

```yaml
schema_version: "0.1"
model: yolov8n-drone-0.1.3
suggestions:
  - setting: decision.conf_threshold
    value: 0.55
    evidence: "0.50 → 12 false alarms, 3 misses; 0.55 → 4 false alarms, 4 misses"
```

| Data | Expected format | Description and meaning |
|---|---|---|
| `setting` | String, a configuration key | Which setting the suggestion is for. |
| `value` | Number | The recommended value. |
| `evidence` | String | The numbers that justify it. |
| `schema_version` | String | Version of this file format. |

**Function signatures**

```text
analyse(predictions_path: str, dataset_dir: str, conf: float)  -> ErrorCaseReport
suggest_thresholds(report: ErrorCaseReport)                    -> ThresholdSuggestion
```

| Function | Description and meaning |
|---|---|
| `analyse()` | Compares predictions with labels at a given confidence level and lists every mistake. |
| `suggest_thresholds()` | Turns the mistake list into recommended settings. |

---

### I — Tracking / Filtering

**Packet: TrackingPacket**

One packet per frame, containing every object currently being followed. It turns frame-by-frame detections into stable targets.

```text
TrackingPacket {
  frame_id:        int
  targets:         list[Track]      may be empty
  timestamp:       int              # ns
  t_track:         int              # ns
  schema_version:  str              "0.1"
}

Track {
  target_id:            int
  class_name:           "drone"
  confidence_smoothed:  float                           0.0–1.0
  bbox:                 [float, float, float, float]    x1, y1, x2, y2 in pixels
  is_confirmed:         bool
}
```

| Data | Expected format | Description and meaning |
|---|---|---|
| `frame_id` | Integer | The frame this result belongs to. |
| `targets` | List of Track; may be empty | Every object currently tracked. |
| `timestamp` | Integer, nanoseconds | Copied unchanged from the frame. |
| `t_track` | Integer, nanoseconds, monotonic clock | When this stage finished. |
| `schema_version` | String | Version of this packet format. |
| `target_id` | Integer | The same physical object keeps the same ID from frame to frame. Never reused within a run. |
| `class_name` | String; v0.1 always `drone` | What the object is. |
| `confidence_smoothed` | Decimal, 0.0–1.0 | Confidence averaged over recent frames, so a single uncertain frame does not cause a flicker. |
| `bbox` | Four decimals `[x1, y1, x2, y2]`, pixels | Where the object is now. |
| `is_confirmed` | True / false | True once the object has been seen in enough consecutive frames to be trusted, filtering out one-frame false detections. |

**Function signatures**

```text
Tracker.update(det: DetectionPacket)  -> TrackingPacket
Tracker.reset()                       -> None
```

| Function | Description and meaning |
|---|---|
| `update()` | Matches new detections with existing tracks and returns the updated target list. |
| `reset()` | Clears all tracks, for example after the camera restarts. |

---

### Decision Layer

**Packet: SystemState**

Describes what the system is currently doing.

```text
SystemState {
  state:           "IDLE" | "SCANNING" | "CANDIDATE" | "CONFIRMED"
                   | "ALERTING" | "COOLDOWN"
  previous:        same values as state
  frame_id:        int
  timestamp:       int        # ns
  schema_version:  str        "0.1"
}
```

| Data | Expected format | Description and meaning |
|---|---|---|
| `state` | String, one of the listed values | The current state. IDLE: not running or no video. SCANNING: watching, nothing found. CANDIDATE: possible drone, checking. CONFIRMED: drone confirmed. ALERTING: alert outputs active. COOLDOWN: alert finished, waiting before another. |
| `previous` | Same values as `state` | The state before the latest change, so every transition can be traced. |
| `frame_id` | Integer | The frame that caused the latest change. |
| `timestamp` | Integer, nanoseconds | Capture time of that frame. |
| `schema_version` | String | Version of this packet format. |

**Packet: ActuatorCommand**

Tells the alert outputs what to do. Produced only when the outputs need to change.

```text
ActuatorCommand {
  alert_level:     0 | 1
  led_mode:        "off" | "on" | "blink"
  buzzer_mode:     "off" | "on" | "pulse"
  laser_on:        bool
  frame_id:        int
  timestamp:       int        # ns
  t_command:       int        # ns
  schema_version:  str        "0.1"
}
```

| Data | Expected format | Description and meaning |
|---|---|---|
| `alert_level` | Integer: `0` or `1` | 0 means no alert; 1 means alert. v0.1 has no grading. When 0, every output is off. |
| `led_mode` | String: `off`, `on`, `blink` | What the LED should do. |
| `buzzer_mode` | String: `off`, `on`, `pulse` | What the buzzer should do. |
| `laser_on` | True / false | Whether the laser indicator is on. |
| `frame_id` | Integer | The frame that caused this command. |
| `timestamp` | Integer, nanoseconds | Capture time of that frame. |
| `t_command` | Integer, nanoseconds, monotonic clock | When the command was issued. `t_command` minus `timestamp` is the end-to-end latency. |
| `schema_version` | String | Version of this packet format. |

**Function signatures**

```text
DecisionEngine.step(trk: TrackingPacket)       -> tuple[SystemState, ActuatorCommand | None]
DecisionEngine.on_source_lost(timestamp: int)  -> ActuatorCommand | None
```

| Function | Description and meaning |
|---|---|
| `step()` | Decides, from the latest tracking result, the system state and whether the alert outputs must change. Returns no command when nothing needs to change. |
| `on_source_lost()` | Called when the video stops. Returns a command to switch the outputs off if an alert was active. |

---

### J — Actuator Mock / Driver

**Packet: ActuatorStatus**

The actual state of the alert outputs after the latest command.

```text
ActuatorStatus {
  led_mode:               "off" | "on" | "blink"
  buzzer_mode:            "off" | "on" | "pulse"
  laser_on:               bool
  last_command_frame_id:  int | null
  healthy:                bool
  t_status:               int        # ns
  schema_version:         str        "0.1"
}
```

| Data | Expected format | Description and meaning |
|---|---|---|
| `led_mode` | String: `off`, `on`, `blink` | What the LED is actually doing. |
| `buzzer_mode` | String: `off`, `on`, `pulse` | What the buzzer is actually doing. |
| `laser_on` | True / false | Whether the laser is actually on. |
| `last_command_frame_id` | Integer, or empty | Frame ID of the last command applied; empty if none yet. |
| `healthy` | True / false | False if any output failed to respond. |
| `t_status` | Integer, nanoseconds, monotonic clock | When this status was read. |
| `schema_version` | String | Version of this packet format. |

**Function signatures**

```text
Alert.send(cmd: ActuatorCommand)  -> None
Alert.status()                    -> ActuatorStatus
```

| Function | Description and meaning |
|---|---|
| `send()` | Applies a command to the outputs. Sending the same command twice changes nothing. A mock version records commands instead of driving hardware, for testing on a laptop. |
| `status()` | Reports what the outputs are actually doing. |

---

### K — Integration Test Support

**Packet: IntegrationResult**

One entry per integration or regression test.

```text
IntegrationResult {
  test_name:       str
  result:          "pass" | "fail"
  run_id:          str
  source:          "live" | "replay"
  note:            str
  schema_version:  str        "0.1"
}
```

| Data | Expected format | Description and meaning |
|---|---|---|
| `test_name` | String | Which test ran. |
| `result` | String: `pass` or `fail` | Outcome. |
| `run_id` | String | The run log produced by the test, for investigating failures. |
| `source` | String: `live` or `replay` | Whether the test used a live camera or a recording, for comparing the two. |
| `note` | String | Reason for failure or other comment. |
| `schema_version` | String | Version of this format. |

**Function signatures**

```text
run_integration(clip: str, config_path: str)  -> IntegrationResult
```

| Function | Description and meaning |
|---|---|
| `run_integration()` | Runs the full pipeline on a clip and checks that a complete, correctly formatted log is produced. |

---

### L — UI Integration Support

**Packet: StateStyle**

How each system state is presented on screen.

```text
StateStyle {
  state:           one of the SystemState values
  label:           str
  colour:          str        hex, e.g. "#FF3B30"
  schema_version:  str        "0.1"
}
```

| Data | Expected format | Description and meaning |
|---|---|---|
| `state` | String, a SystemState value | The state being styled. |
| `label` | String | Text shown to the viewer, written so someone unfamiliar with the system understands it. |
| `colour` | String, hex code | Display colour, so the state can be recognised at a glance. |
| `schema_version` | String | Version of this format. |

**Function signatures**

```text
state_style(state: str)  -> StateStyle
```

| Function | Description and meaning |
|---|---|
| `state_style()` | Returns the label and colour for a state, so every screen shows states the same way. |

---

### M — Replay Demo Support

**Packet: Demo clip set**

The recordings used when a live demo is not possible.

```text
data/demo/
├── <clip_name>.mp4
└── demo_manifest.yaml
```

`demo_manifest.yaml`:

```yaml
schema_version: "0.1"
clips:
  - name: approach_daylight
    file: approach_daylight.mp4
    duration_s: 42.0
    description: "Single drone approaches from the left; one alert expected"
```

| Data | Expected format | Description and meaning |
|---|---|---|
| Clips | MP4 video files | Recordings that reliably show a detection and alert. |
| `name` | String | Short identifier for the clip. |
| `file` | String, file name | The video file. |
| `duration_s` | Decimal, seconds | Clip length, for planning the demo time. |
| `description` | String | What the clip shows, so the presenter picks the right one quickly. |
| `schema_version` | String | Version of the manifest format. |

**Function signatures**

```text
run_demo(clip: str, config_path: str)  -> None
```

| Function | Description and meaning |
|---|---|
| `run_demo()` | Plays a demo clip through the full system as a fallback when the live camera cannot be used. |

---

### N — Final Log / Telemetry Cleanup

**Packet: Session summary**

`runs/<run_id>/summary.json`.

```text
SessionSummary {
  run_id:             str
  duration_s:         float
  frames:             int
  detections:         int
  alerts:             int
  median_latency_ms:  float | null
  errors:             int
  schema_version:     str        "0.1"
}
```

| Data | Expected format | Description and meaning |
|---|---|---|
| `run_id` | String | The run summarised. |
| `duration_s` | Decimal, seconds | How long the run lasted. |
| `frames` | Integer | Number of frames processed. |
| `detections` | Integer | Number of detections. |
| `alerts` | Integer | Number of times the system entered ALERTING. |
| `median_latency_ms` | Decimal milliseconds, or empty | Typical end-to-end latency for the run; empty if there were no alerts. |
| `errors` | Integer | Number of error records. |
| `schema_version` | String | Version of this format. |

**Packet: Session export**

`runs/<run_id>/events.csv` — the run's events as a spreadsheet, one row per record:

```text
type,frame_id,timestamp,state,alert_level,num_detections,num_targets,code
frame,1042,58213377001200,,,,,
detection,1042,58213377001200,,,1,,
```

| Data | Expected format | Description and meaning |
|---|---|---|
| Columns | Fixed header as shown; empty cell where a field does not apply | Lets the run be opened and filtered in a spreadsheet without programming. |

**Function signatures**

```text
summarise(run_dir: str)                      -> SessionSummary
export_session(run_dir: str, out_dir: str)   -> str
```

| Function | Description and meaning |
|---|---|
| `summarise()` | Produces the one-page summary of a run. |
| `export_session()` | Writes the run's events as a spreadsheet file and returns its path. |

---

### O — Benchmark & Stability Run

**Packet: Benchmark report (stability)**

Same format as the benchmark report in section F, with `kind` set to `stability`. Its `result` contains:

```text
result {
  duration_s:       float
  fps_min:          float
  fps_avg:          float
  memory_start_mb:  int
  memory_end_mb:    int
  errors:           int
}
```

| Data | Expected format | Description and meaning |
|---|---|---|
| `duration_s` | Decimal, seconds | How long the system ran continuously. |
| `fps_min` | Decimal, frames per second | The worst frame rate seen; shows whether performance drops over time. |
| `fps_avg` | Decimal, frames per second | Typical frame rate. |
| `memory_start_mb` | Integer, megabytes | Memory used at the beginning. |
| `memory_end_mb` | Integer, megabytes | Memory used at the end. A large increase means a memory leak. |
| `errors` | Integer | Number of errors during the run. |

**Function signatures**

```text
run_stability(duration_s: float, config_path: str)  -> BenchmarkReport
```

| Function | Description and meaning |
|---|---|
| `run_stability()` | Runs the system for the given time and reports whether it stays stable. |

---

### P — Diagnostic Mode

**Packet: DiagnosticStatus**

A health check of the whole system at one moment.

```text
DiagnosticStatus {
  camera_alive:     bool
  model_loaded:     bool
  fps:              float
  state:            one of the SystemState values
  actuator_status:  ActuatorStatus      as in section J
  t_status:         int                 # ns
  schema_version:   str                 "0.1"
}
```

| Data | Expected format | Description and meaning |
|---|---|---|
| `camera_alive` | True / false | Whether frames are arriving. |
| `model_loaded` | True / false | Whether the detection model is ready. |
| `fps` | Decimal, frames per second | Current processing speed. |
| `state` | String, a SystemState value | What the system is currently doing. |
| `actuator_status` | ActuatorStatus | Whether the alert outputs are working. |
| `t_status` | Integer, nanoseconds, monotonic clock | When this check was taken. |
| `schema_version` | String | Version of this packet format. |

**Function signatures**

```text
Diagnostics.snapshot()  -> DiagnosticStatus
```

| Function | Description and meaning |
|---|---|
| `snapshot()` | Collects the current health of every part, so a fault can be located at a glance. |

---

### Q — Quick Config Tool

**Packet: Configuration**

`configs/default.yaml`. Each section holds the settings of one part of the system.

```yaml
schema_version: "0.1"
hardware:
  name: dev-laptop
source:
  type: webcam                  # picam | webcam | video
  uri: "0"
  realtime: true
detector:
  model_path: models/<model_name>/model.pt
  min_confidence: 0.25
tracker:
  confirm_frames: 3
  lost_frames: 5
decision:
  conf_threshold: 0.50
  alert_duration_s: 3.0
  cooldown_s: 5.0
alert:
  on_alert:
    led_mode: blink             # off | on | blink
    buzzer_mode: pulse          # off | on | pulse
    laser_on: false
telemetry:
  runs_dir: runs
```

| Data | Expected format | Description and meaning |
|---|---|---|
| `hardware.name` | String | Name of the current hardware setup. |
| `source.type` | String: `picam`, `webcam`, `video` | Which video source to use. |
| `source.uri` | String | Camera ID or video file path. |
| `source.realtime` | True / false | For video files: play at normal speed (true) or as fast as possible (false). |
| `detector.model_path` | String | Model file to load. |
| `detector.min_confidence` | Decimal, 0.0–1.0 | Detections below this are discarded immediately. |
| `tracker.confirm_frames` | Integer | Consecutive frames needed before a target is confirmed. |
| `tracker.lost_frames` | Integer | Consecutive missed frames before a target is dropped. |
| `decision.conf_threshold` | Decimal, 0.0–1.0 | Smoothed confidence a target needs to be treated as a possible drone. |
| `decision.alert_duration_s` | Decimal, seconds | How long an alert lasts. |
| `decision.cooldown_s` | Decimal, seconds | Pause after an alert before another can start, to avoid repeated alarms. |
| `alert.on_alert.led_mode` | String: `off`, `on`, `blink` | LED behaviour during an alert. |
| `alert.on_alert.buzzer_mode` | String: `off`, `on`, `pulse` | Buzzer behaviour during an alert. |
| `alert.on_alert.laser_on` | True / false | Whether the laser turns on during an alert. Off by default for eye safety. |
| `telemetry.runs_dir` | String | Folder where run logs are written. |
| `schema_version` | String | Version of the configuration format. |

The numbers in the example are starting values only; they are replaced once measured values are available.

**Function signatures**

```text
load_config(path: str)       -> Config
validate_config(cfg: Config) -> list[str]
```

| Function | Description and meaning |
|---|---|
| `load_config()` | Reads the configuration file, so settings can be changed without editing code. |
| `validate_config()` | Checks every value is present and in range. Returns a list of problems; empty means valid. |

---

### R — Error Logging Improvement

**Packet: ErrorRecord**

One record per error, written into the run log.

```text
ErrorRecord {
  t_error:         int          # ns
  package:         str          work package letter, e.g. "A"
  code:            str          upper case, e.g. "SOURCE_LOST"
  message:         str
  frame_id:        int | null
  schema_version:  str          "0.1"
}
```

| Data | Expected format | Description and meaning |
|---|---|---|
| `t_error` | Integer, nanoseconds, monotonic clock | When the error happened. |
| `package` | String, work package letter | Which part of the system failed, so the fault is located immediately. |
| `code` | String, upper case with underscores | Fixed name for the type of error, so errors can be counted and searched. |
| `message` | String | Human-readable explanation. |
| `frame_id` | Integer, or empty | The frame being processed when the error happened, if any. |
| `schema_version` | String | Version of this packet format. |

**Function signatures**

```text
report_error(package: str, code: str, message: str, frame_id: int | None = None)  -> None
```

| Function | Description and meaning |
|---|---|
| `report_error()` | Records an error in a single standard form, so every package reports problems the same way. |

---
