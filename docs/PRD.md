# HADES Product Requirements Document (PRD)
## External version — v1.1

Revision v1.1 (Stage 2 integration). Changes from v1.0: v0.1 senses with vision only; the compute hardware is decided; the line-level encoding of the interface is listed as a v0.2 item; the long-term threat scope, the standard interface (section 6) and the physical and cost constraints (section 7), which the shortened external version had left out, are restored from the Chinese PRD; the packet summary in section 10 now matches `docs/spec.md`. Where this document and the Chinese PRD differ, the Chinese PRD is the reference.

---


## 1. What is HADES?

HADES is a portable detection and decision core. It uses sensors and AI to identify low-altitude drone threats and automatically outputs a standardised signal through a common interface. HADES is not tied to a single carrier; it can be integrated into wearable, fixed-post or other platforms.

It answers two questions: is a drone approaching nearby, and how much time remains to respond?

**Public one-liner:** HADES helps security teams, campuses, event organisers and infrastructure operators detect low-altitude drone risk earlier through wearable AI sensing and real-time alerts.

## 2. What HADES Is Not

| Not | Explanation |
|---|---|
| A payload | The core ends at the common interface and does not include any payload. |
| A long-range primary detection system | HADES is a close-range, last-layer awareness component, not a wide-area surveillance system. It does not need to beat wide-area systems on coverage or detection range. |
| A weapon or effector | The core outputs standardised signals only. It takes no physical action. |
| A decision-maker for response | Responses are carried out by connected systems and people. |

Industry practice treats vision as a confirmation layer, not a detector. HADES takes a different position, and that is an unverified risk assumption (see the market requirements document, section 9).

## 3. Core Responsibility Boundary

```
Core
  Sensing (vision only in v0.1)
  → AI detection
  → Trigger condition
  → Standardised signal output
  → Common interface (physical, electrical and protocol standardised; use-agnostic)
```

## 4. v0.1 Scope

- **Detection goal:** determine whether an object is a consumer-class drone.
- **Trigger logic:** single-level. Detecting a consumer-class drone triggers output; the alert level is 0 or 1. No threat grading in v0.1.
- **Sensing:** vision only. Audio and infrared sensing are not part of v0.1.
- **Common interface:** a consumer-grade physical connector (USB-C) following USB 3.x-compatible signalling. The line-level encoding of the standardised signal is a v0.2 item.
- **Compute hardware:** Raspberry Pi 5 (4 GB) with the AI HAT+ (26 TOPS, Hailo-8). The final camera and lens are chosen after Stage 3 testing.
- **Physical constraint:** total system weight under 2 kg; retail cost target £2,000 at standard production (see section 7).

## 5. Threat Scope

### v0.1 (now)

Only "is this a drone" is decided; there is no threat grading. The target is the ordinary consumer-class drone, for which data is easy to obtain and results are easy to quantify. Detecting a drone triggers the output.

### Long term (the full threat classification, from v0.2)

"Aggressive" is judged from several factors together, not from a single condition. The known directions are the following, and they are not limited to them:

- flight behaviour (a straight approach, a diving trajectory);
- distance and closing speed;
- the look of a specific type (FPV or loitering-munition appearance);
- entry into a defined alert zone.

The other criteria will be added as data and experience accumulate. The long-term targets also include fibre-optic-guided and RF-silent drones.

### Grading and the uncertain case (long term; neither applies in v0.1)

- **Grading:** pure reconnaissance or hovering without clearly aggressive behaviour gives a lower alert level; a threat that escalates gives a higher-intensity trigger. This is not "trigger or not" but different intensities.
- **Uncertain case:** when the AI confidence is in the middle and it cannot be settled whether the object is a threat, **lean towards triggering**. HADES is the last layer, so it saves lives first: a false alarm is better than a miss. This only makes sense once grading exists, because v0.1 does not judge threat.

### Also not in v0.1

Multi-sensor fusion and additional target classes.

## 6. Standard Interface

### Long-term direction (aligned with the NATO dismounted-soldier ecosystem)

- **Data and control:** the protocol family moves towards USB 3.x, HDMI and LVDS class interfaces (the nearest existing category is head-mounted electro-optical and AR devices).
- **Power:** moves towards the STANAG 4695 class.
- **Final compatibility:** the STANAG 4677 (JDSSIN) NATO dismounted-soldier interoperability framework, rather than a closed protocol of its own.

### The existing standard that was found

The Nett Warrior connector, certified to NATO STANAG 4695:

| | |
|---|---|
| Contacts | 7-pin version (USB-C power integrated, backward compatible with 6-pin) |
| Power | standard 5 A contact (an 8–10 A high-power version is optional) |
| Form | micro circular connector, push-pull quick-release coupling; breakaway force 13 ± 3 lbf, so a snagged cable disconnects by itself and protects the wearer |
| Shell | aluminium alloy shell with thermoplastic insulator, to MIL-STD-810G |
| Suppliers | made in volume by several manufacturers (Glenair, TE Connectivity, ITT Cannon, among others); not tied to one supplier |

### The realistic choice for v0.1 (practical, not military grade)

Use a consumer-grade but logically compatible equivalent (for example a USB-C physical connector) that follows the USB 3.x signalling family. A genuine military connector (such as MIL-DTL-38999 or the Nett Warrior connector) is not realistic at £2,000 and 2 kg, because of its cost and certification requirements. The unit cost is not in the existing material and needs to be quoted later.

### Known conflict between the long term and now

The cost of a military connector could consume the whole v0.1 bill of materials. **This conflict can only be settled in the £150k–£300k engineering validation stage; it is not a v0.1 problem.**

### Still open

Even though a long-term standard to follow exists, the v0.1 parameters are open until the real hardware is chosen: which consumer-grade equivalent connector, the exact supply voltage and current, and the latching and housing form. Once decided they belong to the specification (document 3), not to this document. The line-level encoding of the standardised signal is a **v0.2** item.

## 7. Physical and Cost Constraints

| | |
|---|---|
| Weight | under 2 kg |
| Cost | £2,000 (retail, standard production) |

**Why:** the soldier already carries weapons, ammunition, water and communications. The device must be cheap enough that losing it does not hurt, and light enough not to affect mobility. This is the adoption logic proven in the Ukrainian market.

**Principle:** these are the v0.1 figures, but the interface standard itself must leave room for future specification changes. The numbers change with the version; the principle does not.

## 8. Core Concepts

| Term | Definition |
|---|---|
| Sensing input | Raw frames from the camera or other sensors |
| Detection | Model output: bounding box, class and confidence |
| Track | A detection stabilised across multiple frames |
| Trigger | A condition whose fulfilment produces a standardised signal |
| Standardised signal | Fixed-format output sent to the common interface |
| Common interface | The physical, electrical and protocol layer connecting external devices |
| Event log | A time-ordered record of a run |

## 9. Basic Run Flow

1. Load configuration
2. Acquire sensing input
3. Run detection
4. Track and filter across frames
5. Evaluate trigger condition
6. Emit standardised signal
7. Update system state
8. Record event log
9. Export run summary

## 10. Interface Specifications (Summary)

Field-level definitions are maintained in [`docs/spec.md`](spec.md). This PRD lists the packet names and their key fields only; if they differ, `docs/spec.md` is correct.

- **FramePacket:** `frame_id`, `timestamp`, `image`, `source_type`, `source_id`
- **DetectionPacket:** `frame_id`, `detections[]`, `inference_ms`, `timestamp`, `t_detect`
- **TrackingPacket:** `target_id`, `class_name`, `confidence_smoothed`, `bbox`, `is_confirmed`
- **ActuatorCommand:** `alert_level` (0 or 1), `led_mode`, `buzzer_mode`, `laser_on`
- **SystemState:** `IDLE`, `SCANNING`, `CANDIDATE`, `CONFIRMED`, `ALERTING`, `COOLDOWN`

## 11. Result Package

Each run produces a result package containing:

- `run_id`
- `status` (completed / failed / stopped)
- `summary`
- `metrics`: end-to-end latency, effective detection range, false-positive rate
- `event_log_path`

## 12. Open Items

- Camera and lens selection (after Stage 3 testing)
- Audio and infrared sensing (after v0.1)
- The connector, power specification and latching form of the common interface
- The line-level encoding of the standardised signal (v0.2)
- The unit cost of the interface connector (to be quoted)

## 13. Final Definition

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
| 遠距主要偵測系統 | HADES 是近距離、最後一層的感知元件，不是廣域監控系統；不需要在覆蓋範圍與偵測距離上贏過大型裝置。 |
| 武器或作用器 | 核心只輸出標準化訊號，不執行任何實體動作。 |
| 反應決策者 | 反應行動由連接的系統與人員執行。 |

業界把視覺偵測當作確認層，而不是偵測層。HADES 的定位不同，但這是一條未驗證的風險假設（見市場需求文件第 9 節）。

## 3. 核心職責邊界

```
核心
  感測（v0.1 只用視覺）
  → AI 偵測
  → 觸發條件
  → 標準化訊號輸出
  → 通用接口（實體、電氣與通訊協議標準化；不預設用途）
```

## 4. v0.1 範圍

- **偵測目標：** 判斷物件是否為一般消費級無人機。
- **觸發邏輯：** 單一層級。偵測到消費級無人機即觸發輸出；警示等級只有 0 或 1。v0.1 不做威脅分級。
- **感測：** 只用視覺。聲音與紅外線感測不在 v0.1 範圍內。
- **通用接口：** 消費級實體接頭（USB-C），遵循 USB 3.x 相容的訊號協議。標準化訊號的線上編碼列為 v0.2 待辦。
- **運算硬體：** Raspberry Pi 5（4 GB）加 AI HAT+（26 TOPS，Hailo-8）。相機與鏡頭的最終選型待第 3 階段實測後決定。
- **物理限制：** 系統總重量低於 2 公斤；零售成本目標 £2,000（標準量產，見第 7 節）。

## 5. 威脅範疇

### v0.1（現在）

只做「是否為無人機」的識別，不做威脅分級。目標對象是一般消費級無人機（資料好拿、容易量化驗證）。偵測到無人機即觸發輸出。

### 長期（完整版威脅分類，v0.2 之後才實作）

判定「攻擊性」依據多項因素並用，不是單一條件。已知的判準方向包括，但不限於此：

- 飛行行為（直線接近、俯衝軌跡）；
- 距離與接近速度；
- 特定機型特徵（FPV、游蕩彈藥外觀）；
- 是否進入警戒範圍。

其餘判準待補，隨資料與經驗累積擴充。長期目標對象也擴及光纖導引與 RF 靜默無人機。

### 分級與不確定情況（長期；v0.1 都不適用）

- **分級：** 純偵察、盤旋但無明顯攻擊行為，給較低強度的警示等級；威脅升級才用高強度觸發。不是「觸發或不觸發」，而是用不同強度區分。
- **不確定情況：** AI 信心值處於中間、無法確定是否為威脅時，**傾向觸發**。HADES 是最後一層，優先救命：寧可誤報也不要漏判。這條要有分級之後才有意義，因為 v0.1 還不做威脅判斷。

### 也不在 v0.1

多感測器融合、擴充目標類別。

## 6. 標準接口規格

### 長期方向（對齊北約單兵系統生態系）

- **資料與控制：** 協議族群朝 USB 3.x、HDMI、LVDS 等級看齊（對應頭戴式光電與 AR 裝置這個最接近的現行分類）。
- **電源：** 朝 STANAG 4695 等級看齊。
- **最終相容：** STANAG 4677（JDSSIN）這個北約單兵互通框架，而不是自成一套封閉協議。

### 已查到的現行標準

Nett Warrior 連接器，NATO STANAG 4695 認證：

| | |
|---|---|
| 接點數量 | 7-pin 版本（含 USB-C 電力整合，向下相容 6-pin） |
| 供電 | 標準 5 A 接點（可選配 8–10 A 高功率版本） |
| 物理形式 | 微型圓形連接器，push-pull 快拆式耦合；斷離力 13 ± 3 磅力，纜線被勾到會自動斷開，保護配戴者安全 |
| 外殼 | 鋁合金外殼加熱塑性絕緣體，符合 MIL-STD-810G |
| 供應來源 | Glenair、TE Connectivity、ITT Cannon 等多家廠商已量產，非單一供應商綁定 |

### v0.1 現實選擇（務實版，非軍規）

用消費級但邏輯相容的等效方案（例如 USB-C 實體接頭），但遵循 USB 3.x 訊號協議族群。真正的軍規連接器（如 MIL-DTL-38999，或上述 Nett Warrior 連接器）的成本與認證要求，在 £2,000 與 2 公斤的 v0.1 階段不現實。單價成本現有材料沒有數據，需要之後詢價確認。

### 已知的長期與現在的衝突

軍規連接器成本可能直接吃掉整個 v0.1 的 BOM 預算。**這個衝突要等到 £150k–£300k 的 engineering validation 階段才能真正解決，不是 v0.1 該解決的問題。**

### 仍未定案

即使長期方向已有具體標準可依循，v0.1 的具體參數仍待定，要等實際硬體選定後才能決定：採用哪種消費級等效接頭、確切的供電電壓與電流、卡榫與外殼形式。確定後的定案屬於文件 3（Spec）的範疇，不在這份文件處理。標準化訊號的線上編碼列為 **v0.2** 待辦。

## 7. 物理與成本約束

| | |
|---|---|
| 重量 | 低於 2 公斤 |
| 成本 | £2,000（零售價，標準量產） |

**理由：** 單兵已負重（武器、彈藥、水、通訊），所以要便宜到損耗不心疼、輕到不影響機動。這是烏克蘭市場實際驗證過的採用邏輯。

**原則：** 這個約束是 v0.1 的具體數字，但接口標準本身要留給未來規格變動的餘地。數字隨版本變動，原則不變。

## 8. 核心概念

| 術語 | 定義 |
|---|---|
| 感測輸入（Sensing input） | 來自相機或其他感測器的原始畫面 |
| 偵測（Detection） | 模型輸出：邊界框、類別與信心值 |
| 追蹤（Track） | 跨多幀穩定後的偵測結果 |
| 觸發（Trigger） | 條件達成後產生標準化訊號的判斷 |
| 標準化訊號（Standardised signal） | 送往通用接口的固定格式輸出 |
| 通用接口（Common interface） | 連接外部裝置的實體、電氣與協議層 |
| 事件紀錄（Event log） | 每次運行的時間序列紀錄 |

## 9. 基本運行流程

1. 載入設定
2. 取得感測輸入
3. 執行偵測
4. 跨幀追蹤與過濾
5. 評估觸發條件
6. 輸出標準化訊號
7. 更新系統狀態
8. 記錄事件紀錄
9. 匯出運行摘要

## 10. 介面規格（摘要）

欄位層級的定義在 [`docs/spec.md`](spec.md)。本 PRD 只列出封包名稱與主要欄位；兩者不同時，以 `docs/spec.md` 為準。

- **FramePacket：** `frame_id`、`timestamp`、`image`、`source_type`、`source_id`
- **DetectionPacket：** `frame_id`、`detections[]`、`inference_ms`、`timestamp`、`t_detect`
- **TrackingPacket：** `target_id`、`class_name`、`confidence_smoothed`、`bbox`、`is_confirmed`
- **ActuatorCommand：** `alert_level`（0 或 1）、`led_mode`、`buzzer_mode`、`laser_on`
- **SystemState：** `IDLE`、`SCANNING`、`CANDIDATE`、`CONFIRMED`、`ALERTING`、`COOLDOWN`

## 11. 結果封包

每次運行產生一份結果封包，內容包括：

- `run_id`
- `status`（completed / failed / stopped）
- `summary`
- `metrics`：端到端延遲、有效偵測距離、誤報率
- `event_log_path`

## 12. 待定事項

- 相機與鏡頭選型（第 3 階段實測後）
- 聲音與紅外線感測（v0.1 之後）
- 通用接口的接頭、供電規格與卡榫形式
- 標準化訊號的線上編碼（v0.2）
- 接口連接器的單價（待詢價）

## 13. 最終定義

HADES 是一套可移植的偵測與決策核心，從感測輸入判斷低空無人機威脅，並透過通用接口輸出標準化訊號。

**一句話：** HADES = 讓感測到的威脅，在人來不及反應之前，自動變成一道標準化訊號的系統。
