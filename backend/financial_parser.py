"""
財報解析器
==========
支援 PDF（pdfplumber）與 Excel（openpyxl）解析
採用啟發式關鍵字對應，輸出標準化財務資料結構
"""
import re
from typing import Dict, Optional, List
from pathlib import Path


class FinancialParser:
    """財報解析器：PDF / Excel → 標準化 dict"""

    # 關鍵字對映表（中英文 + 常見變體）
    KEYWORD_MAP = {
        # 損益表
        'revenue': ['營業收入', '營業收入總額', '銷貨收入', '營收', 'revenue', 'sales', 'net sales', 'turnover'],
        'gross_profit': ['營業毛利', '毛利', 'gross profit'],
        'operating_income': ['營業利益', '營業淨利', 'operating income', 'operating profit'],
        'ebit': ['EBIT', '息前稅前盈餘', '稅前息前盈餘'],
        'net_income': ['本期淨利', '稅後淨利', '淨利', '淨利潤', 'net income', 'net profit', 'profit after tax'],
        'interest_expense': ['利息費用', '財務費用', 'interest expense'],
        'cogs': ['營業成本', '銷貨成本', 'cost of goods sold', 'cost of sales', 'cogs'],

        # 資產負債表
        'cash': ['現金及約當現金', '現金及銀行存款', '現金', 'cash and cash equivalents', 'cash'],
        'accounts_receivable': ['應收帳款', '應收票據及帳款', '應收款項', 'accounts receivable', 'receivables'],
        'inventory': ['存貨', 'inventory', 'inventories'],
        'current_assets': ['流動資產', 'current assets', 'total current assets'],
        'total_assets': ['資產總額', '總資產', '資產合計', 'total assets'],
        'current_liabilities': ['流動負債', 'current liabilities', 'total current liabilities'],
        'total_liabilities': ['負債總額', '總負債', '負債合計', 'total liabilities'],
        'equity': ['股東權益總額', '權益總額', '業主權益', 'stockholders equity', 'total equity', 'shareholders equity'],
        'retained_earnings': ['保留盈餘', '未分配盈餘', 'retained earnings'],

        # 現金流量表
        'operating_cash_flow': ['營業活動現金流量', '營運活動現金流量', 'operating cash flow', 'cash from operations'],
    }

    @staticmethod
    def parse(file_path: str) -> Dict:
        """
        自動判斷格式並解析
        """
        path = Path(file_path)
        suffix = path.suffix.lower()

        if suffix == '.pdf':
            return FinancialParser.parse_pdf(file_path)
        elif suffix in ('.xlsx', '.xls'):
            return FinancialParser.parse_excel(file_path)
        elif suffix == '.csv':
            return FinancialParser.parse_csv(file_path)
        else:
            return FinancialParser.parse_pdf(file_path)  # 預設

    @staticmethod
    def parse_pdf(file_path: str) -> Dict:
        """解析 PDF 財報"""
        try:
            import pdfplumber
        except ImportError:
            return {'error': 'pdfplumber 未安裝', 'balance_sheet': {}, 'income_statement': {}, 'cash_flow': {}}

        text = ""
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    text += t + "\n"

        return FinancialParser._parse_text(text, source_file=file_path)

    @staticmethod
    def parse_excel(file_path: str) -> Dict:
        """解析 Excel 財報（支援多工作表）"""
        try:
            import openpyxl
        except ImportError:
            return {'error': 'openpyxl 未安裝', 'balance_sheet': {}, 'income_statement': {}, 'cash_flow': {}}

        wb = openpyxl.load_workbook(file_path, data_only=True, read_only=True)
        all_text = ""
        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            sheet_text = f"\n--- {sheet_name} ---\n"
            for row in ws.iter_rows(values_only=True):
                line = " | ".join(str(c) if c is not None else "" for c in row)
                if line.strip(" |"):
                    sheet_text += line + "\n"
            all_text += sheet_text

        wb.close()
        return FinancialParser._parse_text(all_text, source_file=file_path)

    @staticmethod
    def parse_csv(file_path: str) -> Dict:
        """解析 CSV 財報"""
        text = Path(file_path).read_text(encoding='utf-8', errors='ignore')
        return FinancialParser._parse_text(text, source_file=file_path)

    @staticmethod
    def _parse_text(text: str, source_file: str = '') -> Dict:
        """
        從文本中萃取財務數字
        使用關鍵字對映 + 正則表達式
        """
        result = {
            'source_file': source_file,
            'company_name': FinancialParser._extract_company_name(text),
            'period': FinancialParser._extract_period(text),
            'balance_sheet': {},
            'income_statement': {},
            'cash_flow': {},
            'extraction_log': [],  # 記錄每個科目的萃取過程
        }

        # 將文本切成行，逐行掃描
        lines = text.split('\n')

        for field, keywords in FinancialParser.KEYWORD_MAP.items():
            value = FinancialParser._find_value(lines, keywords)
            if value is not None:
                target = FinancialParser._classify_field(field)
                target_dict = result[target]
                target_dict[field] = value
                result['extraction_log'].append({
                    'field': field,
                    'value': value,
                    'matched_keyword': FinancialParser._find_matched_keyword(lines, keywords),
                })

        # 衍生：若無 EBIT 資料，用 operating_income 估計
        if not result['income_statement'].get('ebit') and result['income_statement'].get('operating_income'):
            result['income_statement']['ebit'] = result['income_statement']['operating_income']

        # 衍生：估算有效稅率（若無資料）
        result['income_statement']['tax_rate'] = 0.20

        # 若無明細分項，給出歷史序列以利成長性計算
        result['revenue_history'] = [result['income_statement'].get('revenue') or 0]
        result['net_income_history'] = [result['income_statement'].get('net_income') or 0]

        return result

    @staticmethod
    def _find_value(lines: List[str], keywords: List[str]) -> Optional[float]:
        """
        從行列表中找第一個匹配關鍵字的數值
        """
        for line in lines:
            line_lower = line.lower()
            for kw in keywords:
                kw_lower = kw.lower()
                if kw_lower in line_lower:
                    nums = FinancialParser._extract_numbers_from_line(line)
                    if nums:
                        # 取最大的數字（通常是金額而非年度）
                        return max(nums, key=abs)
        return None

    @staticmethod
    def _find_matched_keyword(lines: List[str], keywords: List[str]) -> Optional[str]:
        for line in lines:
            line_lower = line.lower()
            for kw in keywords:
                if kw.lower() in line_lower:
                    return kw
        return None

    @staticmethod
    def _extract_numbers_from_line(line: str) -> List[float]:
        """
        從一行中萃取所有數字（處理千分位、負號、括號）
        """
        # 移除常見的貨幣符號
        clean = line.replace('$', '').replace('NT$', '').replace('NTD', '').replace('元', '').replace(',', '')

        # 處理括號表示負數: (123) → -123
        def parens_to_neg(m):
            return f"-{m.group(1)}"
        clean = re.sub(r'\(([0-9.]+)\)', parens_to_neg, clean)

        # 找所有數字
        matches = re.findall(r'-?\d+\.?\d*', clean)
        nums = []
        for m in matches:
            try:
                n = float(m)
                if abs(n) > 0.01:  # 過濾 0
                    nums.append(n)
            except ValueError:
                pass
        return nums

    @staticmethod
    def _classify_field(field: str) -> str:
        if field in ('operating_cash_flow',):
            return 'cash_flow'
        elif field in ('revenue', 'gross_profit', 'operating_income', 'ebit', 'net_income', 'interest_expense', 'cogs'):
            return 'income_statement'
        else:
            return 'balance_sheet'

    @staticmethod
    def _extract_company_name(text: str) -> str:
        """從文本前幾行抓公司名稱"""
        # 常見模式：公司名稱 + 股份有限公司 / Inc. / Corp.
        patterns = [
            r'([\u4e00-\u9fff]{2,15}(?:股份有限公司|有限公司|集團|公司))',
            r'([A-Z][A-Za-z]+(?:\s+(?:Inc|Corp|Ltd|Co|LLC)\.?))',
        ]
        lines = text.split('\n')[:20]
        for line in lines:
            for p in patterns:
                m = re.search(p, line)
                if m:
                    return m.group(1).strip()
        return '未識別公司'

    @staticmethod
    def _extract_period(text: str) -> str:
        """從文本抓取會計期間"""
        # 模式：民國 XXX 年、X 年、X 年第 X 季、FY2024、Q1 2024
        patterns = [
            r'(?:民國\s*)?(\d{2,3})\s*年(?:度)?',
            r'FY\s*(\d{4})',
            r'(\d{4})\s*Q[1-4]',
            r'(\d{4})/(\d{2})/(\d{2})',
        ]
        for p in patterns:
            m = re.search(p, text)
            if m:
                return m.group(0)
        return '未識別期間'

    @staticmethod
    def create_sample_csv(output_path: str = None) -> str:
        """產生示範用 CSV 財報（用於 demo）"""
        sample = """會計科目,金額
營業收入,1200000000
營業成本,840000000
營業毛利,360000000
營業利益,180000000
利息費用,20000000
稅前淨利,160000000
所得稅費用,32000000
本期淨利,128000000
現金及約當現金,150000000
應收帳款,240000000
存貨,180000000
流動資產,720000000
資產總額,2000000000
流動負債,500000000
負債總額,1200000000
股東權益總額,800000000
保留盈餘,400000000
營業活動現金流量,200000000
"""
        if output_path:
            Path(output_path).write_text(sample, encoding='utf-8')
            return output_path
        return sample
