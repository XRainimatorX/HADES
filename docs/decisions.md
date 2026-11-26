# Decisions

One file, entries accumulated in order. Entry 1 is reserved for decisions recorded outside this repository.

```text
2  單一 repo；資料集與權重以 Git LFS 管理，原始影片不進 repo
3  硬體選型待決——定案前只有一份設定（已由第7項取代）
4  紀錄模組命名為 telemetry，避免與 Python 內建的 logging 混淆
5  文件4任務2的「7 份 spec」合併為一份 spec.md
6  spec 只定義各工作包發出的封包格式與函式簽名；串接關係、驗收測試、
   需求對照、行為規則移入工作 issue；標準接口規格留在 PRD Ⅳ
7   硬體定案：Raspberry Pi 5 4GB + AI HAT+ 26 TOPS（Hailo-8）；
    相機與鏡頭的最終選型待第3階段實測後決定
8   第2階段不連接任何實體裝置，Pi 相機與 OLED 以虛擬方式實作
9   模型：以 Ultralytics YOLOv8 開發；第2階段用 YOLOv8n，
    第3階段比較 YOLOv8n 與 YOLOv8s 後定案
10  授權：MVP 期間使用 AGPL-3.0；任何商用交付前，須購買企業授權
    或依換模型程序改用 Apache-2.0 模型
11  換模型韌性：資料、評估與模型無關的原則確立；
    具體程序於第3階段 G、H 的 issue 中定義
12  第2階段的 decision 骨架只回報 SCANNING 狀態、不發任何命令，
    讓 D 的整合驗收有 SystemState 可顯示；閾值、冷卻與狀態轉換於第4階段實作
13  封包格式 0.1 升為 0.2，一次做完：FramePacket 加 source_id（v0.2 固定 "cam0"）、
    設定檔 source 加 width / height / fps、ErrorRecord.package 放寬為任何大寫字串；
    spec.md、contracts.py、範例封包、設定檔與契約測試在同一個 commit 更新
14  所有多項目欄位一律用 tuple（空結果是空 tuple），FramePacket 的影像建立時設為唯讀、
    不參與封包比較；轉換由呼叫端負責，封包本身不轉換（照 Issue 0）
15  類別名稱以 contracts.CLASS_NAMES 為唯一來源；data/classes.yaml 由測試比對，
    偵測器不再自己讀 classes.yaml
16  第2階段「看到 → LED 亮」由主程式直接驅動 mock：偵測到目標就把設定的警示送給
    alert mock，下一個沒有目標的 frame 關掉；decision 骨架不變（見第12項）。
    這是暫時做法，第4階段由 decision 層取代
17  MockAlert 以最小版本從 J 提前實作（只記錄命令、回報狀態），讓第2階段能在筆電上
    示範；實體 LED、蜂鳴器、雷射驅動仍是第4階段 J
18  bench/reports/ 進 git；runs/ 仍不進 git。第一次 benchmark 若用的不是真實影片或
    不是目標硬體，不提交報告
19  ReplaySource 與 VideoFileSource 暫不合併，延到第4階段 K（live 與 playback 對照）
20  來源在 close() 之後 read() 回傳 None（輸入已停止）；從沒 open() 過就 read() 是錯誤。
    ReplaySource 預設依影片速率放幀（像直播），測試可傳 realtime=False
21  Python 3.11；依賴釘死到實測版本；ultralytics 放獨立的 detect 依賴組，train 組沿用
22  test_model.pt（官方 YOLOv8n 權重）由專案負責人用 Git LFS 提交；此環境的網路代理擋住
    LFS 上傳，所以沒有從這裡推。三支 fixture 影片同樣由專案負責人提交
23  虛擬 OLED 只在終端機印出（8 行 × 21 字元），不開視窗、不寫檔、不用 Pillow；
    網頁監看預設只綁 127.0.0.1，開放到網路要明確指定 host
```
