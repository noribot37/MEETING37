import os
from flask import Flask, request, abort
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import Configuration, ApiClient, MessagingApi
from linebot.v3.webhooks import MessageEvent, TextMessageContent # ★追加

from config import Config
from line_handlers.message_processors import process_message

# Flaskアプリケーションの初期化
app = Flask(__name__)

# LINE Bot SDKの設定
configuration = Configuration(access_token=Config.LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(Config.LINE_CHANNEL_SECRET)

# MessagingApiの初期化 (必要に応じて他の場所でもインスタンス化される可能性があるが、ここで定義)
line_bot_api_messaging = MessagingApi(ApiClient(configuration))

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    app.logger.info("Request body: %s", body)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        app.logger.error("Invalid signature. Please check your channel access token/channel secret.")
        abort(400)
    except Exception as e:
        app.logger.error(f"Error: {e}", exc_info=True)
        abort(500)

    return 'OK'

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    """
    メッセージイベントを処理するハンドラー
    """
    try:
        # process_message 関数に event オブジェクト全体を渡す
        process_message(event)
    except Exception as e:
        app.logger.error(f"Error in main: {e}", exc_info=True)
        # エラー発生時もLINEに500応答を返す
        abort(500)

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    app.run(host="0.0.0.0", port=port)