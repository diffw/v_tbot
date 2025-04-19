from flask import Flask, request, jsonify, send_from_directory
from datetime import datetime
from pytz import timezone
import bleach, os, json

app = Flask(__name__)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, '../messages.json')

# 确保文件存在
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
    return send_from_directory(directory=os.path.join(BASE_DIR, '..'), path='index.html')

# WSGI entry point for Vercel
def handler(environ, start_response):
    return app.wsgi_app(environ, start_response)
