import os
import sys
from flask import Flask, request, abort

# LINE Bot SDK v3 のインポート
# WebhookHandler は linebot.v3.webhook からで正しい
from linebot.v3.webhook import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
)
from linebot.v3.webhooks import (
    MessageEvent, # WebhookMessageEvent から MessageEvent に修正
    TextMessageContent, # WebhookTextMessageContent は TextMessageContent のままで正しい
    PostbackEvent, # WebhookPostbackEvent から PostbackEvent に修正
    FollowEvent, # WebhookFollowEvent から FollowEvent に修正
    UnfollowEvent, # WebhookUnfollowEvent から UnfollowEvent に修正
    JoinEvent, # WebhookJoinEvent から JoinEvent に修正
    LeaveEvent, # WebhookLeaveEvent から LeaveEvent に修正
    MemberJoinedEvent, # WebhookMemberJoinedEvent から MemberJoinedEvent に修正
    MemberLeftEvent, # WebhookMemberLeftEvent から MemberLeftEvent に修正
    BeaconEvent, # WebhookBeaconEvent から BeaconEvent に修正
    AccountLinkEvent, # WebhookAccountLinkEvent から AccountLinkEvent に修正
    ThingsEvent # WebhookThingsEvent から ThingsEvent に修正
)

# config.py から設定をインポート
from config import (
    LINE_CHANNEL_ACCESS_TOKEN,
    LINE_CHANNEL_SECRET,
    Config # Configクラスをインポート
)

# 各ハンドラをインポート
# これらのハンドラは event_callbacks.py に定義されており、
# event_callbacks.py 内で MessageEvent など正しい v3 クラス名を使用していることを前提とする
from line_handlers.event_callbacks import (
    handle_message_event,
    handle_postback_event,
    handle_follow_event,
    handle_unfollow_event,
    handle_join_event,
    handle_leave_event,
    handle_member_joined_event,
    handle_member_left_event,
    handle_beacon_event,
    handle_account_link_event,
    handle_things_event
)

print("LINE SDK modules imported.")
print("Google Sheets modules will be imported by respective handlers.")

try:
    # Flaskアプリの初期化
    app = Flask(__name__)

    # LINE Bot SDK v3 Configuration and WebhookHandler initialized.
    configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
    api_client = ApiClient(configuration)
    line_bot_api_messaging = MessagingApi(api_client) # MessagingApiクライアントを初期化
    handler = WebhookHandler(LINE_CHANNEL_SECRET)
    print("LINE Bot SDK Configuration and WebhookHandler initialized.")

except Exception as e:
    print(f"Error loading config.py or initializing LINE Bot SDK: {e}")
    print("Please ensure LINE_CHANNEL_ACCESS_TOKEN and LINE_CHANNEL_SECRET are correctly set as environment variables in Replit.")
    sys.exit(1)

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    app.logger.info("Request body: %s", body)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        print("Invalid signature. Please check your channel access token/channel secret.")
        abort(400)
    except Exception as e:
        print(f"Error handling webhook: {e}")
        abort(500)
    return 'OK'

# @handler.add デコレータの引数も修正されたクラス名に合わせる
@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    # テキストメッセージはhandle_message_eventに任せる
    handle_message_event(event) # event_callbacks.py の handle_message_event が MessagingApi を受け取らないため引数を修正

# TextMessageContent以外のMessageEventはhandle_message_event内で処理されるべきであるため、
# 以下のハンドラは不要。handle_message_eventがイベントタイプを適切に判別する前提。
# @handler.add(MessageEvent) # こちらも MessageEvent に修正
# def handle_other_message_types(event):
#     if not isinstance(event.message, TextMessageContent): # こちらも TextMessageContent のままで正しい
#         handle_message_event(event) # MessagingApi を渡さない

@handler.add(PostbackEvent)
def handle_postback(event):
    handle_postback_event(event) # MessagingApi を渡さない

@handler.add(FollowEvent)
def handle_follow(event):
    handle_follow_event(event) # MessagingApi を渡さない

@handler.add(UnfollowEvent)
def handle_unfollow(event):
    handle_unfollow_event(event) # MessagingApi を渡さない

@handler.add(JoinEvent)
def handle_join(event):
    handle_join_event(event) # MessagingApi を渡さない

@handler.add(LeaveEvent)
def handle_leave(event):
    handle_leave_event(event) # MessagingApi を渡さない

@handler.add(MemberJoinedEvent)
def handle_member_joined(event):
    handle_member_joined_event(event) # MessagingApi を渡さない

@handler.add(MemberLeftEvent)
def handle_member_left(event):
    handle_member_left_event(event) # MessagingApi を渡さない

@handler.add(BeaconEvent)
def handle_beacon(event):
    handle_beacon_event(event) # MessagingApi を渡さない

@handler.add(AccountLinkEvent)
def handle_account_link(event):
    handle_account_link_event(event) # MessagingApi を渡さない

@handler.add(ThingsEvent)
def handle_things(event):
    handle_things_event(event) # MessagingApi を渡さない


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

