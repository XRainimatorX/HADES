# HADES Product Requirements Document (PRD)
## External version
---


## 1. What is HADES?

HADES is a portable detection and decision core. It uses sensors and AI to identify low-altitude drone threats and automatically outputs a standardised signal through a common interface. HADES is not tied to a single carrier; it can be integrated into wearable, fixed-post or other platforms.

It answers two questions: is a drone approaching nearby, and how much time remains to respond?

**Public one-liner:** HADES helps security teams, campuses, event organisers and infrastructure operators detect low-altitude drone risk earlier through wearable AI sensing and real-time alerts.

## 2. What HADES Is Not

| Not | Explanation |
|---|---|
| A payload | The core ends at the common interface and does not include any payload. |
| A long-range primary detection system | HADES is a close-range, last-layer awareness component, not a wide-area surveillance system. |
| A weapon or effector | The core outputs standardised signals only. It takes no physical action. |
| A decision-maker for response | Responses are carried out by connected systems and people. |

## 3. Core Responsibility Boundary

```
Core
  Sensing (vision-first; other modalities under evaluation)
  → AI detection
  → Trigger condition
  → Standardised signal output
  → Common interface (physical, electrical and protocol standardised; use-agnostic)
```

## 4. v0.1 Scope

- **Detection goal:** determine whether an object is a consumer-class drone.
- **Trigger logic:** single-level. Detecting a consumer-class drone triggers output. No threat grading in v0.1.
- **Sensing:** vision is the primary modality. Audio and infrared inputs are under evaluation.
- **Common interface:** consumer-grade connector following USB 3.x-compatible signalling. Exact parameters depend on hardware selection.
- **Compute hardware:** to be confirmed before development begins.
- **Physical constraint:** total system weight under 2 kg.

## 5. Future Scope (Not in v0.1)

- Multi-level threat assessment based on flight behaviour, distance, closing speed, aircraft characteristics and entry into a defined alert zone. Criteria are under study and will be defined in later versions.
- Multi-sensor fusion.
- Expanded target classes.

## 6. Core Concepts

| Term | Definition |
|---|---|
| Sensing input | Raw frames from the camera or other sensors |
| Detection | Model output: bounding box, class and confidence |
| Track | A detection stabilised across multiple frames |
| Trigger | A condition whose fulfilment produces a standardised signal |
| Standardised signal | Fixed-format output sent to the common interface |
| Common interface | The physical, electrical and protocol layer connecting external devices |
| Event log | A time-ordered record of a run |

## 7. Basic Run Flow

1. Load configuration
2. Acquire sensing input
3. Run detection
4. Track and filter across frames
5. Evaluate trigger condition
6. Emit standardised signal
7. Update system state
8. Record event log
9. Export run summary

## 8. Interface Specifications (Summary)

Field-level definitions are maintained in the interface specification documents. This PRD lists the packet names and their key fields only.

- **FramePacket:** `frame_id`, `timestamp`, `image`, `source_type`
- **DetectionPacket:** `frame_id`, `detections[]`, `inference_ms`
- **TrackingPacket:** `target_id`, `class_name`, `confidence_smoothed`, `bbox`, `is_confirmed`
- **ActuatorCommand:** `trigger_state`, `output_mode`
- **SystemState:** `IDLE`, `SCANNING`, `CANDIDATE`, `CONFIRMED`, `ALERTING`, `COOLDOWN`

## 9. Result Package

Each run produces a result package containing:

- `run_id`
- `status` (completed / failed / stopped)
- `summary`
- `metrics`: end-to-end latency, effective detection range, false-positive rate
- `event_log_path`

## 10. Open Items

- Compute hardware selection
- Sensing modality beyond vision
- Exact common interface parameters and power specification

## 11. Final Definition

HADES is a portable detection and decision core that identifies low-altitude drone threats from sensor input and outputs standardised signals through a common interface.

**In one line:** HADES = a system that turns a sensed threat into a standardised signal before a person has time to react.

---

## 1. HADES 是什麼？

HADES 是一套可移植的偵測與決策核心。它使用感測器與 AI 判斷低空無人機威脅，並透過通用接口自動輸出標準化訊號。HADES 不綁定單一載體，可整合於穿戴式、固定哨站或其他平台。

它回答兩個問題：附近是否有無人機正在接近，以及還有多少反應時間。

**對外一句話：** HADES helps security teams, campuses, event organisers and infrastructure operators detect low-altitude drone risk earlier through wearable AI sensing and real-time alerts.
（中文：HADES 透過穿戴式 AI 感測與即時警示，協助安保團隊、校園、活動主辦單位與基礎設施營運者更早察覺低空無人機風險。）

## 2. HADES 不是什麼？

| 不是 | 說明 |
|---|---|
| 酬載（payload） | 核心的範圍止於通用接口，不包含任何酬載。 |
| 遠距主要偵測系統 | HADES 是近距離、最後一層的感知元件，不是廣域監控系統。 |
| 武器或作用器 | 核心只輸出標準化訊號，不執行任何實體動作。 |
| 反應決策者 | 反應行動由連接的系統與人員執行。 |

## 3. 核心職責邊界

```
核心
  感測（以視覺為主；其他感測方式評估中）
  → AI 偵測
  → 觸發條件
  → 標準化訊號輸出
  → 通用接口（實體、電氣與通訊協議標準化；不預設用途）
```

## 4. v0.1 範圍

- **偵測目標：** 判斷物件是否為一般消費級無人機。
- **觸發邏輯：** 單一層級。偵測到消費級無人機即觸發輸出。v0.1 不做威脅分級。
- **感測：** 以視覺為主。聲音與紅外線輸入評估中。
- **通用接口：** 消費級連接器，遵循 USB 3.x 相容的訊號協議。確切參數依硬體選型而定。
- **運算硬體：** 開發開始前確認。
- **物理限制：** 系統總重量低於 2 公斤。

## 5. 未來範圍（不在 v0.1）

- 多層級威脅評估，依據飛行行為、距離、接近速度、機型特徵與是否進入指定警戒範圍。判準評估中，將於後續版本定義。
- 多感測器融合。
- 擴充目標類別。

## 6. 核心概念

| 術語 | 定義 |
|---|---|
| 感測輸入（Sensing input） | 來自相機或其他感測器的原始畫面 |
| 偵測（Detection） | 模型輸出：邊界框、類別與信心值 |
| 追蹤（Track） | 跨多幀穩定後的偵測結果 |
| 觸發（Trigger） | 條件達成後產生標準化訊號的判斷 |
| 標準化訊號（Standardised signal） | 送往通用接口的固定格式輸出 |
| 通用接口（Common interface） | 連接外部裝置的實體、電氣與協議層 |
| 事件紀錄（Event log） | 每次運行的時間序列紀錄 |

## 7. 基本運行流程

1. 載入設定
2. 取得感測輸入
3. 執行偵測
4. 跨幀追蹤與過濾
5. 評估觸發條件
6. 輸出標準化訊號
7. 更新系統狀態
8. 記錄事件紀錄
9. 匯出運行摘要

## 8. 介面規格（摘要）

欄位層級的定義由介面規格文件維護。本 PRD 只列出封包名稱與主要欄位。

- **FramePacket：** `frame_id`、`timestamp`、`image`、`source_type`
- **DetectionPacket：** `frame_id`、`detections[]`、`inference_ms`
- **TrackingPacket：** `target_id`、`class_name`、`confidence_smoothed`、`bbox`、`is_confirmed`
- **ActuatorCommand：** `trigger_state`、`output_mode`
- **SystemState：** `IDLE`、`SCANNING`、`CANDIDATE`、`CONFIRMED`、`ALERTING`、`COOLDOWN`

## 9. 結果封包

每次運行產生一份結果封包，內容包括：

- `run_id`
- `status`（completed / failed / stopped）
- `summary`
- `metrics`：端到端延遲、有效偵測距離、誤報率
- `event_log_path`

## 10. 待定事項

- 運算硬體選型
- 視覺以外的感測方式
- 通用接口的確切參數與供電規格

## 11. 最終定義

HADES 是一套可移植的偵測與決策核心，從感測輸入判斷低空無人機威脅，並透過通用接口輸出標準化訊號。

**一句話：** HADES = 讓感測到的威脅，在人來不及反應之前，自動變成一道標準化訊號的系統。
