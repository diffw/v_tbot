from flask import Flask, request, jsonify, send_file
from datetime import datetime
from pytz import timezone
import bleach, os, json, sys, traceback
import redis
from urllib.parse import urlparse
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

def get_redis_client():
    try:
        # 获取 Vercel KV 环境变量
        kv_url = os.getenv('KV_REST_API_URL')
        kv_token = os.getenv('KV_REST_API_TOKEN')
        kv_timeout = os.getenv('KV_REST_API_TIMEOUT', '3000')
        
        logger.info("Checking KV environment variables...")
        logger.info(f"KV_REST_API_URL exists: {'yes' if kv_url else 'no'}")
        logger.info(f"KV_REST_API_TOKEN exists: {'yes' if kv_token else 'no'}")
        
        if not (kv_url and kv_token):
            logger.error("Missing required KV environment variables")
            return None
            
        # 解析 URL
        parsed = urlparse(kv_url)
        logger.info(f"Parsed URL - scheme: {parsed.scheme}, host: {parsed.hostname}")
        
        # 创建 Redis 客户端
        client = redis.Redis(
            host=parsed.hostname,
            port=parsed.port or 6379,
            username=parsed.username,
            password=kv_token,  # 使用 token 作为密码
            ssl=True,
            ssl_cert_reqs=None,  # 禁用证书验证
            decode_responses=True,
            socket_timeout=float(kv_timeout) / 1000,
            socket_connect_timeout=float(kv_timeout) / 1000
        )
        
        # 测试连接
        client.ping()
        logger.info("Successfully connected to Vercel KV")
        return client
    except Exception as e:
        logger.error(f"Failed to connect to Vercel KV: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return None

redis_client = get_redis_client()

def get_messages():
    try:
        if not redis_client:
            logger.error("Redis client not available")
            return []
        messages = redis_client.lrange('messages', 0, -1)
        logger.info(f"Retrieved {len(messages)} messages from Redis")
        return [json.loads(m) for m in messages] if messages else []
    except Exception as e:
        logger.error(f"Error getting messages: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return []

def save_message(message):
    try:
        if not redis_client:
            logger.error("Redis client not available")
            return False
        redis_client.lpush('messages', json.dumps(message))
        redis_client.ltrim('messages', 0, 99)  # 只保留最新的100条消息
        logger.info("Message saved successfully")
        return True
    except Exception as e:
        logger.error(f"Error saving message: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return False

@app.route('/telegram', methods=['POST'])
def telegram_webhook():
    try:
        data = request.get_json()
        logger.info(f"Received webhook data: {json.dumps(data)}")
        
        text = data.get('message', {}).get('text', '')
        chat_id = data.get('message', {}).get('chat', {}).get('id')
        logger.info(f"Extracted text: {text}, chat_id: {chat_id}")
        
        if text:
            text = bleach.linkify(text)
            timestamp = datetime.now(timezone('America/Chicago')).strftime('%Y-%m-%d %H:%M')
            new_msg = {
                "text": text,
                "timestamp": timestamp,
                "chat_id": chat_id
            }
            if save_message(new_msg):
                logger.info(f"Successfully saved message: {json.dumps(new_msg)}")
            else:
                logger.error("Failed to save message")
        return jsonify({"status": "ok"})
    except Exception as e:
        error_msg = f"Error in webhook: {str(e)}\nTraceback: {traceback.format_exc()}"
        logger.error(error_msg)
        return jsonify({"error": error_msg}), 500

@app.route('/export', methods=['GET'])
def export_html():
    try:
        messages = get_messages()
        logger.info(f"Retrieved {len(messages)} messages")
        if not messages:
            return '<div class="message">No messages yet</div>'
        html = ""
        for msg in messages:
            html += f'<div class="message"><p>{msg["text"]}</p><div class="timestamp">{msg["timestamp"]}</div></div>\n'
        return html
    except Exception as e:
        error_msg = f"Error in export: {str(e)}\nTraceback: {traceback.format_exc()}"
        logger.error(error_msg)
        return error_msg, 500

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
                #error {
                    color: #ff4444;
                    text-align: center;
                    margin-top: 20px;
                    display: none;
                }
            </style>
        </head>
        <body>
            <h1>Messages</h1>
            <div id="messages"></div>
            <div id="status">Loading messages...</div>
            <div id="error"></div>
            <script>
                function loadMessages() {
                    fetch('/export')
                        .then(response => {
                            if (!response.ok) {
                                throw new Error(`HTTP error! status: ${response.status}`);
                            }
                            return response.text();
                        })
                        .then(html => {
                            document.getElementById('messages').innerHTML = html;
                            const status = document.getElementById('status');
                            const error = document.getElementById('error');
                            if (html.trim() === '') {
                                status.textContent = 'No messages yet';
                                status.style.display = 'block';
                            } else {
                                status.style.display = 'none';
                            }
                            error.style.display = 'none';
                        })
                        .catch(error => {
                            console.error('Error loading messages:', error);
                            document.getElementById('error').textContent = 'Error loading messages: ' + error.message;
                            document.getElementById('error').style.display = 'block';
                            document.getElementById('status').style.display = 'none';
                        });
                }
                loadMessages();
                setInterval(loadMessages, 30000);
            </script>
        </body>
        </html>
        """
    except Exception as e:
        error_msg = f"Error in index: {str(e)}\nTraceback: {traceback.format_exc()}"
        logger.error(error_msg)
        return error_msg, 500

@app.route('/debug', methods=['GET'])
def debug():
    """Debug endpoint to check environment and configuration"""
    try:
        # 获取环境变量（排除敏感信息）
        env_vars = {}
        for k, v in os.environ.items():
            if any(s in k.lower() for s in ['key', 'secret', 'password', 'token', 'url']):
                env_vars[k] = '***'
            else:
                env_vars[k] = v
        
        # 测试 Redis 连接
        redis_status = False
        redis_error = None
        if redis_client:
            try:
                redis_client.ping()
                redis_status = True
            except Exception as e:
                redis_error = str(e)
        
        # 获取 Redis 信息
        redis_info = None
        if redis_status:
            try:
                info = redis_client.info()
                redis_info = {
                    'version': info.get('redis_version'),
                    'connected_clients': info.get('connected_clients'),
                    'used_memory_human': info.get('used_memory_human')
                }
            except:
                redis_info = "Failed to get Redis info"
        
        info = {
            'env_vars': env_vars,
            'redis_connected': redis_status,
            'redis_error': redis_error,
            'redis_info': redis_info,
            'python_version': sys.version,
            'message_count': len(get_messages()) if redis_status else None
        }
        logger.info(f"Debug info: {json.dumps(info, indent=2)}")
        return jsonify(info)
    except Exception as e:
        error_info = {'error': str(e), 'traceback': traceback.format_exc()}
        logger.error(f"Debug endpoint error: {json.dumps(error_info, indent=2)}")
        return jsonify(error_info), 500

def handler(environ, start_response):
    return app.wsgi_app(environ, start_response)
