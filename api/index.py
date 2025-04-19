from flask import Flask, request, jsonify, send_file
from datetime import datetime
from pytz import timezone
import bleach, os, json
import redis
from urllib.parse import urlparse

app = Flask(__name__)

# 配置 Redis 连接
redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
url = urlparse(redis_url)
redis_client = redis.Redis(
    host=url.hostname,
    port=url.port,
    password=url.password,
    ssl=True if url.scheme == 'rediss' else False
)

def get_messages():
    try:
        messages = redis_client.lrange('messages', 0, -1)
        return [json.loads(m.decode('utf-8')) for m in messages]
    except Exception as e:
        print(f"Error getting messages: {str(e)}")
        return []

def save_message(message):
    try:
        redis_client.lpush('messages', json.dumps(message))
        redis_client.ltrim('messages', 0, 99)  # 只保留最新的100条消息
    except Exception as e:
        print(f"Error saving message: {str(e)}")

@app.route('/telegram', methods=['POST'])
def telegram_webhook():
    try:
        data = request.get_json()
        print(f"Received webhook data: {json.dumps(data)}")  # 调试日志
        
        text = data.get('message', {}).get('text', '')
        if text:
            text = bleach.linkify(text)
            timestamp = datetime.now(timezone('America/Chicago')).strftime('%Y-%m-%d %H:%M')
            new_msg = {"text": text, "timestamp": timestamp}
            save_message(new_msg)
            print(f"Saved message: {json.dumps(new_msg)}")  # 调试日志
        return jsonify({"status": "ok"})
    except Exception as e:
        print(f"Error in webhook: {str(e)}")  # 调试日志
        return jsonify({"error": str(e)}), 500

@app.route('/export', methods=['GET'])
def export_html():
    try:
        messages = get_messages()
        print(f"Retrieved {len(messages)} messages")  # 调试日志
        html = ""
        for msg in messages:
            html += f'<p>{msg["text"]} <span style="color:gray; font-size:0.9em;">{msg["timestamp"]}</span></p>\n'
        return html
    except Exception as e:
        print(f"Error in export: {str(e)}")  # 调试日志
        return str(e), 500

@app.route('/', methods=['GET'])
def index():
    try:
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Messages</title>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <style>
                body { 
                    font-family: Arial, sans-serif; 
                    max-width: 800px; 
                    margin: 0 auto; 
                    padding: 20px;
                    background-color: #f5f5f5;
                }
                .message {
                    background: white;
                    border-radius: 8px;
                    padding: 15px;
                    margin-bottom: 15px;
                    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
                }
                .timestamp {
                    color: #666;
                    font-size: 0.9em;
                    margin-top: 5px;
                }
                h1 {
                    color: #333;
                    text-align: center;
                    margin-bottom: 30px;
                }
                #status {
                    text-align: center;
                    color: #666;
                    margin-top: 20px;
                    font-style: italic;
                }
            </style>
        </head>
        <body>
            <h1>Messages</h1>
            <div id="messages"></div>
            <div id="status">Loading messages...</div>
            <script>
                function loadMessages() {
                    fetch('/export')
                        .then(response => response.text())
                        .then(html => {
                            document.getElementById('messages').innerHTML = html;
                            const status = document.getElementById('status');
                            if (html.trim() === '') {
                                status.textContent = 'No messages yet';
                            } else {
                                status.style.display = 'none';
                            }
                        })
                        .catch(error => {
                            console.error('Error loading messages:', error);
                            document.getElementById('status').textContent = 'Error loading messages';
                        });
                }
                loadMessages();
                setInterval(loadMessages, 30000);
            </script>
        </body>
        </html>
        """
    except Exception as e:
        print(f"Error in index: {str(e)}")  # 调试日志
        return str(e), 500

def handler(environ, start_response):
    return app.wsgi_app(environ, start_response)
