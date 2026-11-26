# 第 2 階段 — 各工作包審查報告(給 helper)

第 2 階段審查報告。**本文件是第 2 階段審查的凍結紀錄,此版本之後不再更新。** 系統現在怎麼運作,見 [`../architecture.md`](../architecture.md) 與 [`../handoff.zh.md`](../handoff.zh.md)。英文版:[`stage2_review_for_helpers.md`](stage2_review_for_helpers.md)。

**狀態:第 2 階段尚未完成。** 工作包 A、B、D、E、F 的程式與測試在替代影片上通過;工作包 C 尚未開始;真實 fixture(三支影片與模型檔)還沒提交,所以沒有任何工作包用真實素材驗收過。

**這份報告的用途。** 每一節講一個工作包:交付了什麼、逐條對照 issue 的完成標準、做得好的地方、缺的地方、**整合時我在你的檔案裡改了什麼、為什麼改**、還剩什麼。請讀自己的那一節,再讀第 6 節(共通問題)與第 12 節(每次 PR 前的檢查清單)。本報告檢討的是工作與流程,不是人。

---

## 1. 第 2 階段總覽

| WP | 負責人 | Issue | 整合前 | 現況 | 剩下 |
|---|---|---|---|---|---|
| A 影像輸入 | dougleungch | [#3](https://github.com/XRainimatorX/HADES/issues/3) | 程式與 issue 不符;沒有測試 | 符合 issue;25 個測試(無相機時跳過 1 個) | 實機相機檢查、真實影片驗收 |
| B 偵測 | dougleungch | [#4](https://github.com/XRainimatorX/HADES/issues/4) | 程式符合 issue;沒有測試 | 48 個測試,覆蓋率 99 % | 準確度(第 3 階段)、真實影片驗收 |
| C 資料集 | Greencslethan | [#5](https://github.com/XRainimatorX/HADES/issues/5) | **未開始** | 未開始 | 全部 |
| D 螢幕與監看 | Greencslethan | [#6](https://github.com/XRainimatorX/HADES/issues/6) | 能運作;多出檔案與視窗程式;測試跑不起來 | 符合 issue;23 + 14 個測試 | 真實影片驗收、Flask 問題 |
| E 執行紀錄與重播 | Greencslethan | [#7](https://github.com/XRainimatorX/HADES/issues/7) | 設計良好;測試跑不起來 | 符合 issue;45 個測試 | 真實影片驗收 |
| F 測試框架與 benchmark | 項目所有人 | [#8](https://github.com/XRainimatorX/HADES/issues/8) | 未開始 | 完成;覆蓋率 100 % | 真實影片驗收 |

## 2. 這次審查怎麼做的

```text
來源        helper 分支 doug 與 Greencslethan(原樣,11/15 至 11/22 推送),以及合併後的 review_branch
CI 紀錄     helper 推送 4 次,4 次都死在第一道檢查(black --check);pylint、mypy、bandit、pytest
            都被跳過,所以沒有任何 helper 測試在 CI 跑過
整體檢查    Python 3.11 上跑 black --check、pylint、mypy、bandit、pytest(含覆蓋率);
            整合後五項全過(pytest:305 通過、1 個跳過(沒有相機)、1 個預期失敗,覆蓋率 94 %)
測試有效性  每個修過或新增的測試都故意弄壞程式確認它會失敗(docs/test-plan.md 第 6 節);
            弄壞後沒失敗的測試,換成更好的測試
素材        三支影片與模型檔未提交。全部用官方 YOLOv8n 權重與放在 git 之外的合成替代影片驗證。
            依賴真實素材的結果,一律標「換真實影片後重跑」。
```

**本報告任何一處都不是偵測準確度、距離或誤報率的量測。** 這些數字都還不存在。

---

## 3. WP A — 影像輸入(dougleungch,Issue #3)

### 交付了什麼

`src/hades/sources.py`:`VideoFileSource(video_path)`、`WebcamSource(camera_index)`、`VirtualPiCamSource(video_path)`;沒有測試;11/15 的提交。

### 對照 issue 的完成標準

| # | 標準 | 整合前 | 現在 |
|---|---|---|---|
| 1 | `frame_id` 從 0 開始,每送出一幀加 1 | 正確,未測試 | 正確;`test_frame_id_starts_at_zero_and_rises_by_one` |
| 2 | `timestamp` 取自 `time.monotonic_ns()`,取得影像後立即記錄 | 正確(讀取後取值) | 正確;與時鐘對照檢查 |
| 3 | 每張影像為 高 × 寬 × 3、uint8、BGR | 檔案來源正確;未縮放 | 正確;虛擬相機縮放到要求的尺寸 |
| 4 | Webcam 回報 `"webcam"` 且只回傳最新幀 | 類型正確;**沒有相機執行緒,所以不是只給最新幀**;建構子只有 `camera_index` | 相機執行緒只保留最新幀;`WebcamSource(device, width, height, fps)` |
| 5 | 檔案來源回報 `"video"`;`realtime=True` 依檔案速率放幀並回傳最新幀,`realtime=False` 回傳每一幀 | **沒有 `realtime` 參數** | `VideoFileSource(path, realtime=True)`;讀得慢就跳幀 |
| 6 | 虛擬 Pi 相機:`"picam"`、指定尺寸與速率、只給最新幀、循環、永不結束 | 類型正確;**沒有尺寸、速率、循環、執行緒**;建構子只有 `video_path` | `VirtualPiCamSource(path, width=1280, height=720, fps=30.0)`,上述都有 |
| 7 | 影片結束或讀取失敗時 `read()` 回傳 None | 正確 | 正確 |
| 8 | `open()` 以清楚訊息拋出 `RuntimeError` | 有拋出,但訊息沒有檔名 | 訊息帶檔名 |
| 9 | `close()` 可呼叫兩次並停止相機執行緒 | 冪等(當時沒有執行緒) | 冪等;執行緒會被 join |
| — | `tests/test_sources.py`(Issue A 第 8 節,第 1–10 項) | **缺** | 25 個測試;沒有相機時跳過 webcam 測試 |
| — | 每個公開類別與函式都有 docstring | 多數沒有 | 全部都有 |

### 做得好的地方

封包的組裝本來就是對的:計數器、讀取後取的單調時間戳、唯讀影像、檔案不存在時乾淨的錯誤。結構(每種來源一個類別、共用一個基底)保留。

### 問題

```text
1  建構子與 issue 不符(device、width、height、fps;realtime;width、height、fps)。
   其他工作包與 benchmark 呼叫的是 issue 的簽名,簽名不符就是整合失敗,即使類別自己能運作。
2  沒有相機執行緒:webcam 與虛擬 Pi 相機無法做到「只回傳最新幀」。
3  虛擬 Pi 相機不循環、不縮放、不控速,所以不像它所代表的真實相機。
4  沒有測試;沒有 docstring。
5  註解寫的是疑問而不是原因(「idk how does the simulation work」),還有錯字。註解應該說明為什麼。
6  未使用的 import(dataclasses.replace)與 import 順序錯誤;black 不過。
```

### 整合時改了什麼、為什麼

`src/hades/sources.py` 依 issue 重寫(172 → 334 行);`tests/test_sources.py` 為新增。

```text
建構子        同 Issue A。
相機執行緒    每個即時來源(webcam、虛擬 Pi 相機)一條執行緒,只保留最新幀,open() 啟動、close() join。
檔案控速      realtime=True:依檔案速率放幀;讀得較慢的呼叫端會跳幀而不是排隊。
              frame_id 仍是每送出一幀加 1,所以跳幀不會造成編號斷層。
虛擬 Pi 相機  循環播放檔案、縮放到指定尺寸、依指定速率控速。
close 之後    read() 回傳 None(「輸入已停止」);尚未 open() 就 read() 拋 RuntimeError(呼叫端的錯)。決策 20。
source_id     每個封包帶 source_id "cam0"(契約 0.2)。
```

### 你還要做的

```text
1  在有相機的筆電上跑 webcam 測試(CI 與這裡都會跳過)。
2  真實影片提交後,重跑 tests/test_sources.py。
3  Windows 路徑(webcam 用 cv2.CAP_DSHOW)已寫但未執行過。
4  整合驗收(Issue A 第 11 節第 6、7 項):由項目所有人執行。
```

### 自己檢查

```bash
pytest tests/test_sources.py -q --cov=hades.sources --cov-report=term-missing
black --check src tests && pylint src/hades/sources.py && mypy src/hades/sources.py
```

---

## 4. WP B — 偵測(dougleungch,Issue #4)

### 交付了什麼

`src/hades/detect.py`:`UltralyticsDetector(min_confidence, input_size)`、`load()`、`detect()`;沒有測試;11/22 的提交。

### 對照 issue 的完成標準

| # | 標準 | 整合前 | 現在 |
|---|---|---|---|
| 1 | `load()` 只載入一次並做一次暖機 | 正確 | 正確;`test_load_runs_exactly_one_warm_up_and_loads_the_model_once` |
| 2 | 每幀一個封包,沒找到時為空 tuple | 正確(tuple);`contracts.py` 當時寫 list(見第 7 節) | 正確,且 `contracts.py` 現在寫 tuple |
| 3 | `frame_id` 與 `timestamp` 原樣複製 | 正確 | 正確 |
| 4 | `t_detect` 為最後一步取的 `time.monotonic_ns()` | 正確 | 正確;有檢查 |
| 5 | `inference_ms` 是模型自己的時間(`results[0].speed["inference"]`) | 正確 | 正確;與腳本化的數值對照 |
| 6 | 每個框都是原始影像像素座標且在影像內 | 正確(夾限、丟棄空框) | 正確;7 種不可用的框都有測試 |
| 7 | 所有數值都是純 Python 數字 | 正確 | 正確;刻意用 `type() is float`,因為 `np.float64` 是 `float` 的子類別 |
| 8 | `class_name` 來自模型;只保留 `classes.yaml` 裡的類別 | 正確 | 現在來自 `contracts.CLASS_NAMES`(決策 15);有測試與 `classes.yaml` 對照 |
| 9 | 同一幀得到同樣的偵測結果 | 正確 | 正確;同一幀測兩次 |
| — | `tests/test_detect.py`(Issue B 第 8 節,第 1–11 項) | **缺** | 48 個測試 |

### 做得好的地方

這是很用心的工作:建構子拒絕壞值、`load()` 在載入前檢查權重檔、模型類別名稱、schema 版本;`detect()` 拒絕壞影像與多於一筆的結果;模型沒有可用推論時間會報錯而不是悄悄填 0。程式**把 tuple 與 list 的不一致寫在註解裡,而不是默默選一邊**,這是正確的習慣,也因此契約才會被修正(第 7 節)。

### 問題

```text
1  沒有測試(要求 11 個)。
2  pylint:detect() 太長(22 個區域變數、一個 6 部分的條件);import 順序錯。mypy:2 個錯誤
   (YOLO 的 import、多餘的 ignore)。
3  類別名稱在 load() 內從 classes.yaml 讀,等於有兩份類別清單。
```

### 整合時改了什麼、為什麼

`src/hades/detect.py`(173 → 178 行),行為不變;`tests/test_detect.py` 為新增。

```text
結構        detect() 拆成 _is_valid_image()、_clamp_box()、_convert();檢查與錯誤訊息不變。
類別名稱    用 contracts.CLASS_NAMES,不再讀 classes.yaml。
型別        修掉 mypy 錯誤。
測試        真實 YOLOv8n 跑影片,檢查格式、時間與每幀一個封包;
            過濾規則用腳本化的假 YOLO,因為官方模型沒有 drone 類別,什麼也偵測不到。
```

### 你還要做的

```text
1  準確度屬於第 3 階段(訓練)。目前沒有任何東西證明偵測得到無人機。
2  換真實影片與已提交的 test_model.pt 重跑。
3  Hailo 路徑(HEF 模型)之後是同兩個函式的另一個實作。
```

### 自己檢查

```bash
pytest tests/test_detect.py -q --cov=hades.detect --cov-report=term-missing
pylint src/hades/detect.py && mypy src/hades/detect.py
```

---

## 5. WP C — 資料集(Greencslethan,Issue #5)

### 交付了什麼

**沒有。** 沒有任何一個提交動到工作包 C 的檔案。

```text
ml/dataset.py                        三個函式,全部仍是 "raise NotImplementedError"
data/annotation_guideline.md         5 行:佔位文字
data/dataset_v1/                     0 張影像、0 個標註檔
data/dataset_v1/split_manifest.csv   只有標題列,0 筆
tests/test_dataset.py                不存在
```

### 對照 issue 的完成標準

| # | 標準 | 狀態 |
|---|---|---|
| 1 | `extract_frames()` 檔名為 `<clip>_<6 位數>.jpg` 並回傳路徑 | 未做 |
| 2 | `build_split()` 讓每支來源影片只在一個 split 並寫出 manifest | 未做 |
| 3 | 相同 seed 得到相同 split | 未做 |
| 4 | `validate_dataset()` 回報列出的六種問題 | 未做 |
| 5 | 資料集合法時 `validate_dataset()` 回傳空清單 | 未做 |
| — | `classes.yaml` 恰好一個類別 | 完成(repo 本來就有) |
| — | 標註規範涵蓋六種情況且各有範例 | 未做 |
| — | `dataset_v1` 合法、每個 split 都有「有無人機」、沒有影片同時在兩個 split | 未做 |

### 回饋

沒有它,第 3 階段訓練就沒東西可訓練,所以這是最影響時程的工作包。**不需要任何真實影片就能開始:**三個函式處理的是資料夾與 fixture 影片,可以先寫、先測。

```text
建議順序   1  validate_dataset()   純函式,讀資料夾,最容易測
           2  extract_frames()     輸入一支影片,輸出編號的 .jpg
           3  build_split()        整支影片分到同一個 split;有 seed,可重現
           4  標註規範             在任何人標註之前先寫好
           5  標註好的資料         需要素材與標註工具
測試       tests/test_dataset.py:Issue C 第 8 節的九個測試,用 fixture 影片在暫存資料夾裡建資料,
           不要動 data/
```

issue 沒回答、需要項目所有人在第 5 步前回覆的問題:素材從哪裡來、授權是否允許使用;用哪個標註工具(issue 說要能匯出 YOLO 格式,並與項目所有人商定);以及原始影片永遠不提交(決策 2)。

### 你還要做的

全部。如果卡住,請盡早在 issue 裡說;越早知道,修正成本越低。

---

## 6. 共通問題(所有工作包)

```text
1  格式          helper 的 4 次推送都在 black --check 失敗,所以 pylint、mypy、bandit、pytest 從沒跑過。
                 推送前請跑第 12 節的五項檢查。
2  不屬於 repo   poetry.lock(4,589 行;專案用 setuptools 建置、沒有 poetry 設定)、demo_oled.py、
   的檔案        oled.png、.vscode/settings.json。已移除。
3  共用檔案      tests/conftest.py 屬於工作包 F(Issue 0 規則 8:不改別人工作包的檔案)。第二份
                 conftest.py 會衝突。D、E 測試需要的 fixture(packets、states、detection_packet、
                 make_frame)現在在共用那份,格式為真實格式。
4  猜測的格式    sample-packet 的格式是猜的({"type": "DetectionPacket", "data": {...}})。真實格式是
                 run-log 格式:小寫 type("frame"、"detection"、"state"),封包欄位在最上層。
5  跑不起來的    E 的測試用了四個不存在的 fixture(load_contract_packets、expected_event_type、
   測試          frame_packet、packet);D 的測試需要 Pillow 與一份不相符的 conftest。跑不起來的測試
                 什麼也證明不了。
6  被註解掉的    alert.py 約 160 行、telemetry.py 約 65 行、monitor.py 約 30 行,另有重複的模組
   程式碼        docstring。版本控制會保留舊程式,請刪掉。
7  sys.path 修改 alert.py、monitor.py、telemetry.py 為了找套件而改 sys.path。套件已用 pip install -e
                 安裝,不需要這樣做,而且會掩蓋 import 錯誤。
8  依賴          用了 Pillow 但沒宣告為依賴。要嘛宣告,要嘛用已宣告的(OpenCV 已宣告)。
9  永遠通過的    測試只有在程式錯誤時會失敗才有用。請故意弄壞程式一次(docs/test-plan.md 第 6 節)。
   測試
```

## 7. 契約 0.2 — 改了什麼、對你的工作包的影響

封包格式一次從 0.1 升到 0.2(決策 13)。內容在 `docs/spec.md` 與 `src/hades/contracts.py`。

| 變更 | 影響 |
|---|---|
| `FramePacket.source_id`,固定 `"cam0"`(有預設值,既有呼叫仍可用) | A(每個封包)、E(frame 記錄)、D(無)、組裝 frame 的測試 |
| 多項目欄位為 tuple;沒有結果是空 tuple,不是 list | B(`detections`)、I(`targets`)、E(把 tuple 寫成 JSON 陣列)、測試 |
| frame 的影像唯讀、不參與封包比較 | A、D(在複本上畫)、B(對複本運算) |
| 設定裡的 `source.width`、`source.height`、`source.fps` | A(建構子參數)、主程式 |
| `ErrorRecord.package` 可為任何大寫字串 | R |
| `contracts.CLASS_NAMES` 是唯一的類別名稱清單 | B、C(`classes.yaml` 要與它核對)、H |
| Schema 版本 `"0.2"`:取自 `contracts.SCHEMA_VERSION`,程式裡不要寫死 | E(原本自己有 `"0.1"`)、所有測試 |

## 8. WP D — 螢幕與監看(Greencslethan,Issue #6)

### 交付了什麼

`alert.py` 的 `VirtualOledDisplay` 與 `format_lines()`;`monitor.py` 的 `WebMonitor`;三個測試檔;11/15 與 11/20 兩個提交。

### 對照 issue 的完成標準

| # | 標準 | 整合前 | 現在 |
|---|---|---|---|
| A1 | 最多八行、每行最多 21 字元 | 正確 | 正確;過長的 frame 編號也測過 |
| A2 | 狀態照封包原樣顯示 | 正確 | 正確,每個狀態都測 |
| A3 | 幀率顯示到小數一位 | 正確 | 正確(24.84 → 24.8,24.86 → 24.9) |
| A4 | 不 import 硬體函式庫 | 預設路徑乾淨,**但**同檔有選用的 Tk 視窗與 Pillow,並把 `oled.png` 寫到工作資料夾 | 乾淨;在原始碼與執行時都測過(沒有載入硬體、`tkinter`、`PIL`) |
| B1 | 伺服器在一條背景執行緒執行 | 正確(標準 `HTTPServer`) | 正確;請求不會增加執行緒 |
| B2 | `publish()` 只存同類型最新的一筆並立即返回 | 正確 | 正確;未知類型忽略 |
| B3 | 只對 `frame_id` 相同的偵測畫框 | 正確 | 正確 |
| B4 | 不修改 frame 的影像 | 正確(先複製) | 正確;影像也是唯讀 |
| B5 | `/status.json` 反映最新狀態與偵測 | 正確 | 正確;幀率有測 |
| — | `tests/test_alert.py`、`tests/test_monitor.py` 使用共用 fixture | 有,但依賴猜的 conftest 與 Pillow | 23 與 14 個測試,用共用 fixture |

### 做得好的地方

監看服務的設計是對的:一條伺服器執行緒、鎖後面存每種訊息的最新一筆、圖片在 frame 或偵測改變前快取、畫之前先複製 frame。這正是 issue 要的。

### 問題

```text
1  虛擬 OLED 會開 Tk 視窗並把 oled.png 寫進工作資料夾。issue 說螢幕在終端機顯示;Issue 0 說只有程式
   入口與 Telemetry 可以寫檔、只有主迴圈可以顯示視窗。
2  監看服務綁在 0.0.0.0,等於對整個網路開放。Bandit 標示(B104)。開發用網頁除非要求,應只綁本機。
3  用 Pillow 畫圖與編碼 JPEG,但它不是宣告的依賴;issue 列的是 OpenCV。
4  約 160 行舊程式被註解掉、重複的模組 docstring、sys.path 修改。
5  部分測試屬於別的工作包(測 LFS 指標檢查,其實是測 conftest,屬於工作包 F)。
```

### 整合時改了什麼、為什麼

```text
alert.py     284 → 91 行。移除 Tk 視窗、Pillow、oled.png、註解與 sys.path 修改;format_lines() 與
             VirtualOledDisplay 保持原樣。新增最小的 MockAlert(J),讓第 2 階段主程式能顯示
             「看到目標,LED 亮」(決策 17)。
monitor.py   230 → 213 行。繪圖與 JPEG 編碼改用 OpenCV;host 為建構子參數,預設 127.0.0.1;
             加型別;移除註解。邏輯是你的。
測試         改用共用 fixture、真實封包格式、不用 Pillow 重寫;新增「不寫檔、不開視窗」、
             只綁本機、幀率、503 與 404 回應、圖片快取的測試。
```

### 你還要做的

```text
1  給項目所有人的問題:Issue D 列的是 Flask。標準函式庫的伺服器滿足「一條執行緒」規則且不需要依賴。
   除非項目所有人要 Flask,否則維持現狀。
2  換真實影片重跑。整合驗收時由項目所有人觀看網頁與螢幕(Issue D 第 11 節第 6、7 項)。
3  狀態顏色與標籤屬於工作包 L(第 4 階段);state_style() 仍是骨架。
```

### 自己檢查

```bash
pytest tests/test_alert.py tests/test_monitor.py -q --cov=hades.alert --cov=hades.monitor
pylint src/hades/alert.py src/hades/monitor.py && mypy src/hades/alert.py src/hades/monitor.py
```

---

## 9. WP E — 執行紀錄與重播(Greencslethan,Issue #7)

### 交付了什麼

`telemetry.py` 的 `Telemetry`、`ReplaySource`、`file_sha256()`、`git_info()`;一個測試檔;11/20 的提交。

### 對照 issue 的完成標準

| # | 標準 | 整合前 | 現在 |
|---|---|---|---|
| 1 | `start_run()` 建立 run 資料夾與 `meta.json` | 正確 | 正確;每個欄位都比對 |
| 2 | `record()` 只排隊並返回 | 正確 | 正確;用每行要 50 ms 的寫入器測過 |
| 3 | 寫入器每個封包寫一行 JSON:正確 type、所有欄位、純 JSON | 正確 | 正確;壞封包會被跳過,執行繼續 |
| 4 | frame 記錄有 `height` 與 `width`,沒有影像 | 正確 | 正確;證明沒有用 `dataclasses.asdict` |
| 5 | `end_run()` 寫完佇列內所有東西;程式在 Ctrl+C 時呼叫它 | `end_run()` 正確;Ctrl+C 時沒人呼叫 | 主程式在 `finally` 關閉紀錄;有測試 |
| 6 | `file_sha256()` 分塊讀取 | 正確 | 正確;2.5 MB 檔案,以及 "abc" 的已知雜湊 |
| 7 | 沒有 git 時 `git_info()` 回傳 `("unknown", False)` | 正確 | 正確;git 失敗與卡住也測;dirty 旗標兩個方向都測 |
| 8 | `ReplaySource` 把原影片當即時來源播放 | 預設盡快播完 | 預設即時(`realtime=True`);測試傳 `realtime=False` 求快 |
| 9 | `ReplaySource` 遇到非影片的 run 拋 `RuntimeError` | 正確 | 正確,訊息指出問題 |
| — | `tests/test_telemetry.py` 使用共用 fixture | 用了四個不存在的 fixture | 45 個可執行的測試 |

### 做得好的地方

這是三個裡設計最強的:一條寫入執行緒由佇列餵;結束標記是在與 `record()` 同一把鎖下放進佇列,所以**任何已接受的紀錄都不可能排在它後面**;刻意不用 `dataclasses.asdict` 並用註解說明原因(它會複製每張影像);寫入錯誤會保留並由 `end_run()` 回報,而不是遺失。

### 問題

```text
1  測試跑不起來(第 6 節第 5 點),所以沒有任何東西證明這個設計行得通。
2  模組自己有 SCHEMA_VERSION = "0.1",而不是用契約的。
3  約 65 行舊程式被註解掉、sys.path 修改、12 個 mypy 錯誤、pylint 問題。
4  ReplaySource 在 close() 之後 read() 會重新開影片,所以停掉的重播會悄悄重新開始。
```

### 整合時改了什麼、為什麼

```text
telemetry.py   494 → 425 行。設計不變;schema 版本取自 contracts;ReplaySource 預設即時,
               close() 之後保持停止;git 透過一個固定參數清單的小函式呼叫(Issue 0 規則 27),
               並標註 bandit 說明;加型別;移除註解與 sys.path 修改。
測試           重寫:45 個測試涵蓋 Issue E 第 8 節的全部十一項,加上錯誤路徑(磁碟錯誤、壞封包、
               第二次 run、重複使用資料夾、壞掉的 meta.json)。
```

### 你還要做的

```text
1  寫入執行緒不是 daemon:程式忘了呼叫 end_run() 就無法結束行程。這是刻意的(不丟紀錄);
   主程式一定會關閉紀錄。
2  summarise()、export_session()、report_error()、replay_main() 屬於 N、R、M,仍是骨架。
3  ReplaySource 與 VideoFileSource 有重疊;合併延到第 4 階段(決策 19)。
4  換真實影片重跑。
```

### 自己檢查

```bash
pytest tests/test_telemetry.py -q --cov=hades.telemetry --cov-report=term-missing
pylint src/hades/telemetry.py && mypy src/hades/telemetry.py && bandit -q src/hades/telemetry.py
```

---

## 10. WP F — 測試框架與 benchmark(項目所有人,Issue #8)

交付:`bench/benchmark.py`(`run_benchmark()`:延遲、幀率、記憶體;`write_report()`)、`tests/conftest.py`、`tests/test_benchmark.py`(43 個測試)、`.github/workflows/tests.yml`、`pyproject.toml` 設定。

```text
標準     Issue F 第 7B 節的七項全部達成並有測試;benchmark.py 覆蓋率 100 %。
發現     write_report(report, "bench/reports") 在資料夾尚不存在時會寫出一個叫 "reports" 的檔案;
         已修正並有測試。
驗收     Issue F 第 11 節第 6、7 項,用真實的 A 與 B 在替代影片上跑過,並打開三份報告檢查
         (median <= p95 <= max、fps_min <= fps_avg、模型雜湊等於檔案的、硬體有寫名稱)。
         它們沒有提交:不是真實數字(docs/test-plan.md 第 9 節)。
剩下     在真實影片與目標硬體上跑。
尚未     tests.yml 從沒在 GitHub 上跑過:它只在 PR 與推到 main 時執行。
```

## 11. 第 2 階段的流程檢討

本節檢討流程,不點名任何人。

**做對的。** 每個 issue 都有編號的最終完成標準,讓這次審查變得機械化:上面每一項都是 issue 的一行。Issue 0 凍結的介面,讓格式一致後各工作包就能接起來。helper 的程式邏輯大致健全;問題出在周邊(測試、格式、介面),不在邏輯。

**出了什麼問題、為什麼。**

```text
1  Issue 0 承諾 fixture 與契約會在開工前提交。三支影片與模型沒提交,而已提交的契約又與 issue 寫的不符
   (list 而不是 tuple、沒有 source_id、沒有 source.width)。helper 只能猜,而猜的東西
   (sample-packet 格式、conftest)彼此不一致。
2  風格檢查只在 CI 跑。4 次推送都死在第一道檢查,後面能顯示真正問題的檢查從沒跑到。
3  issue 用的名稱(VideoFileSource、UltralyticsDetector、VirtualOledDisplay)與 repo 骨架的名稱
   (VideoSource、ModelDetector)不同。讀骨架的 helper 與讀 issue 的 helper 做出不同的介面。
4  沒有人負責組裝後的程式,所以整合之前沒有真正的端到端執行:每個工作包通過自己的檢查,整體卻沒被證明。
```

**第 3 階段要改的。**

```text
1  開第 3 階段 issue 之前,先提交 fixture 與契約。
2  每個 PR 都從第 12 節的清單開始;CI 是確認,不是第一次跑檢查。
3  寫 issue 時,讓骨架名稱與 issue 一致。
4  tests/integration/test_pipeline_smoke.py 從現在起存在:弄壞整條鏈的修改會讓它失敗。
```

## 12. 每次 PR 前的檢查清單

```bash
git fetch origin && git rebase origin/main            # 從最新的 main 開始
black --check src ml bench tests                      # 格式
pylint src ml bench                                   # 風格與明顯錯誤
mypy src ml bench                                     # 型別
bandit -q -r src ml bench                             # 不安全寫法
pytest --cov --cov-report=term-missing                # 測試與覆蓋率
cd /tmp && pytest "<repository>/tests"                # 從別的資料夾執行也要過
grep -rn --include='*.py' "open(" tests/ | grep -E "runs/|bench/reports"   # 沒有測試讀輸出資料夾
```

```text
□ 只改你的 issue 列出的檔案;不改別人的檔案,不改 docs/spec.md、contracts.py
□ 沒有被註解掉的程式、沒有 sys.path 修改、沒有沒用到的檔案
□ 每個公開類別與函式都有 docstring
□ 你 import 的每個依賴都已在 pyproject.toml 宣告
□ 你故意弄壞程式一次,有測試失敗
□ issue 第 11 節的每一項都在 PR 裡勾選,並寫明怎麼檢查的
```

## 13. 已知限制與未驗證項目

```text
未驗證    真實影片(三支):所有結果都來自替代影片
          實機上的 webcam;Windows 相機路徑
          GitHub Actions:tests.yml 沒在 GitHub 上跑過
          目標硬體(Raspberry Pi 5 加 AI HAT+)與 Hailo 模型路徑
          偵測準確度、距離、誤報率:沒量過(docs/test-plan.md)
未提交    tests/fixtures/test_model.pt 與三支影片:由項目所有人提交(決策 22)。
          在那之前,需要它們的測試會失敗並說明原因。
未決      WP C 未開始。D 用 Flask 還是標準函式庫伺服器。第一批門檻與「G. Demo Success Criteria」。
```

## 14. 一句話總結

> 第 2 階段做出了能運作且有測試的 A、B、D、E、F,以及一個跑完整條鏈並記錄每一幀的主程式——但測試是在替代影片上通過,fixture 尚未提交,資料集(C)還沒開始,也沒有量過任何偵測準確度,所以要等真實影片到位且 C 完成,第 2 階段才算完成。
