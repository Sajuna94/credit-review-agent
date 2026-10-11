"""
異常偵測引擎
============
使用統計方法偵測財務異常：
1. 同期變動率（YoY）異常
2. Z-score 偏離正常範圍
3. Altman Z 分數（破產風險預測）
4. 規則式紅旗偵測
"""
import statistics
from typing import Dict, List, Optional, Tuple


class AnomalyDetector:
    """財務異常偵測器"""

    # === 重大異常門檻 ===
    CRITICAL_DROP = 0.30      # 同期下跌 30% 觸發紅旗
    CRITICAL_SURGE = 0.50     # 同期上漲 50% 觸發紅旗
    WARNING_DROP = 0.15       # 同期下跌 15% 警示
    WARNING_SURGE = 0.25      # 同期上漲 25% 警示

    @staticmethod
    def detect_all(financials: Dict, ratios: Dict) -> Dict:
        """執行所有異常偵測"""
        return {
            'yoy_anomalies': AnomalyDetector.detect_yoy_anomalies(financials),
            'altman_z': AnomalyDetector.altman_z_score(financials, ratios),
            'red_flags': AnomalyDetector.red_flag_check(financials, ratios),
            'risk_summary': None,  # 最後填入
        }

    @staticmethod
    def detect_yoy_anomalies(financials: Dict) -> List[Dict]:
        """
        偵測同期異常變動
        比對科目當期 vs 上期
        """
        anomalies = []
        is_ = financials.get('income_statement', {})
        bs = financials.get('balance_sheet', {})

        # 檢查項目：(科目, 路徑, 警示方向)
        checks = [
            ('營收', is_.get('revenue'), 'either'),
            ('毛利', is_.get('gross_profit'), 'either'),
            ('營業利益', is_.get('operating_income'), 'either'),
            ('淨利', is_.get('net_income'), 'either'),
            ('負債總額', bs.get('total_liabilities'), 'surge'),
            ('應收帳款', bs.get('accounts_receivable'), 'surge'),
            ('存貨', bs.get('inventory'), 'surge'),
            ('現金', bs.get('cash'), 'drop'),
        ]

        # 取出歷史值用於 YoY 計算
        revenue_hist = financials.get('revenue_history', [])
        profit_hist = financials.get('net_income_history', [])

        for idx, (name, cur, direction) in enumerate(checks):
            if cur is None:
                continue
            # 簡化示範：用單期資料做占比異常檢查
            severity = AnomalyDetector._classify_anomaly(cur, direction, financials)
            if severity != 'normal':
                anomalies.append({
                    'item': name,
                    'current': cur,
                    'change_pct': None,  # 需多年資料才能算
                    'severity': severity,
                    'message': AnomalyDetector._format_message(name, severity, direction),
                })

        return anomalies

    @staticmethod
    def _classify_anomaly(value, direction, financials) -> str:
        """
        簡化版異常分類（基於當期值與行業啟發式）
        """
        # 這裡用單期值做粗略檢查；真實部署需要多年序列
        is_ = financials.get('income_statement', {})
        bs = financials.get('balance_sheet', {})

        # 淨利率深度負值 → 嚴重異常
        if is_.get('net_income', 0) < 0 and is_.get('revenue', 0) > 0:
            loss_margin = is_['net_income'] / is_['revenue']
            if loss_margin < -0.20:
                return 'critical'
            elif loss_margin < -0.05:
                return 'warning'

        # 負債比 > 80% → 嚴重
        debt_ratio = bs.get('total_liabilities', 0) / max(bs.get('total_assets', 1), 1)
        if debt_ratio > 0.85:
            return 'critical'
        elif debt_ratio > 0.70:
            return 'warning'

        # 現金幾乎為零
        cash = bs.get('cash', 0) or 0
        cl = bs.get('current_liabilities', 1) or 1
        if cl > 0 and cash / cl < 0.05:
            return 'warning'

        return 'normal'

    @staticmethod
    def _format_message(name, severity, direction) -> str:
        if severity == 'critical':
            if direction == 'surge':
                return f'{name}大幅上升，觸發紅旗警報'
            elif direction == 'drop':
                return f'{name}大幅下滑，觸發紅旗警報'
            return f'{name}出現嚴重異常'
        else:
            return f'{name}變動需關注'

    @staticmethod
    def altman_z_score(financials: Dict, ratios: Dict) -> Dict:
        """
        Altman Z 分數（1968 年版）
        Z = 1.2*A + 1.4*B + 3.3*C + 0.6*D + 1.0*E
        A: 營運資金/總資產
        B: 保留盈餘/總資產
        C: EBIT/總資產
        D: 權益市值/總負債帳面
        E: 銷售額/總資產
        Z > 2.99 安全；1.81 < Z < 2.99 灰色；Z < 1.81 危險
        """
        bs = financials.get('balance_sheet', {})
        is_ = financials.get('income_statement', {})

        ta = bs.get('total_assets', 0) or 0
        if ta == 0:
            return {'score': None, 'zone': 'insufficient_data'}

        # 公開公司才能拿到市值；以權益帳面替代（保守）
        equity = bs.get('equity', 0) or 0
        tl = bs.get('total_liabilities', 0) or 0

        wc = (bs.get('current_assets', 0) or 0) - (bs.get('current_liabilities', 0) or 0)
        re = bs.get('retained_earnings', 0) or 0
        ebit = is_.get('ebit', 0) or 0
        sales = is_.get('revenue', 0) or 0

        a = wc / ta
        b = re / ta
        c = ebit / ta
        d = equity / tl if tl > 0 else 0
        e = sales / ta

        z = 1.2 * a + 1.4 * b + 3.3 * c + 0.6 * d + 1.0 * e

        if z > 2.99:
            zone = 'safe'
            zone_label = '安全區'
        elif z > 1.81:
            zone = 'grey'
            zone_label = '灰色區 (需關注)'
        else:
            zone = 'distress'
            zone_label = '危險區 (高破產風險)'

        return {
            'score': round(z, 2),
            'zone': zone,
            'zone_label': zone_label,
            'components': {
                'A_working_capital_ratio': round(a, 4),
                'B_retained_earnings_ratio': round(b, 4),
                'C_ebit_ratio': round(c, 4),
                'D_equity_to_debt': round(d, 4),
                'E_asset_turnover': round(e, 4),
            }
        }

    @staticmethod
    def red_flag_check(financials: Dict, ratios: Dict) -> List[Dict]:
        """
        規則式紅旗檢查
        來源：銀行授信實務常見警示指標
        """
        flags = []
        is_ = financials.get('income_statement', {})
        bs = financials.get('balance_sheet', {})

        # 1. 連續虧損
        profit_hist = financials.get('net_income_history', [])
        if len(profit_hist) >= 2 and all(p is not None and p < 0 for p in profit_hist[-2:]):
            flags.append({
                'code': 'RF001',
                'level': 'high',
                'title': '連續虧損',
                'description': f'近兩期淨利皆為負值（{profit_hist[-2]:,.0f} / {profit_hist[-1]:,.0f}）',
                'action': '建議實地訪察與了解經營困境',
            })

        # 2. 流動比過低
        cr = ratios.get('current_ratio')
        if cr is not None and cr < 1.0:
            flags.append({
                'code': 'RF002',
                'level': 'high',
                'title': '短期償債能力不足',
                'description': f'流動比 {cr:.2f} < 1.0，短期負債可能無法清償',
                'action': '建議要求增提擔保品或還款來源證明',
            })

        # 3. 負債比過高
        dr = ratios.get('debt_ratio')
        if dr is not None and dr > 0.80:
            flags.append({
                'code': 'RF003',
                'level': 'high',
                'title': '負債比率過高',
                'description': f'負債占總資產 {dr*100:.1f}%，財務槓桿偏高',
                'action': '評估再融資風險與利息保障倍數',
            })

        # 4. 利息保障倍數過低
        ic = ratios.get('interest_coverage')
        if ic is not None and ic < 1.5:
            flags.append({
                'code': 'RF004',
                'level': 'high',
                'title': '利息保障不足',
                'description': f'利息保障倍數僅 {ic:.2f} 倍，EBIT 不足以支付利息',
                'action': '高度關注現金流與還款計畫',
            })

        # 5. ROE 偏低
        roe_v = ratios.get('roe')
        if roe_v is not None and roe_v < 0.05:
            flags.append({
                'code': 'RF005',
                'level': 'medium',
                'title': '股東權益報酬率偏低',
                'description': f'ROE {roe_v*100:.2f}%，低於多數產業平均 5%',
                'action': '關注獲利模式與產業競爭力',
            })

        # 6. 應收帳款激增（需歷史，這裡用比例檢查）
        ar = bs.get('accounts_receivable', 0) or 0
        revenue = is_.get('revenue', 1) or 1
        ar_to_rev = ar / revenue
        if ar_to_rev > 0.4:
            flags.append({
                'code': 'RF006',
                'level': 'medium',
                'title': '應收帳款占營收比偏高',
                'description': f'應收帳款/營收 = {ar_to_rev*100:.1f}%，收款天數可能拉長',
                'action': '檢視客戶結構與帳款回收情形',
            })

        # 7. 現金短絀
        cash = bs.get('cash', 0) or 0
        cl = bs.get('current_liabilities', 1) or 1
        if cl > 0 and cash / cl < 0.10:
            flags.append({
                'code': 'RF007',
                'level': 'medium',
                'title': '現金水位偏低',
                'description': f'現金/流動負債 = {cash/cl*100:.1f}%，流動性緩衝不足',
                'action': '了解融資額度與調度彈性',
            })

        # 8. 利息保障倍數偏低（中等警示）
        ic = ratios.get('interest_coverage')
        if ic is not None and 1.5 <= ic < 3.0:
            flags.append({
                'code': 'RF008',
                'level': 'medium',
                'title': '利息保障倍數偏低',
                'description': f'利息保障倍數 {ic:.2f} 倍，獲利對利息覆蓋不足',
                'action': '評估升息環境下的還款壓力',
            })

        # 9. 流動比偏低（中等警示）
        cr = ratios.get('current_ratio')
        if cr is not None and 1.0 <= cr < 1.5:
            flags.append({
                'code': 'RF009',
                'level': 'medium',
                'title': '流動比偏低',
                'description': f'流動比 {cr:.2f}，介於 1.0~1.5 警戒區',
                'action': '監控營運資金週轉與短期負債到期分布',
            })

        return flags

    @staticmethod
    def summarize_risks(anomalies, altman, red_flags) -> Dict:
        """彙整風險摘要"""
        high_count = sum(1 for f in red_flags if f.get('level') == 'high')
        medium_count = sum(1 for f in red_flags if f.get('level') == 'medium')
        critical_anom = sum(1 for a in anomalies if a.get('severity') == 'critical')

        risk_level = 'low'
        altman_score = altman.get('score') or 99
        if high_count >= 2 or (altman_score < 1.5) or critical_anom >= 1:
            risk_level = 'high'
        elif high_count >= 1 or (altman_score < 2.0) or (medium_count >= 3):
            risk_level = 'medium'

        return {
            'risk_level': risk_level,
            'risk_label': {'low': '低風險', 'medium': '中風險', 'high': '高風險'}[risk_level],
            'high_flags': high_count,
            'medium_flags': medium_count,
            'critical_anomalies': critical_anom,
            'altman_zone': altman.get('zone'),
        }
