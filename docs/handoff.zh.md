# HADES 移交文件 — 第 2 階段結束時系統怎麼運作

活文件:鏈路、指令或維護程序改變時更新。英文版:[`handoff.md`](handoff.md)。第 2 階段各工作包的審查見 [`phases/stage2_review_for_helpers.zh.md`](phases/stage2_review_for_helpers.zh.md)(凍結)。

**用途。** 讓第 2 階段沒參與的人能執行、測試、維護系統,並開始第 3 階段。**第 2 階段尚未完成**(見第 9 節):這裡所有東西都是在替代影片上檢查的,沒有用真實影片、沒有在 GitHub Actions、也沒有在目標硬體上驗證。

---

## 1. 現有什麼

```text
可運作    A 影像來源(檔案、筆電相機、虛擬 Pi 相機)
          B YOLO 偵測器(官方 YOLOv8n 權重,所以偵測不到無人機)
          D 終端機虛擬 OLED、網頁監看
          E 執行紀錄(events.jsonl、meta.json)與重播來源
          F benchmark(延遲、幀率、記憶體)與共用測試 fixture
          一個把以上全部串起來、跑一支影片或一個相機的主程式
骨架      追蹤器(I)、決策層(狀態機永遠回 SCANNING、從不發命令)、診斷、demo 重播、
          整合檢查、錯誤紀錄、摘要
尚未      C 資料集、G 訓練、H 誤差分析、Hailo 模型、真實 Pi 相機、真實 OLED、LED 與蜂鳴器驅動
```

## 2. 一幀怎麼走

```text
A source.read()          FramePacket       frame_id、timestamp(單調 ns)、image、source_id
        |
B detector.detect()      DetectionPacket   同樣的 frame_id 與 timestamp、detections(tuple)、
        |                                  inference_ms、t_detect
        |  (還沒有追蹤器:往下傳一個空的 TrackingPacket)
決策骨架                 StateSnapshot     狀態 SCANNING,沒有命令
        |
E telemetry.record()     events.jsonl      每個封包一行:frame、detection、state
D 螢幕、監看             終端機畫面與網頁顯示最新的封包

第 2 階段捷徑            某幀有偵測結果時,主迴圈自己把設定好的警報送給警報 mock(LED 亮);
                         第一個沒有偵測結果的幀把它關掉。第 4 階段會搬進決策層(決策 12、16、17)。
```

**封包格式凍結在 `docs/spec.md` 與 `src/hades/contracts.py`(schema 0.2)。** 多項目欄位是 tuple;frame 影像唯讀;schema 版本一律取自 `contracts.SCHEMA_VERSION`。

## 3. 模組

| 檔案 | 做什麼 | 依賴 | 執行緒 |
|---|---|---|---|
| `contracts.py` | 封包、狀態名稱、介面 | 無 | 無 |
| `config.py` | `load_config()`、`validate_config()`、`resolve_path()` | contracts、PyYAML | 無 |
| `sources.py` | 三種來源 | contracts、OpenCV | 每個即時來源一條相機執行緒 |
| `detect.py` | `UltralyticsDetector` | contracts、ultralytics(extra `detect`) | 無 |
| `decide.py` | 狀態機骨架 | contracts | 無 |
| `alert.py` | `format_lines`、`VirtualOledDisplay`、`MockAlert` | contracts | 無 |
| `monitor.py` | `WebMonitor` | contracts、OpenCV | 一條伺服器執行緒 |
| `telemetry.py` | `Telemetry`、`ReplaySource`、`file_sha256`、`git_info` | contracts、OpenCV | 一條寫入執行緒(不是 daemon) |
| `pipeline.py` | `run_pipeline()`、`main()` | 以上全部 | 主執行緒 |
| `bench/benchmark.py` | `run_benchmark()`、`write_report()` | config、sources、detect | 無 |

**整個程式最多用四條執行緒**(主、相機、監看伺服器、紀錄寫入),符合 Issue 0。時間一律是 `time.monotonic_ns()`,不用牆上時鐘,所以延遲都是同一個時鐘的差。

## 4. 執行

```bash
python3.11 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,detect]"
git lfs pull --include="tests/fixtures/"
cp configs/default.yaml my.yaml     # 然後把 detector.model_path 改成 tests/fixtures/test_model.pt
hades-run --config my.yaml --clip tests/fixtures/drone_daylight_01.mp4 --max-frames 100
hades-run --config my.yaml --monitor-port 8080     # 用設定的來源;網頁在 8080 埠
```

**`configs/default.yaml` 的模型路徑刻意是佔位值(`models/<model_name>/model.pt`):**目前還沒有訓練好的模型。請複製檔案並指到真實權重檔,如上;否則執行會停下並訊息指出缺的檔案。

```text
輸出     runs/<run_id>/meta.json     git commit 與 dirty 旗標、模型與設定的 SHA-256、來源、硬體名稱
         runs/<run_id>/events.jsonl  每個封包一行 JSON
         最後印出的一行會說跑了幾幀、紀錄在哪裡。
停止     Ctrl+C:先關閉紀錄(結束碼 130)
設定     configs/default.yaml;來源類型為 picam | webcam | video;缺少或型別錯誤的設定會在錯誤訊息裡點名
```

`hades-replay` 已宣告為入口,但 `replay_main()` 仍是骨架(工作包 M)。`ReplaySource(run_dir)` 在程式裡已可播放某次 run 的原始影片。

## 5. 測試與量測

```bash
pytest --cov --cov-report=term-missing         # 全部測試;回報覆蓋率,尚未強制
pytest tests/integration -q                     # 在一支影片上跑整條鏈
python -c "from bench.benchmark import run_benchmark, write_report; \
r = run_benchmark('latency', 'my.yaml', 'tests/fixtures/drone_daylight_01.mp4'); \
print(write_report(r, 'bench/reports/'))"        # kind:latency | fps | memory
```

```text
各 kind 回報什麼   latency:t_detect - timestamp 的 median、p95(nearest rank)、max
                   fps:平均與最低
                   memory:開始、結束與峰值的常駐記憶體
每份報告           都寫硬體名稱(設定的 hardware.name)與模型的 SHA-256
怎麼看數字         只能與相同硬體、相同模型、相同影片比(docs/test-plan.md 第 9 節)。
                   來自替代素材或錯誤機器的數字不是量測。
```

**只有真實的報告才提交:**真實影片、正確標明目標硬體、且檔案有被打開讀過。

## 6. 除錯

| 症狀 | 可能原因 | 看哪裡 |
|---|---|---|
| 測試說缺 fixture 或它是 LFS 指標 | 影片或 `test_model.pt` 沒拉下來 | `git lfs pull --include="tests/fixtures/"` |
| `ModuleNotFoundError: ultralytics` | 沒裝 `detect` extra | `pip install -e ".[dev,detect]"` |
| 執行結束後行程沒退出 | 沒呼叫 `Telemetry.end_run()`,寫入執行緒在等 | 呼叫端要在 `finally` 關閉紀錄 |
| `events.jsonl` 少於 3 × 幀數行 | 執行被中斷或寫入錯誤 | 結束訊息;`end_run()` 會回報第一個寫入錯誤 |
| 幀率遠低於來源速率 | 偵測比來源慢;即時來源刻意跳幀 | detection 記錄裡的 `inference_ms`;`fps` benchmark |
| `RuntimeError` 點名某個影片檔 | 設定裡的路徑錯或檔案不可讀 | `source.uri`;相對路徑從 repo 根目錄解析 |
| 別台電腦打不開網頁 | 監看服務只聽 127.0.0.1 | `WebMonitor(host=...)`;請明確知道自己在做什麼 |
| Windows 上 webcam 全黑或找不到 | Windows 需要 DirectShow 後端(程式內已設定,未測) | 相機編號;是否被別的程式占用 |
| 每個偵測清單都是空的 | 官方 YOLOv8n 沒有 drone 類別,屬預期 | 不是故障;訓練好的模型是第 3 階段 |

## 7. 維護

**每日。** [`phases/stage2_review_for_helpers.zh.md`](phases/stage2_review_for_helpers.zh.md) 第 12 節的檢查(black、pylint、mypy、bandit、pytest、從別的資料夾跑)。CI 紅燈要先修,再合併其他東西。

**改封包格式(契約)。** 格式是凍結的;改它是契約變更,不是重構。

```text
1  寫下改什麼、為什麼、誰受影響(審查報告第 7 節的表是範本)。
2  取得項目所有人核准;contracts.py 有 CODEOWNERS。
3  在同一個 PR 裡:docs/spec.md、src/hades/contracts.py、configs/default.yaml、
   data/classes.yaml、tests/fixtures/sample_packets.jsonl、tests/test_contracts.py;
   把 schema 版本到處升版(它取自 contracts.SCHEMA_VERSION)。
4  通知每個工作包負責人;檔案之間有任何不一致,契約測試都會失敗。
```

**換模型。** `detector.model_path` 指定權重;run 紀錄存它的 SHA-256,所以每次 run 都說得出用了哪個模型。新模型檔以 Git LFS 取代 `models/<name>/` 裡的舊檔(永遠不放原始影片,決策 2)。重跑 benchmark,並把舊報告與新報告放在一起。

**改用 Hailo 加速器(第 3 階段之後)。** 偵測器介面只有兩個函式 `load()` 與 `detect()`,測試也只呼叫這兩個。Hailo 偵測器(HEF 模型,把回傳的框轉成 `Detection`)是同樣兩個函式後面的第二個類別;不要改封包。要確認類別名稱符合 `contracts.CLASS_NAMES`、框是原始影像像素座標、`inference_ms` 是加速器的時間。**這些目前都不存在,也沒測過。**

**依賴。** 版本釘死在 `pyproject.toml`。一次升一個並跑完整檢查;這些版本只在 Python 3.11 驗證過。

## 8. 第 3 階段 — 往哪裡接

| WP | 建立在 | 從哪開始 | 做到什麼算完成 |
|---|---|---|---|
| G 訓練 | C 的 `dataset_v1`;`ml/train.py`、`ml/export.py`;benchmark | 一個 `UltralyticsDetector` 載得進去的匯出模型 | 匯出的模型能跑過 `hades-run` 與 `tests/integration`;benchmark 報告是真實的(第 5 節) |
| H 誤差分析 | 有標註影片的 run 紀錄;`ml/analysis.py` | 在有標註的影片上跑出的 `events.jsonl` | 從紀錄逐幀列出誤報與漏報;**需要真實影片與標註** |
| I 追蹤 | `track.py`;`DetectionPacket`;`contracts.TrackingPacket` | 主迴圈現在傳的空 `TrackingPacket` | 主迴圈把追蹤器的輸出傳給決策骨架;追蹤器用腳本化偵測測試;狀態遵守設定裡的確認/遺失幀數 |
| C 資料集 | `ml/dataset.py`;fixtures | 審查報告第 5 節 | Issue C 最終完成標準;**它擋住 G** |

**第 3 階段開始前**,第 10 節的清單應該全部打勾。

## 9. 未驗證的項目

```text
真實影片     三支影片未提交;所有結果都來自替代影片與官方 YOLOv8n 權重
GitHub       tests.yml 從沒在 GitHub 上跑過(它在 PR 與推到 main 時執行)
Actions
硬體         沒有在 Raspberry Pi 5 加 AI HAT+ 上跑過;Hailo 路徑不存在;
             沒有真實相機、OLED、LED、蜂鳴器
Windows      DirectShow 相機路徑已寫但沒跑過
Webcam       沒有相機時 webcam 測試被跳過
準確度       偵測準確度、距離、誤報率都沒量過
筆電數字     沒有在項目所有人的筆電上跑過 benchmark;這裡做的那份報告用的是替代影片,沒有提交
未決事項     十週時程的落差;兩人備案;三個數字與穩定性測試的門檻;錯誤代碼清單;
             「G. Demo Success Criteria」;監看服務用 Flask 還是標準函式庫伺服器
```

## 10. 第 3 階段就緒清單

```text
□ 三支影片與 test_model.pt 已透過 Git LFS 提交(項目所有人)
□ tests.yml 已在 GitHub 的 review_branch 上跑過,並用真實 fixture 全綠
□ 十週落差與第 3 階段 issue(G、H、I)已決定並寫好
□ Issue 0 補充已核准(核准管道、契約變更流程、預設值)
□ WP C 已開始,因為沒有資料集 G 就無法開始
□ 目標硬體上的真實 benchmark 報告已存在,或已排定日期
□ 沒寫過這份文件的人,只讀本檔、issue 與審查報告就能回答「第 3 階段我要做什麼」
```

## 11. 一句話總結

> 鏈路 A → B → 決策骨架 → E → D 用一個指令就能端到端執行,並寫出完整、可重播的紀錄;封包格式凍結在 schema 0.2,每個部分都在它的 issue 所指名的介面後面——第 3 階段接下來需要真實 fixture、資料集、追蹤器與訓練好的模型,而目前還沒有人檢查過的是真實影片、GitHub Actions 與硬體。
