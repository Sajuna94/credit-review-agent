"""
授信覆審 AI Agent（核心協調者）
================================
採用「確定性 Pipeline + 模板化敘述」設計：
- 數值分析：純演算法（financial_ratios + anomaly_detector）
- 文字生成：模板填空（report_generator），不呼叫 LLM

這個設計的核心目的：避免 LLM 對財務數字產生幻覺
每一句結論都對應到具體計算結果，可逐項驗證
"""
from typing import Dict, List, Optional
from pathlib import Path
import json

from .financial_parser import FinancialParser
from .financial_ratios import FinancialRatios
from .anomaly_detector import AnomalyDetector
from .report_generator import ReportGenerator


class CreditReviewAgent:
    """授信覆審 AI Agent"""

    def __init__(self, data_dir: str = None):
        self.data_dir = data_dir or str(Path(__file__).parent.parent / 'data')
        Path(self.data_dir).mkdir(parents=True, exist_ok=True)

    def review(self, file_path: str, output_dir: str = None) -> Dict:
        """
        完整覆審流程（Pipeline）
        Step 1: 解析財報
        Step 2: 計算財務比率
        Step 3: 異常偵測 + 紅旗檢查
        Step 4: 生成 HTML 報告
        Step 5: 儲存 JSON 結果（供前端使用）
        """
        output_dir = output_dir or str(Path(__file__).parent.parent / 'reports')
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        # Step 1: 解析
        parsed = FinancialParser.parse(file_path)

        # Step 2: 比率
        ratios = FinancialRatios.compute_all(parsed)

        # Step 3: 異常
        anomalies = AnomalyDetector.detect_all(parsed, ratios)
        risk_summary = AnomalyDetector.summarize_risks(
            anomalies.get('yoy_anomalies', []),
            anomalies.get('altman_z', {}),
            anomalies.get('red_flags', []),
        )
        anomalies['risk_summary'] = risk_summary

        # Step 4: HTML
        html = ReportGenerator.generate(parsed, ratios, anomalies)

        # Step 5: 存檔
        ts = Path(file_path).stem
        company_slug = parsed.get('company_name', 'company').replace(' ', '_')
        html_path = Path(output_dir) / f"report_{company_slug}_{ts}.html"
        json_path = Path(output_dir) / f"report_{company_slug}_{ts}.json"

        html_path.write_text(html, encoding='utf-8')

        result = {
            'company': parsed.get('company_name', '未識別'),
            'period': parsed.get('period', '未識別'),
            'source_file': file_path,
            'parsed': parsed,
            'ratios': ratios,
            'anomalies': anomalies,
            'risk_summary': risk_summary,
        }

        # JSON 移除無法序列化的內容
        json_safe = json.loads(json.dumps(result, default=str, ensure_ascii=False))
        json_path.write_text(json.dumps(json_safe, ensure_ascii=False, indent=2), encoding='utf-8')

        result['html_path'] = str(html_path)
        result['json_path'] = str(json_path)

        return result

    def review_text(self, financial_text: str, company_name: str = '測試案例', period: str = '示範') -> Dict:
        """直接從文字內容分析（不需檔案）"""
        parsed = FinancialParser._parse_text(financial_text)
        parsed['company_name'] = company_name
        parsed['period'] = period

        ratios = FinancialRatios.compute_all(parsed)
        anomalies = AnomalyDetector.detect_all(parsed, ratios)
        risk_summary = AnomalyDetector.summarize_risks(
            anomalies.get('yoy_anomalies', []),
            anomalies.get('altman_z', {}),
            anomalies.get('red_flags', []),
        )
        anomalies['risk_summary'] = risk_summary

        return {
            'company': company_name,
            'period': period,
            'parsed': parsed,
            'ratios': ratios,
            'anomalies': anomalies,
            'risk_summary': risk_summary,
        }

    def get_demo_data(self) -> Dict:
        """產生三個示範案例（好/中/差）"""
        return {
            'case_a_strong': self._build_case_strong(),
            'case_b_medium': self._build_case_medium(),
            'case_c_weak': self._build_case_weak(),
        }

    def _build_case_strong(self) -> Dict:
        text = """營業收入,2400000000
營業成本,1440000000
營業毛利,960000000
營業利益,360000000
利息費用,20000000
稅前淨利,340000000
所得稅費用,68000000
本期淨利,272000000
現金及約當現金,500000000
應收帳款,300000000
存貨,200000000
流動資產,1300000000
資產總額,3000000000
流動負債,400000000
負債總額,1200000000
股東權益總額,1800000000
保留盈餘,900000000
營業活動現金流量,400000000"""
        return self.review_text(text, '示範A_穩健企業', '2024 年度')

    def _build_case_medium(self) -> Dict:
        text = """營業收入,1800000000
營業成本,1260000000
營業毛利,540000000
營業利益,150000000
利息費用,30000000
稅前淨利,120000000
所得稅費用,24000000
本期淨利,96000000
現金及約當現金,50000000
應收帳款,400000000
存貨,300000000
流動資產,1050000000
資產總額,2400000000
流動負債,720000000
負債總額,1400000000
股東權益總額,1000000000
保留盈餘,400000000
營業活動現金流量,140000000"""
        return self.review_text(text, '示範B_中等企業', '2024 年度')

    def _build_case_weak(self) -> Dict:
        text = """營業收入,800000000
營業成本,650000000
營業毛利,150000000
營業利益,-20000000
利息費用,40000000
稅前淨利,-60000000
所得稅費用,0
本期淨利,-60000000
現金及約當現金,30000000
應收帳款,350000000
存貨,280000000
流動資產,700000000
資產總額,1800000000
流動負債,800000000
負債總額,1500000000
股東權益總額,300000000
保留盈餘,50000000
營業活動現金流量,20000000"""
        return self.review_text(text, '示範C_高風險企業', '2024 年度')
