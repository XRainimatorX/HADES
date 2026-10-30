# Decisions

One file, entries accumulated in order. Entry 1 is reserved for decisions recorded outside this repository.

```text
2  單一 repo；資料集與權重以 Git LFS 管理，原始影片不進 repo
3  硬體選型待決——定案前只有一份設定
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
```
