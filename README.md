# UberEats 消費分析系統

追蹤 UberEats 消費紀錄、分析用餐習慣的本地 Web 應用程式。

## 功能

- 消費統計儀表板（總訂單、總金額、平均金額）
- 手動新增訂單紀錄
- 上傳手機截圖（從 Uber Eats App 截取訂單紀錄）
- 訂單歷史記錄查詢
- SQLite 資料庫儲存

## 使用方式

### 需求

- Python 3.8+（不需要安裝任何套件）

### 啟動

```bash
python simple_server.py
```

瀏覽器會自動開啟 http://localhost:8000

### 使用流程

1. 開啟系統後，可在「手動新增」分頁輸入訂單資料
2. 或在「截圖上傳」分頁上傳 Uber Eats App 的訂單截圖
3. 在首頁查看消費統計

## 技術

- 純 Python 標準函式庫（http.server, sqlite3）
- 前端：Bootstrap 5
- 資料庫：SQLite
- 零依賴，無需 pip install

## 授權

MIT License
