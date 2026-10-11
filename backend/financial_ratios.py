"""
財務比率計算引擎
=================
純演算法實作：償債能力、流動性、獲利能力、槓桿、現金流
所有公式來自銀行授信實務手冊與財務分析教科書
"""
from typing import Dict, List, Optional
import pandas as pd


class FinancialRatios:
    """計算企業財務比率"""

    @staticmethod
    def compute_all(financials: Dict) -> Dict:
        """
        輸入：financials dict 含 balance_sheet, income_statement, cash_flow
        輸出：所有比率 + 健康度評分
        """
        bs = financials.get('balance_sheet', {})
        is_ = financials.get('income_statement', {})
        cf = financials.get('cash_flow', {})

        ratios = {
            # === 償債能力 ===
            'current_ratio': FinancialRatios.current_ratio(bs),
            'quick_ratio': FinancialRatios.quick_ratio(bs),
            'cash_ratio': FinancialRatios.cash_ratio(bs),
            'debt_ratio': FinancialRatios.debt_ratio(bs),
            'debt_to_equity': FinancialRatios.debt_to_equity(bs),
            'interest_coverage': FinancialRatios.interest_coverage(is_),

            # === 獲利能力 ===
            'gross_margin': FinancialRatios.gross_margin(is_),
            'operating_margin': FinancialRatios.operating_margin(is_),
            'net_margin': FinancialRatios.net_margin(is_),
            'roe': FinancialRatios.roe(is_, bs),
            'roa': FinancialRatios.roa(is_, bs),
            'roic': FinancialRatios.roic(is_, bs),

            # === 成長性 ===
            'revenue_growth': FinancialRatios.revenue_growth(financials),
            'profit_growth': FinancialRatios.profit_growth(financials),

            # === 營運效率 ===
            'asset_turnover': FinancialRatios.asset_turnover(is_, bs),
            'receivable_turnover': FinancialRatios.receivable_turnover(is_, bs),
            'inventory_turnover': FinancialRatios.inventory_turnover(is_, bs),
        }

        ratios['health_score'] = FinancialRatios.health_score(ratios)
        ratios['health_grade'] = FinancialRatios.health_grade(ratios['health_score'])

        return ratios

    @staticmethod
    def _safe_div(a, b):
        if a is None or b is None or b == 0:
            return None
        return a / b

    # === 償債能力 ===
    @staticmethod
    def current_ratio(bs):
        return FinancialRatios._safe_div(bs.get('current_assets'), bs.get('current_liabilities'))

    @staticmethod
    def quick_ratio(bs):
        ca = bs.get('current_assets', 0) or 0
        inv = bs.get('inventory', 0) or 0
        cl = bs.get('current_liabilities', 0) or 0
        if cl == 0:
            return None
        return (ca - inv) / cl

    @staticmethod
    def cash_ratio(bs):
        return FinancialRatios._safe_div(bs.get('cash'), bs.get('current_liabilities'))

    @staticmethod
    def debt_ratio(bs):
        ta = bs.get('total_assets', 0) or 0
        tl = bs.get('total_liabilities', 0) or 0
        if ta == 0:
            return None
        return tl / ta

    @staticmethod
    def debt_to_equity(bs):
        return FinancialRatios._safe_div(bs.get('total_liabilities'), bs.get('equity'))

    @staticmethod
    def interest_coverage(is_):
        ebit = is_.get('ebit', 0) or 0
        interest = is_.get('interest_expense', 0) or 0
        if interest == 0:
            return None
        return ebit / interest

    # === 獲利能力 ===
    @staticmethod
    def gross_margin(is_):
        return FinancialRatios._safe_div(is_.get('gross_profit'), is_.get('revenue'))

    @staticmethod
    def operating_margin(is_):
        return FinancialRatios._safe_div(is_.get('operating_income'), is_.get('revenue'))

    @staticmethod
    def net_margin(is_):
        return FinancialRatios._safe_div(is_.get('net_income'), is_.get('revenue'))

    @staticmethod
    def roe(is_, bs):
        return FinancialRatios._safe_div(is_.get('net_income'), bs.get('equity'))

    @staticmethod
    def roa(is_, bs):
        return FinancialRatios._safe_div(is_.get('net_income'), bs.get('total_assets'))

    @staticmethod
    def roic(is_, bs):
        ebit = is_.get('ebit', 0) or 0
        tax_rate = is_.get('tax_rate', 0.20) or 0.20
        nopat = ebit * (1 - tax_rate)
        invested = (bs.get('equity', 0) or 0) + (bs.get('total_liabilities', 0) or 0)
        if invested == 0:
            return None
        return nopat / invested

    # === 成長性 ===
    @staticmethod
    def revenue_growth(financials):
        years = financials.get('revenue_history', [])
        if len(years) < 2:
            return None
        cur, prev = years[-1], years[-2]
        if not prev or prev == 0:
            return None
        return (cur - prev) / prev

    @staticmethod
    def profit_growth(financials):
        years = financials.get('net_income_history', [])
        if len(years) < 2:
            return None
        cur, prev = years[-1], years[-2]
        if prev is None or prev == 0:
            return None
        return (cur - prev) / prev

    # === 營運效率 ===
    @staticmethod
    def asset_turnover(is_, bs):
        return FinancialRatios._safe_div(is_.get('revenue'), bs.get('total_assets'))

    @staticmethod
    def receivable_turnover(is_, bs):
        return FinancialRatios._safe_div(is_.get('revenue'), bs.get('accounts_receivable'))

    @staticmethod
    def inventory_turnover(is_, bs):
        return FinancialRatios._safe_div(is_.get('cogs'), bs.get('inventory'))

    # === 綜合健康度評分 ===
    @staticmethod
    def health_score(ratios: Dict) -> float:
        """
        加權評分模型 (0-100)
        權重：償債 35% / 獲利 35% / 成長 15% / 效率 15%
        """
        score = 0.0
        total_weight = 0.0

        # 償債 35 分
        cr = ratios.get('current_ratio')
        if cr is not None:
            # 流動比 1.5-2.0 為最佳
            if cr >= 1.5:
                score += 12
            elif cr >= 1.0:
                score += 8
            else:
                score += 3
            total_weight += 12

        dr = ratios.get('debt_ratio')
        if dr is not None:
            # 負債比 < 0.6 為佳
            if dr < 0.4:
                score += 12
            elif dr < 0.6:
                score += 9
            elif dr < 0.8:
                score += 5
            else:
                score += 1
            total_weight += 12

        ic = ratios.get('interest_coverage')
        if ic is not None:
            if ic >= 5:
                score += 11
            elif ic >= 2:
                score += 7
            else:
                score += 2
            total_weight += 11

        # 獲利 35 分
        nm = ratios.get('net_margin')
        if nm is not None:
            if nm >= 0.10:
                score += 12
            elif nm >= 0.05:
                score += 8
            elif nm >= 0:
                score += 4
            else:
                score += 0
            total_weight += 12

        roe_v = ratios.get('roe')
        if roe_v is not None:
            if roe_v >= 0.15:
                score += 12
            elif roe_v >= 0.10:
                score += 9
            elif roe_v >= 0.05:
                score += 5
            else:
                score += 1
            total_weight += 12

        roa_v = ratios.get('roa')
        if roa_v is not None:
            if roa_v >= 0.08:
                score += 11
            elif roa_v >= 0.04:
                score += 7
            else:
                score += 2
            total_weight += 11

        # 成長 15 分
        rg = ratios.get('revenue_growth')
        if rg is not None:
            if rg >= 0.10:
                score += 8
            elif rg >= 0:
                score += 5
            else:
                score += 1
            total_weight += 8

        pg = ratios.get('profit_growth')
        if pg is not None:
            if pg >= 0.15:
                score += 7
            elif pg >= 0:
                score += 4
            else:
                score += 0
            total_weight += 7

        # 效率 15 分
        at = ratios.get('asset_turnover')
        if at is not None:
            if at >= 1.0:
                score += 8
            elif at >= 0.5:
                score += 5
            else:
                score += 2
            total_weight += 8

        rt = ratios.get('receivable_turnover')
        if rt is not None:
            if rt >= 8:
                score += 7
            elif rt >= 4:
                score += 4
            else:
                score += 1
            total_weight += 7

        if total_weight == 0:
            return 0
        return round((score / total_weight) * 100, 1)

    @staticmethod
    def health_grade(score: float) -> str:
        if score >= 80:
            return 'A 級 (低風險)'
        elif score >= 65:
            return 'B 級 (中低風險)'
        elif score >= 50:
            return 'C 級 (中等風險)'
        elif score >= 35:
            return 'D 級 (中高風險)'
        else:
            return 'E 級 (高風險)'

    @staticmethod
    def format_ratio(value, fmt='pct', digits=2):
        """格式化比率數值"""
        if value is None:
            return 'N/A'
        if fmt == 'pct':
            return f"{value * 100:.{digits}f}%"
        elif fmt == 'ratio':
            return f"{value:.{digits}f}"
        elif fmt == 'times':
            return f"{value:.{digits}f} 倍"
        return str(value)
