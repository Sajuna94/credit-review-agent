"""
AI vs 人工分析差異比較器
=========================
用於驗證 AI 自動分析的品質，比較：
- AI 提取的數字 vs 人工覆核的數字（準確率）
- AI 判定的紅旗 vs 人工判定的紅旗（覆蓋率、誤報率）
- AI 報告 vs 人工報告的關鍵指標一致性
- 計算 hallucination 率：AI 報告中提到但原始資料沒有的項目
"""
from typing import Dict, List


class AIvsHumanComparator:
    """AI vs 人工分析差異比較器"""

    @staticmethod
    def compare_numbers(ai_extracted: Dict, human_extracted: Dict, tolerance: float = 0.01) -> Dict:
        """
        比較 AI 與人工從同一份財報萃取的數字
        只比對「人工有覆核」的核心欄位，AI 多萃取的視為加分項
        tolerance: 容許誤差（1%）
        """
        # 只比對人工有覆核的欄位（避免 AI 多萃取導致假性低分）
        if not human_extracted:
            return {
                'total_fields': 0, 'matched': 0, 'mismatched': 0,
                'missing_in_ai': 0, 'missing_in_human': 0,
                'match_rate': 100.0, 'details': [],
            }

        all_fields = set(human_extracted.keys())

        results = {
            'total_fields': len(all_fields),
            'matched': 0,
            'mismatched': 0,
            'missing_in_ai': 0,
            'missing_in_human': 0,
            'details': [],
        }

        for field in sorted(all_fields):
            ai_v = ai_extracted.get(field)
            hu_v = human_extracted.get(field)

            if ai_v is None and hu_v is not None:
                results['missing_in_ai'] += 1
                results['details'].append({
                    'field': field, 'ai': None, 'human': hu_v,
                    'status': 'MISSING_IN_AI'
                })
            elif ai_v is not None and hu_v is None:
                continue  # AI 多萃取，視為加分
            elif ai_v is None and hu_v is None:
                continue
            else:
                if hu_v == 0:
                    diff = abs(ai_v)
                else:
                    diff = abs(ai_v - hu_v) / abs(hu_v)
                if diff <= tolerance:
                    results['matched'] += 1
                    status = 'MATCH'
                else:
                    results['mismatched'] += 1
                    status = 'MISMATCH'
                results['details'].append({
                    'field': field, 'ai': ai_v, 'human': hu_v,
                    'diff_pct': round(diff * 100, 2),
                    'status': status,
                })

        if results['total_fields'] > 0:
            results['match_rate'] = round(results['matched'] / results['total_fields'] * 100, 1)
        else:
            results['match_rate'] = 100.0

        # 額外加分：AI 萃取到但人工沒列的欄位
        extra_fields = [k for k in ai_extracted if k not in human_extracted and ai_extracted.get(k) is not None]
        results['ai_extra_fields'] = extra_fields
        results['extraction_coverage'] = f"{results['matched'] + results['mismatched']}/{len(human_extracted)} 一致; AI 多萃取 {len(extra_fields)} 項"

        return results

    @staticmethod
    def check_hallucination(report_html: str, source_data: Dict) -> Dict:
        """
        檢查報告中提到的關鍵數字是否都來自原始資料
        焦點放在「金額級距」的數字（百萬/億），排除比率百分比與 CSS 樣式碼
        """
        import re

        # 先剝離 <style>...</style> 區塊（CSS 顏色碼如 #3b82f6）
        clean_html = re.sub(r'<style[^>]*>.*?</style>', '', report_html, flags=re.DOTALL | re.IGNORECASE)
        # 也剝離顏色相關屬性
        clean_html = re.sub(r'#[0-9a-fA-F]{3,6}', '', clean_html)
        # 剝離所有 HTML 標籤
        clean_html = re.sub(r'<[^>]+>', ' ', clean_html)

        # 抓出報告中所有 > 1000 的數字（金額級距）
        numbers_in_report = re.findall(r'[\d,]+\.?\d*', clean_html)
        report_numbers = set()
        for n in numbers_in_report:
            try:
                v = float(n.replace(',', ''))
                if abs(v) >= 1000:
                    report_numbers.add(v)
            except ValueError:
                pass

        # 收集來源資料中的所有「金額級距」數字
        source_numbers = set()
        flat = AIvsHumanComparator._flatten(source_data)
        for v in flat.values():
            if isinstance(v, (int, float)) and abs(v) >= 1000:
                source_numbers.add(float(v))
                if abs(v) >= 1e8:
                    source_numbers.add(round(v / 1e8, 2))
                if abs(v) >= 1e4:
                    source_numbers.add(round(v / 1e4, 0))

        # 也加入比率（指標的數字）
        for v in flat.values():
            if isinstance(v, (int, float)) and 0 < abs(v) < 100:
                source_numbers.add(round(v, 2))
                source_numbers.add(round(v * 100, 2))

        # 健康分數（0-100）
        for v in flat.values():
            if isinstance(v, (int, float)) and 0 < abs(v) <= 100:
                source_numbers.add(round(v, 1))

        def fuzzy_match(target, pool, tol=0.05):
            for p in pool:
                if p == 0:
                    if abs(target) < 1:
                        return True
                    continue
                if abs(target - p) / abs(p) <= tol:
                    return True
            return False

        verified = 0
        unverified = []
        for n in report_numbers:
            if fuzzy_match(n, source_numbers, 0.05):
                verified += 1
            else:
                unverified.append(n)

        total = len(report_numbers)
        hallucination_rate = round((len(unverified) / total * 100), 1) if total > 0 else 0.0

        return {
            'total_numbers_in_report': total,
            'verified_numbers': verified,
            'unverified_count': len(unverified),
            'hallucination_rate': hallucination_rate,
            'unverified_samples': unverified[:10],
            'note': '已剝離 CSS 樣式碼，僅比對文字內容中的數字',
        }

    @staticmethod
    def _flatten(d: Dict, prefix='') -> Dict:
        out = {}
        for k, v in d.items():
            key = f"{prefix}.{k}" if prefix else k
            if isinstance(v, dict):
                out.update(AIvsHumanComparator._flatten(v, key))
            else:
                out[key] = v
        return out

    @staticmethod
    def compare_flags(ai_flags: List[Dict], human_flags: List[Dict]) -> Dict:
        """
        比較 AI 與人工識別的紅旗
        """
        ai_codes = {f.get('code', '') for f in ai_flags}
        hu_codes = {f.get('code', '') for f in human_flags}

        true_positive = ai_codes & hu_codes
        false_positive = ai_codes - hu_codes
        false_negative = hu_codes - ai_codes

        precision = len(true_positive) / len(ai_codes) if ai_codes else 0
        recall = len(true_positive) / len(hu_codes) if hu_codes else 0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

        return {
            'ai_total': len(ai_codes),
            'human_total': len(hu_codes),
            'true_positive': sorted(true_positive),
            'false_positive': sorted(false_positive),
            'false_negative': sorted(false_negative),
            'precision': round(precision * 100, 1),
            'recall': round(recall * 100, 1),
            'f1_score': round(f1 * 100, 1),
        }

    @staticmethod
    def efficiency_comparison(ai_metrics: Dict, human_metrics: Dict) -> Dict:
        """
        比較 AI 與人工的效率
        ai_metrics/human_metrics: 包含 time_seconds, report_pages, error_count
        """
        ai_time = ai_metrics.get('time_seconds', 0)
        hu_time = human_metrics.get('time_seconds', 1)
        speedup = round(hu_time / ai_time, 1) if ai_time > 0 else None

        return {
            'ai_time_seconds': ai_time,
            'human_time_seconds': hu_time,
            'speedup_factor': speedup,
            'time_saved_minutes': round((hu_time - ai_time) / 60, 1),
            'ai_error_count': ai_metrics.get('error_count', 0),
            'human_error_count': human_metrics.get('error_count', 0),
            'cost_reduction_pct': round((1 - ai_metrics.get('cost_per_report', 1) / max(human_metrics.get('cost_per_report', 1), 1)) * 100, 1),
        }
