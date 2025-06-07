# main.py

import os
import sys
from flask import Flask, request, abort
from linebot.v3 import WebhookHandler
from linebot.v3.messaging import Configuration, ApiClient, MessagingApi
from linebot.v3.webhooks import MessageEvent, TextMessageContent

# sys.path.append(os.path.join(os.path.dirname(__file__), 'line_handlers'))

from line_handlers.message_processors import process_message # 修正: process_message をインポート

app = Flask(__name__)

# 環境変数からLINE Developersの情報を取得
CHANNEL_ACCESS_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
CHANNEL_SECRET = os.getenv('LINE_CHANNEL_SECRET')

if CHANNEL_ACCESS_TOKEN is None:
    print('Specify LINE_CHANNEL_ACCESS_TOKEN as environment variable.')
    sys.exit(1)
if CHANNEL_SECRET is None:
    print('Specify LINE_CHANNEL_SECRET as environment variable.')
    sys.exit(1)

# LINE Bot SDKの設定
configuration = Configuration(access_token=CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    app.logger.info("Request body: %s", body)

    try:
        handler.handle(body, signature)
    except Exception as e:
        app.logger.error("Error: %s", e)
        abort(500)
    return 'OK'

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event: MessageEvent): # eventの型ヒントを追加
    with ApiClient(configuration) as api_client:
        line_bot_api_messaging = MessagingApi(api_client)

        # ここを修正: eventオブジェクトから必要な情報を抽出して渡す
        user_id = event.source.user_id
        message_text = event.message.text
        reply_token = event.reply_token
        
        process_message(user_id, message_text, reply_token, line_bot_api_messaging)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))