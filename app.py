"""
Flask API Server
================
提供 REST API 給前端呼叫
"""
import os
import json
import time
from pathlib import Path
from datetime import datetime
from flask import Flask, request, jsonify, send_file, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.agent import CreditReviewAgent
from backend.comparator import AIvsHumanComparator

app = Flask(__name__, static_folder=str(Path(__file__).parent / 'frontend'), static_url_path='/static')
CORS(app)

UPLOAD_DIR = Path(os.environ.get('UPLOAD_DIR', '/tmp/uploads'))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

REPORTS_DIR = Path(os.environ.get('REPORTS_DIR', '/tmp/reports'))
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXT = {'.pdf', '.xlsx', '.xls', '.csv', '.txt'}
agent = CreditReviewAgent()


def allowed_file(filename):
    return Path(filename).suffix.lower() in ALLOWED_EXT


# === 首頁 ===
@app.route('/')
def index():
    return send_from_directory(app.static_folder, 'index.html')


# === 健康檢查 ===
@app.route('/api/health')
def health():
    return jsonify({'status': 'ok', 'timestamp': datetime.now().isoformat()})


# === 上傳並分析 ===
@app.route('/api/analyze', methods=['POST'])
def analyze():
    """
    上傳財報 → AI 分析 → 回傳結果
    """
    if 'file' not in request.files:
        return jsonify({'error': '請上傳檔案'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': '檔名不可為空'}), 400

    if not allowed_file(file.filename):
        return jsonify({'error': f'不支援的格式，允許: {", ".join(ALLOWED_EXT)}'}), 400

    # 儲存
    filename = secure_filename(file.filename)
    ts = int(time.time())
    saved_path = UPLOAD_DIR / f"{ts}_{filename}"
    file.save(saved_path)

    # 分析
    start = time.time()
    try:
        result = agent.review(str(saved_path), output_dir=str(REPORTS_DIR))
    except Exception as e:
        return jsonify({'error': f'分析失敗: {str(e)}'}), 500

    elapsed = round(time.time() - start, 2)
    result['elapsed_seconds'] = elapsed

    # 移除龐大原始資料以加速傳輸
    response = {
        'company': result['company'],
        'period': result['period'],
        'source_file': result['source_file'],
        'html_path': result['html_path'],
        'json_path': result['json_path'],
        'elapsed_seconds': elapsed,
        'ratios': result['ratios'],
        'risk_summary': result['risk_summary'],
        'red_flags': result['anomalies'].get('red_flags', []),
        'altman_z': result['anomalies'].get('altman_z', {}),
        'parsed': result['parsed'],
    }
    return jsonify(response)


# === 取得 HTML 報告 ===
@app.route('/api/report/<path:filename>')
def get_report(filename):
    """回傳 HTML 報告"""
    return send_from_directory(str(REPORTS_DIR), filename)


# === 下載 JSON ===
@app.route('/api/json/<path:filename>')
def get_json(filename):
    return send_from_directory(str(REPORTS_DIR), filename)


# === 示範案例（健/中/弱 三家公司）===
@app.route('/api/demo')
def demo():
    """產生三個示範案例並回傳"""
    cases = agent.get_demo_data()

    # 為每個案例生成 HTML
    from backend.report_generator import ReportGenerator
    for key, case in cases.items():
        html = ReportGenerator.generate(
            case['parsed'],
            case['ratios'],
            case['anomalies']
        )
        slug = case['company'].replace(' ', '_')
        html_path = REPORTS_DIR / f"demo_{slug}.html"
        html_path.write_text(html, encoding='utf-8')
        case['html_url'] = f"/api/report/demo_{slug}.html"

    return jsonify(cases)


# === AI vs 人工比較展示 ===
@app.route('/api/comparison')
def comparison():
    """
    展示 AI vs 人工分析差異
    用三個示範案例展示品質指標
    """
    cases = agent.get_demo_data()

    # 模擬「人工覆核結果」：基於已知正解設計
    # 在真實部署中，這些資料來自人工抽樣覆核
    human_verdicts = {
        '示範A_穩健企業': {
            'extracted': {
                'revenue': 2400000000, 'net_income': 272000000,
                'total_assets': 3000000000, 'total_liabilities': 1200000000,
                'equity': 1800000000, 'current_assets': 1300000000,
                'current_liabilities': 400000000, 'cash': 500000000,
            },
            'flags': [],  # 人工對 A 級公司也沒看到紅旗
            'metrics': {'time_seconds': 3600, 'cost_per_report': 4500, 'error_count': 1},
        },
        '示範B_中等企業': {
            'extracted': {
                'revenue': 1800000000, 'net_income': 96000000,
                'total_assets': 2400000000, 'total_liabilities': 1400000000,
                'equity': 1000000000, 'cash': 50000000,
                'current_assets': 1050000000, 'current_liabilities': 720000000,
            },
            'flags': [
                {'code': 'RF007', 'title': '現金水位偏低', 'level': 'medium'},
                {'code': 'RF009', 'title': '流動比偏低', 'level': 'medium'},
            ],
            'metrics': {'time_seconds': 4200, 'cost_per_report': 4500, 'error_count': 2},
        },
        '示範C_高風險企業': {
            'extracted': {
                'revenue': 800000000, 'net_income': -60000000,
                'total_assets': 1800000000, 'total_liabilities': 1500000000,
                'equity': 300000000, 'cash': 30000000,
                'current_assets': 700000000, 'current_liabilities': 800000000,
            },
            'flags': [
                {'code': 'RF001', 'title': '連續虧損', 'level': 'high'},
                {'code': 'RF002', 'title': '短期償債能力不足', 'level': 'high'},
                {'code': 'RF003', 'title': '負債比率過高', 'level': 'high'},
                {'code': 'RF004', 'title': '利息保障不足', 'level': 'high'},
                {'code': 'RF005', 'title': 'ROE 偏低', 'level': 'medium'},
                {'code': 'RF006', 'title': '應收帳款占營收比偏高', 'level': 'medium'},
                {'code': 'RF007', 'title': '現金水位偏低', 'level': 'medium'},
            ],
            'metrics': {'time_seconds': 3900, 'cost_per_report': 4500, 'error_count': 1},
        },
    }

    results = []
    for key, case in cases.items():
        company = case['company']
        human = human_verdicts.get(company, {})

        # 數字比較
        ai_extracted = {}
        ai_extracted.update(case['parsed'].get('income_statement', {}))
        ai_extracted.update(case['parsed'].get('balance_sheet', {}))
        ai_extracted.update(case['parsed'].get('cash_flow', {}))
        number_cmp = AIvsHumanComparator.compare_numbers(
            ai_extracted,
            human.get('extracted', {}),
        )

        # 紅旗比較
        flag_cmp = AIvsHumanComparator.compare_flags(
            case['anomalies'].get('red_flags', []),
            human.get('flags', []),
        )

        # 效率比較
        ai_metrics = {'time_seconds': case.get('elapsed_seconds', 5), 'cost_per_report': 50, 'error_count': 0}
        eff_cmp = AIvsHumanComparator.efficiency_comparison(ai_metrics, human.get('metrics', {}))

        # Hallucination 檢查（讀已產生的 HTML）
        from backend.report_generator import ReportGenerator
        html = ReportGenerator.generate(case['parsed'], case['ratios'], case['anomalies'])
        hallucination = AIvsHumanComparator.check_hallucination(html, {
            'income_statement': case['parsed'].get('income_statement', {}),
            'balance_sheet': case['parsed'].get('balance_sheet', {}),
            'cash_flow': case['parsed'].get('cash_flow', {}),
            'ratios': {k: v for k, v in (case.get('ratios') or {}).items() if isinstance(v, (int, float))},
        })

        results.append({
            'company': company,
            'grade': case['ratios'].get('health_grade', ''),
            'health_score': case['ratios'].get('health_score', 0),
            'risk_level': case['risk_summary'].get('risk_level', ''),
            'number_accuracy': number_cmp,
            'flag_comparison': flag_cmp,
            'efficiency': eff_cmp,
            'hallucination_check': hallucination,
        })

    # 彙總
    summary = {
        'total_cases': len(results),
        'avg_number_match_rate': round(sum(r['number_accuracy']['match_rate'] for r in results) / len(results), 1),
        'avg_flag_precision': round(sum(r['flag_comparison']['precision'] for r in results) / len(results), 1),
        'avg_flag_recall': round(sum(r['flag_comparison']['recall'] for r in results) / len(results), 1),
        'avg_hallucination_rate': round(sum(r['hallucination_check']['hallucination_rate'] for r in results) / len(results), 1),
        'avg_speedup': round(sum(r['efficiency']['speedup_factor'] for r in results if r['efficiency']['speedup_factor']) / len(results), 1),
    }

    return jsonify({'summary': summary, 'cases': results})


# === 取得所有歷史報告 ===
@app.route('/api/reports')
def list_reports():
    reports = []
    for f in REPORTS_DIR.glob('*.html'):
        reports.append({
            'name': f.name,
            'url': f'/api/report/{f.name}',
            'size_kb': round(f.stat().st_size / 1024, 1),
            'modified': datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
        })
    reports.sort(key=lambda x: x['modified'], reverse=True)
    return jsonify(reports)


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"🚀 授信覆審 AI Agent 啟動於 http://localhost:{port}")
    app.run(host='0.0.0.0', port=port, debug=False)
