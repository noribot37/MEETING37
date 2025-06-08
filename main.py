import os
import sys
from flask import Flask, request, abort
from linebot.v3 import WebhookHandler
from linebot.v3.messaging import Configuration, ApiClient, MessagingApi
# Profileクラスのインポートは不要なため削除 (エラー回避のため)
from linebot.v3.webhooks import MessageEvent, TextMessageContent

from line_handlers.message_processors import process_message

app = Flask(__name__)

CHANNEL_ACCESS_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
CHANNEL_SECRET = os.getenv('LINE_CHANNEL_SECRET')

if CHANNEL_ACCESS_TOKEN is None:
    print('Specify LINE_CHANNEL_ACCESS_TOKEN as environment variable.')
    sys.exit(1)
if CHANNEL_SECRET is None:
    print('Specify LINE_CHANNEL_SECRET as environment variable.')
    sys.exit(1)

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
def handle_message(event: MessageEvent):
    with ApiClient(configuration) as api_client:
        line_bot_api_messaging = MessagingApi(api_client)

        user_id = event.source.user_id
        message_text = event.message.text
        reply_token = event.reply_token
        user_display_name = "名無し" # デフォルト値

        # ユーザーのプロフィール情報を取得
        try:
            profile_obj = line_bot_api_messaging.get_profile(user_id)
            user_display_name = profile_obj.display_name
            app.logger.info(f"DEBUG: Fetched profile for {user_id}: {user_display_name}")
        except Exception as e:
            app.logger.warning(f"WARNING: Could not get profile for user {user_id}: {e}")
            # プロフィールが取得できない場合も処理を継続

        process_message(user_id, message_text, reply_token, user_display_name, line_bot_api_messaging)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
