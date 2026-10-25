# repo 結構

活文件：隨 repo 實際建立與調整而更新。

## 一、repo 結構

```text
hades/
├── README.md                    是什麼、怎麼跑、去哪找
├── CONTRIBUTING.md              開發紀律
├── pyproject.toml               依賴分三組：core / dev / train；
│                                程式入口：hades-run、hades-replay
├── .gitignore
├── .gitattributes               Git LFS 規則
├── .github/
│   ├── CODEOWNERS               contracts.py 的修改須經項目所有人審核
│   └── ISSUE_TEMPLATE/
│       └── work_issue.md        
│
├── src/hades/                   上機執行的全部
│   ├── contracts.py             所有封包、狀態機、各層介面
│   ├── sources.py               影像來源：picam / webcam / video
│   ├── detect.py                偵測器介面與實作
│   ├── track.py                 追蹤與過濾
│   ├── decide.py                狀態機、threshold → trigger
│   ├── alert.py                 觸發輸出：mock、LED、蜂鳴器、雷射、OLED
│   ├── monitor.py               開發用網頁監看
│   ├── telemetry.py             事件紀錄、run metadata、重播
│   ├── config.py                設定載入與驗證
│   └── pipeline.py              組裝整條鏈、主迴圈、診斷模式
│
├── ml/                          訓練線，不上機
│   ├── dataset.py               切 frame、整理、split
│   ├── train.py                 訓練、評估、模型選擇
│   ├── analysis.py              誤報 / 漏報分析
│   └── export.py                轉成上機用的模型格式
│
├── bench/
│   ├── benchmark.py             延遲、FPS、記憶體量測
│   └── stability.py             長時間穩定性測試
│
├── data/                        資料集
│   ├── classes.yaml             v0.1 只有一類：一般消費級無人機
│   ├── annotation_guideline.md  標註規範
│   ├── demo/                    demo 重播用片段
│   └── dataset_v1/
│       ├── images/{train,val,test}/
│       ├── labels/{train,val,test}/
│       └── split_manifest.csv
│
├── models/                      模型權重
├── configs/
│   └── default.yaml             threshold、cooldown、模型路徑、硬體設定
├── tests/
│   ├── test_*.py                各模組的單元測試
│   ├── integration/             整條鏈的整合測試
│   └── fixtures/                固定測試片段
├── hardware/                    接線圖、pin map、BOM
└── docs/
    ├── spec.md                  封包規格
    ├── architecture.md          系統怎麼運作
    ├── test-plan.md             三個數字怎麼量、什麼不算量到
    ├── decisions.md             決策紀錄
    ├── PRD.md                   
    └── plan.md                  
```

## 二、資料與權重

```text
走 Git LFS     data/ 的影像與 demo 片段、models/ 的權重檔、
               tests/fixtures/ 的測試片段
一般 git       標註檔、classes.yaml、split_manifest.csv、標註規範
不進 repo      原始影片——體積最大，放進 LFS 會很快用完免費額度
成員設定       預設跳過 LFS 下載；只有做 C、G、H 的成員才拉資料
帳號設定       登記付款方式並設預算上限，避免額度用完被封鎖
```

## 三、18 個工作包對應

| 工作包 | 位置 |
|---|---|
| A Video Input | `src/hades/sources.py` |
| B Detection | `src/hades/detect.py` |
| C Dataset | `ml/dataset.py`、`data/` |
| D UI / Monitoring | OLED → `alert.py`；網頁 → `monitor.py` |
| E Logging / Replay | `src/hades/telemetry.py` |
| F Test Harness / Benchmark | `bench/benchmark.py`、`tests/` |
| G Training | `ml/train.py`、`ml/export.py`、`models/` |
| H FP / FN 分析 | `ml/analysis.py` |
| I Tracking | `src/hades/track.py` |
| J Actuator Mock / Driver | `src/hades/alert.py` |
| K Integration Test | `tests/integration/` |
| L UI integration | `src/hades/monitor.py` |
| M Replay Demo | `telemetry.py`、`hades-replay`、`data/demo/` |
| N Final Log Cleanup | `src/hades/telemetry.py` |
| O Stability Run | `bench/stability.py` |
| P Diagnostic Mode | `src/hades/pipeline.py` |
| Q Quick Config | `src/hades/config.py`、`configs/default.yaml` |
| R Error Logging | `src/hades/telemetry.py` |

## 四、第一批決策紀錄

見 [`docs/decisions.md`](decisions.md)。
