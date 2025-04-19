from flask import Flask, request, jsonify, send_file
from datetime import datetime
from pytz import timezone
import bleach, os, json

app = Flask(__name__)

# 使用绝对路径以兼容 Vercel Serverless 文件系统
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, '..', 'messages.json')
HTML_FILE = os.path.join(BASE_DIR, '..', 'index.html')

# 确保 messages.json 文件存在
if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, 'w') as f:
        json.dump([], f)

@app.route('/api/telegram', methods=['POST'])
def telegram_webhook():
    data = request.get_json()
    text = data.get('message', {}).get('text', '')
    if text:
        text = bleach.linkify(text)
        timestamp = datetime.now(timezone('America/Chicago')).strftime('%Y-%m-%d %H:%M')
        new_msg = {"text": text, "timestamp": timestamp}

        with open(DATA_FILE, 'r+', encoding='utf-8') as f:
            messages = json.load(f)
            messages.insert(0, new_msg)
            f.seek(0)
            json.dump(messages, f, ensure_ascii=False)
            f.truncate()
    return jsonify({"status": "ok"})


@app.route('/api/export', methods=['GET'])
def export_html():
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        messages = json.load(f)
    html = ""
    for msg in messages:
        html += f'<p>{msg["text"]} <span style="color:gray; font-size:0.9em;">{msg["timestamp"]}</span></p>\n'
    return html


@app.route('/api/index', methods=['GET'])
def index():
    return send_file(HTML_FILE)

# ✅ Vercel 需要的 Serverless 入口函数
def handler(environ, start_response):
    return app.wsgi_app(environ, start_response)
