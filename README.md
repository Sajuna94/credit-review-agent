# 企業授信覆審 AI Agent — POC

## 快速啟動

```bash
unzip credit_review_agent_poc.zip
cd credit_review_agent
pip install -r requirements.txt
python app.py
# 開啟瀏覽器: http://localhost:5000/
```

## 系統功能

### 1. 個案分析（Tab 1）
上傳財報（PDF / Excel / CSV / TXT）→ AI 自動分析 → 即時產出風險報告

### 2. 示範案例（Tab 2）
三種風險等級的代表性企業：
- A級穩健企業（健康分數 92.9）
- B級中等企業（健康分數 71.8，2 個中度警示）
- C級高風險企業（健康分數 14.1，6 個紅旗）

### 3. AI vs 人工比較（Tab 3）
量化展示 AI 自動分析相較人工的：
- 數字萃取準確率：91.7%
- 紅旗偵測 F1：66.7%
- Hallucination 率：21.4%
- 效率提升：780 倍

### 4. 系統架構（Tab 4）
說明「確定性 Pipeline + 模板化敘述」設計如何避免 LLM hallucination

## 技術棧
- 後端：Python 3.11 + Flask + Pandas + pdfplumber + openpyxl
- 前端：純 HTML/CSS/JS（零框架依賴）
- 分析：確定性演算法 + 統計異常偵測

## 檔案結構
```
credit_review_agent/
├── app.py                      # Flask API server（8 個端點）
├── requirements.txt
├── backend/
│   ├── agent.py                # AI Agent 協調者
│   ├── financial_parser.py     # 財報解析（PDF/Excel/CSV）
│   ├── financial_ratios.py     # 16 項財務比率 + 健康評分
│   ├── anomaly_detector.py     # 9 條紅旗規則 + Altman Z
│   ├── report_generator.py     # 模板化 HTML 報告
│   └── comparator.py           # AI vs 人工差異量化
├── frontend/
│   └── index.html              # 單頁前端（30KB，4 個 tab）
├── reports/                    # 生成的 HTML 報告
└── data/uploads/               # 上傳檔案暫存
```

## 核心設計：避免 Hallucination

所有數值分析（比率、Z 分數、紅旗）皆由 Python 確定性演算法計算，無隨機性。
所有敘述文字（報告、覆審意見）採用「if-else 模板 + 數字填空」，不呼叫 LLM。
每句結論都對應到具體財務數字，可逐項追溯驗證。
