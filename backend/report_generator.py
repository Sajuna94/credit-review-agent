"""
銀行風險報告生成器
==================
從分析結果生成結構化 HTML 報告
所有數字來自確定性演算法，無 hallucination 風險
"""
from datetime import datetime
from typing import Dict, List
from .financial_ratios import FinancialRatios
from .anomaly_detector import AnomalyDetector


class ReportGenerator:
    """銀行授信覆審報告生成器"""

    @staticmethod
    def generate(parsed: Dict, ratios: Dict, anomalies: Dict) -> str:
        """
        生成完整 HTML 報告
        """
        company = parsed.get('company_name', '未識別')
        period = parsed.get('period', '未識別')
        is_ = parsed.get('income_statement', {})
        bs = parsed.get('balance_sheet', {})
        cf = parsed.get('cash_flow', {})

        # 風險評等
        risk_summary = AnomalyDetector.summarize_risks(
            anomalies.get('yoy_anomalies', []),
            anomalies.get('altman_z', {}),
            anomalies.get('red_flags', []),
        )
        health_score = ratios.get('health_score', 0)
        health_grade = ratios.get('health_grade', '')
        altman = anomalies.get('altman_z', {})

        # 各段落 HTML
        html = f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="UTF-8">
<title>企業授信覆審報告 — {company}</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{
    font-family: 'Microsoft JhengHei', 'PingFang TC', sans-serif;
    margin: 0;
    background: #f4f6f9;
    color: #2c3e50;
    line-height: 1.6;
  }}
  .container {{ max-width: 1100px; margin: 30px auto; padding: 0 20px; }}
  .header {{
    background: linear-gradient(135deg, #1e3a5f 0%, #2c5282 100%);
    color: white;
    padding: 30px 40px;
    border-radius: 8px;
    box-shadow: 0 4px 12px rgba(0,0,0,.1);
    margin-bottom: 24px;
  }}
  .header h1 {{ margin: 0 0 8px 0; font-size: 26px; }}
  .header .meta {{ opacity: 0.85; font-size: 14px; }}
  .grade-badge {{
    display: inline-block;
    padding: 8px 18px;
    border-radius: 20px;
    font-weight: bold;
    margin-top: 12px;
    font-size: 15px;
  }}
  .grade-A {{ background: #10b981; color: white; }}
  .grade-B {{ background: #3b82f6; color: white; }}
  .grade-C {{ background: #f59e0b; color: white; }}
  .grade-D {{ background: #f97316; color: white; }}
  .grade-E {{ background: #ef4444; color: white; }}

  .card {{
    background: white;
    border-radius: 8px;
    padding: 24px 30px;
    margin-bottom: 20px;
    box-shadow: 0 2px 6px rgba(0,0,0,.05);
  }}
  .card h2 {{
    font-size: 18px;
    margin: 0 0 18px 0;
    padding-bottom: 10px;
    border-bottom: 2px solid #e2e8f0;
    color: #1e3a5f;
  }}
  .summary-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 16px;
    margin-bottom: 20px;
  }}
  .stat-box {{
    background: #f8fafc;
    border-left: 4px solid #3b82f6;
    padding: 14px 18px;
    border-radius: 4px;
  }}
  .stat-box .label {{ font-size: 12px; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; }}
  .stat-box .value {{ font-size: 22px; font-weight: bold; color: #1e293b; margin-top: 4px; }}
  .stat-box.warning {{ border-left-color: #f59e0b; }}
  .stat-box.danger {{ border-left-color: #ef4444; }}
  .stat-box.success {{ border-left-color: #10b981; }}

  table {{
    width: 100%;
    border-collapse: collapse;
    margin-top: 10px;
  }}
  th, td {{
    padding: 10px 14px;
    text-align: left;
    border-bottom: 1px solid #e2e8f0;
  }}
  th {{
    background: #f1f5f9;
    font-weight: 600;
    color: #475569;
    font-size: 13px;
  }}
  td {{ font-size: 14px; }}

  .flag-list {{ list-style: none; padding: 0; margin: 0; }}
  .flag-item {{
    padding: 14px 18px;
    margin-bottom: 10px;
    border-radius: 6px;
    border-left: 4px solid;
  }}
  .flag-high {{ background: #fef2f2; border-color: #ef4444; }}
  .flag-medium {{ background: #fffbeb; border-color: #f59e0b; }}
  .flag-low {{ background: #f0fdf4; border-color: #10b981; }}
  .flag-item .title {{ font-weight: bold; margin-bottom: 4px; }}
  .flag-item .desc {{ font-size: 13px; color: #475569; margin-bottom: 4px; }}
  .flag-item .action {{ font-size: 13px; color: #1e40af; font-style: italic; }}

  .altman-bar {{
    background: #e2e8f0;
    height: 28px;
    border-radius: 14px;
    position: relative;
    overflow: hidden;
    margin: 10px 0 20px 0;
  }}
  .altman-bar .zone-safe {{ position: absolute; left: 70%; right: 0; background: #10b981; height: 100%; }}
  .altman-bar .zone-grey {{ position: absolute; left: 43%; right: 30%; background: #f59e0b; height: 100%; }}
  .altman-bar .zone-distress {{ position: absolute; left: 0; right: 57%; background: #ef4444; height: 100%; }}
  .altman-bar .marker {{
    position: absolute;
    top: -4px;
    width: 4px;
    height: 36px;
    background: #1e293b;
    transform: translateX(-50%);
  }}
  .altman-bar .marker-label {{
    position: absolute;
    top: 36px;
    transform: translateX(-50%);
    font-size: 12px;
    font-weight: bold;
    color: #1e293b;
    white-space: nowrap;
  }}

  .opinion {{
    background: #eff6ff;
    border-left: 4px solid #3b82f6;
    padding: 20px 24px;
    border-radius: 4px;
    margin-top: 16px;
  }}
  .opinion h3 {{ margin: 0 0 10px 0; color: #1e40af; }}
  .opinion p {{ margin: 8px 0; }}

  .footer {{
    text-align: center;
    color: #94a3b8;
    font-size: 12px;
    margin: 30px 0;
  }}
  .disclaimer {{
    background: #f8fafc;
    border: 1px dashed #cbd5e1;
    padding: 12px 16px;
    border-radius: 4px;
    font-size: 12px;
    color: #64748b;
    margin-top: 20px;
  }}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>📋 企業授信覆審報告</h1>
    <div class="meta">
      公司名稱：<strong>{company}</strong> ｜
      報告期間：<strong>{period}</strong> ｜
      產出時間：{datetime.now().strftime('%Y-%m-%d %H:%M')}
    </div>
    <div>
      <span class="grade-badge grade-{health_grade[0]}">綜合評等：{health_grade}（健康分數 {health_score}）</span>
    </div>
  </div>

  {ReportGenerator._summary_section(risk_summary, health_score)}
  {ReportGenerator._financial_overview(is_, bs, cf)}
  {ReportGenerator._ratios_section(ratios)}
  {ReportGenerator._altman_section(altman)}
  {ReportGenerator._flags_section(anomalies.get('red_flags', []))}
  {ReportGenerator._opinion_section(company, health_grade, risk_summary, ratios, anomalies)}

  <div class="disclaimer">
    ⚠️ 本報告由 AI 授信分析助手自動產出，所有數據皆來自上傳財報之擷取結果，計算流程採用銀行授信實務公式。
    覆審意見僅供人工決策參考，最終授信決策應由授信審查人員依全盤資訊綜合判斷。
  </div>

  <div class="footer">
    企業授信覆審 AI Agent POC ｜ 銀行風險決策輔助系統
  </div>
</div>
</body>
</html>
"""
        return html

    @staticmethod
    def _summary_section(risk_summary: Dict, health_score: float) -> str:
        risk_class = 'danger' if risk_summary['risk_level'] == 'high' else ('warning' if risk_summary['risk_level'] == 'medium' else 'success')
        return f"""
  <div class="card">
    <h2>一、風險總覽</h2>
    <div class="summary-grid">
      <div class="stat-box {risk_class}">
        <div class="label">整體風險等級</div>
        <div class="value">{risk_summary['risk_label']}</div>
      </div>
      <div class="stat-box">
        <div class="label">健康分數</div>
        <div class="value">{health_score} / 100</div>
      </div>
      <div class="stat-box {'danger' if risk_summary['high_flags'] > 0 else 'success'}">
        <div class="label">高風險紅旗</div>
        <div class="value">{risk_summary['high_flags']} 項</div>
      </div>
      <div class="stat-box {'warning' if risk_summary['medium_flags'] > 0 else 'success'}">
        <div class="label">中度警示</div>
        <div class="value">{risk_summary['medium_flags']} 項</div>
      </div>
    </div>
  </div>
"""

    @staticmethod
    def _financial_overview(is_: Dict, bs: Dict, cf: Dict) -> str:
        def fmt(v, unit='元'):
            if v is None:
                return 'N/A'
            if abs(v) >= 1e8:
                return f"{v/1e8:,.2f} 億{unit}"
            elif abs(v) >= 1e4:
                return f"{v/1e4:,.0f} 萬{unit}"
            else:
                return f"{v:,.0f} {unit}"
        return f"""
  <div class="card">
    <h2>二、財務數據摘要</h2>
    <table>
      <thead>
        <tr><th>項目</th><th>金額</th><th>項目</th><th>金額</th></tr>
      </thead>
      <tbody>
        <tr><td>營業收入</td><td>{fmt(is_.get('revenue'))}</td>
            <td>資產總額</td><td>{fmt(bs.get('total_assets'))}</td></tr>
        <tr><td>營業毛利</td><td>{fmt(is_.get('gross_profit'))}</td>
            <td>流動資產</td><td>{fmt(bs.get('current_assets'))}</td></tr>
        <tr><td>營業利益</td><td>{fmt(is_.get('operating_income'))}</td>
            <td>現金及約當現金</td><td>{fmt(bs.get('cash'))}</td></tr>
        <tr><td>稅後淨利</td><td>{fmt(is_.get('net_income'))}</td>
            <td>負債總額</td><td>{fmt(bs.get('total_liabilities'))}</td></tr>
        <tr><td>利息費用</td><td>{fmt(is_.get('interest_expense'))}</td>
            <td>股東權益</td><td>{fmt(bs.get('equity'))}</td></tr>
        <tr><td>營業現金流</td><td>{fmt(cf.get('operating_cash_flow'))}</td>
            <td>保留盈餘</td><td>{fmt(bs.get('retained_earnings'))}</td></tr>
      </tbody>
    </table>
  </div>
"""

    @staticmethod
    def _ratios_section(ratios: Dict) -> str:
        rows = [
            ('償債能力', None, None),
            ('流動比', ratios.get('current_ratio'), 'ratio'),
            ('速動比', ratios.get('quick_ratio'), 'ratio'),
            ('現金比', ratios.get('cash_ratio'), 'ratio'),
            ('負債比', ratios.get('debt_ratio'), 'pct'),
            ('權益負債比', ratios.get('debt_to_equity'), 'ratio'),
            ('利息保障倍數', ratios.get('interest_coverage'), 'times'),
            ('獲利能力', None, None),
            ('毛利率', ratios.get('gross_margin'), 'pct'),
            ('營業利益率', ratios.get('operating_margin'), 'pct'),
            ('淨利率', ratios.get('net_margin'), 'pct'),
            ('ROE (股東權益報酬率)', ratios.get('roe'), 'pct'),
            ('ROA (總資產報酬率)', ratios.get('roa'), 'pct'),
            ('ROIC (投入資本報酬率)', ratios.get('roic'), 'pct'),
            ('營運效率', None, None),
            ('總資產周轉率', ratios.get('asset_turnover'), 'ratio'),
            ('應收帳款周轉率', ratios.get('receivable_turnover'), 'ratio'),
            ('存貨周轉率', ratios.get('inventory_turnover'), 'ratio'),
        ]

        rows_html = ""
        for name, val, fmt_type in rows:
            if val is None and fmt_type is None:
                rows_html += f'<tr><td colspan="2" style="background:#f1f5f9;font-weight:bold;color:#1e3a5f;">{name}</td></tr>'
            else:
                display = FinancialRatios.format_ratio(val, fmt_type or 'ratio')
                rows_html += f'<tr><td>{name}</td><td style="text-align:right;font-weight:600;">{display}</td></tr>'

        return f"""
  <div class="card">
    <h2>三、關鍵財務比率</h2>
    <table>
      <thead><tr><th>指標</th><th style="text-align:right;">數值</th></tr></thead>
      <tbody>{rows_html}</tbody>
    </table>
  </div>
"""

    @staticmethod
    def _altman_section(altman: Dict) -> str:
        z = altman.get('score')
        if z is None:
            return """
  <div class="card">
    <h2>四、Altman Z 破產風險指數</h2>
    <p style="color:#94a3b8;">資料不足，無法計算（需要保留盈餘、權益市值等完整資訊）</p>
  </div>
"""
        zone = altman.get('zone', '')
        zone_label = altman.get('zone_label', '')
        zone_color = {'safe': '#10b981', 'grey': '#f59e0b', 'distress': '#ef4444'}[zone]
        return f"""
  <div class="card">
    <h2>四、Altman Z 破產風險指數</h2>
    <p>Z 分數：<strong style="font-size:22px;color:{zone_color};">{z}</strong> ｜ 判定區間：<strong>{zone_label}</strong></p>
    <div class="altman-bar">
      <div class="zone-distress"></div>
      <div class="zone-grey"></div>
      <div class="zone-safe"></div>
      <div class="marker" style="left:{min(max(z/5*100, 0), 100)}%;"></div>
      <div class="marker-label" style="left:{min(max(z/5*100, 0), 100)}%;">Z = {z}</div>
    </div>
    <table style="margin-top:30px;">
      <thead><tr><th>組成因子</th><th style="text-align:right;">數值</th></tr></thead>
      <tbody>
        <tr><td>A. 營運資金/總資產</td><td style="text-align:right;">{altman['components']['A_working_capital_ratio']:.4f}</td></tr>
        <tr><td>B. 保留盈餘/總資產</td><td style="text-align:right;">{altman['components']['B_retained_earnings_ratio']:.4f}</td></tr>
        <tr><td>C. EBIT/總資產</td><td style="text-align:right;">{altman['components']['C_ebit_ratio']:.4f}</td></tr>
        <tr><td>D. 權益/負債</td><td style="text-align:right;">{altman['components']['D_equity_to_debt']:.4f}</td></tr>
        <tr><td>E. 銷售額/總資產</td><td style="text-align:right;">{altman['components']['E_asset_turnover']:.4f}</td></tr>
      </tbody>
    </table>
  </div>
"""

    @staticmethod
    def _flags_section(flags: List[Dict]) -> str:
        if not flags:
            return """
  <div class="card">
    <h2>五、紅旗警示</h2>
    <p style="color:#10b981;font-weight:600;">✓ 目前未偵測到重大紅旗，財務狀況相對穩健。</p>
  </div>
"""
        items = ""
        for f in flags:
            level = f.get('level', 'low')
            level_label = {'high': '🔴 高風險', 'medium': '🟡 中度警示', 'low': '🟢 輕微'}[level]
            items += f"""
        <li class="flag-item flag-{level}">
          <div class="title">[{f.get('code', '')}] {f.get('title', '')} — {level_label}</div>
          <div class="desc">{f.get('description', '')}</div>
          <div class="action">💡 建議處置：{f.get('action', '')}</div>
        </li>
"""
        return f"""
  <div class="card">
    <h2>五、紅旗警示</h2>
    <ul class="flag-list">{items}</ul>
  </div>
"""

    @staticmethod
    def _opinion_section(company: str, grade: str, risk: Dict, ratios: Dict, anomalies: Dict) -> str:
        # 用模板組合（避免 LLM 幻覺）
        health_score = ratios.get('health_score', 0)
        cr = ratios.get('current_ratio') or 0
        dr = ratios.get('debt_ratio') or 0
        roe = ratios.get('roe') or 0
        altman_zone = anomalies.get('altman_z', {}).get('zone_label', 'N/A')

        # 評等對應建議
        opinion_map = {
            'A': '授信條件可維持或優化，建議年度覆審。',
            'B': '整體體質尚屬穩健，持續觀察並於下次覆審追蹤關鍵指標。',
            'C': '財務表現中性，建議半年內加強追蹤，必要時要求補充擔保。',
            'D': '財務體質轉弱，建議密切關注並考慮調降授信額度或加強擔保。',
            'E': '財務狀況堪慮，建議啟動預警機制，評估是否提前收回或要求還款計畫。',
        }
        grade_key = grade[0] if grade else 'C'
        base_opinion = opinion_map.get(grade_key, opinion_map['C'])

        # 補上具體數字佐證
        specific = []
        if cr < 1.0:
            specific.append(f'流動比 {cr:.2f} 偏低，短期償債壓力值得關注')
        if dr > 0.70:
            specific.append(f'負債比 {dr*100:.1f}% 偏高，財務槓桿風險提升')
        if roe < 0.05:
            specific.append(f'ROE {roe*100:.2f}% 偏弱，獲利能力需改善')

        specific_text = ('具體警訊：' + '；'.join(specific) + '。') if specific else '未發現結構性警訊。'

        return f"""
  <div class="card">
    <h2>六、覆審意見摘要</h2>
    <div class="opinion">
      <h3>📊 綜合評等：{grade}</h3>
      <p><strong>{company}</strong> 經本系統分析，綜合健康分數為 <strong>{health_score}/100</strong>，
      整體風險等級為 <strong>{risk['risk_label']}</strong>，Altman Z 分數判定為 <strong>{altman_zone}</strong>。</p>
      <p><strong>覆審建議：</strong>{base_opinion}</p>
      <p><strong>數據佐證：</strong>{specific_text}</p>
      <p style="color:#64748b;font-size:13px;margin-top:14px;">
        ⓘ 本意見由 AI 根據財務指標自動生成，所有結論均對應到具體財務數值，無 LLM 推論成分，可作為覆審決策的量化參考依據。
      </p>
    </div>
  </div>
"""
