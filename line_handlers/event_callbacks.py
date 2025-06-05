import os
import sys
# LINE Bot SDK v3 のインポートに統一
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage, # v3 の TextMessage を使用
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
from linebot.exceptions import InvalidSignatureError

from line_handlers.message_processors import process_message # process_message をインポート

# main.py から config.py を参照するためのパス設定
# このファイル (event_callbacks.py) が line_handlers ディレクトリにある場合
# config.py は一つ上の階層にあると想定
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

# 修正箇所: Config クラスではなく、グローバル変数 LINE_CHANNEL_ACCESS_TOKEN を直接インポート
from config import LINE_CHANNEL_ACCESS_TOKEN 

# LINE Bot API の設定
# 修正箇所: Config.LINE_CHANNEL_ACCESS_TOKEN ではなく、直接インポートした LINE_CHANNEL_ACCESS_TOKEN を使用
configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)

# MessagingApiClient を初期化
messaging_api_client = ApiClient(configuration)
line_bot_api_messaging = MessagingApi(messaging_api_client)

def handle_message_event(event: MessageEvent): # 型ヒントを MessageEvent に修正
    """
    LINEからのメッセージイベントを処理する。
    """
    # MessagingApi クライアントは process_message 内で MessagingApi(ApiClient(configuration)) として
    # ローカルで初期化されるか、または main.py から渡されるべき。
    # event_callbacks.py の handle_message_event が MessagingApi オブジェクトを
    # 引数として受け取るように変更されたため、ここで渡す。
    if isinstance(event, MessageEvent) and isinstance(event.message, TextMessageContent):
        # process_message 関数に処理を委譲
        process_message(event, line_bot_api_messaging) # line_bot_api_messaging を引数として渡す
    else:
        print(f"DEBUG: Unknown event type or message type: {event}")

def handle_postback_event(event: PostbackEvent, line_bot_api_messaging: MessagingApi): # 型ヒントを PostbackEvent に修正
    print(f"DEBUG: Postback event received: {event}")
    user_id = event.source.user_id
    reply_token = event.reply_token
    messages = [TextMessage(text=f"ポストバックデータ: {event.postback.data}")]
    line_bot_api_messaging.reply_message(
        ReplyMessageRequest(
            reply_token=reply_token,
            messages=messages
        )
    )

def handle_follow_event(event: FollowEvent, line_bot_api_messaging: MessagingApi): # 型ヒントを FollowEvent に修正
    print(f"DEBUG: Follow event received: {event}")
    user_id = event.source.user_id
    reply_token = event.reply_token
    messages = [TextMessage(text="友だち追加ありがとうございます！")]
    line_bot_api_messaging.reply_message(
        ReplyMessageRequest(
            reply_token=reply_token,
            messages=messages
        )
    )

def handle_unfollow_event(event: UnfollowEvent, line_bot_api_messaging: MessagingApi): # 型ヒントを UnfollowEvent に修正
    print(f"DEBUG: Unfollow event received: {event}")
    # 友だち解除イベントでは返信できない
    pass

def handle_join_event(event: JoinEvent, line_bot_api_messaging: MessagingApi): # 型ヒントを JoinEvent に修正
    print(f"DEBUG: Join event received: {event}")
    user_id = event.source.group_id if event.source.type == 'group' else event.source.room_id
    reply_token = event.reply_token
    messages = [TextMessage(text="グループに参加しました！")]
    line_bot_api_messaging.reply_message(
        ReplyMessageRequest(
            reply_token=reply_token,
            messages=messages
        )
    )

def handle_leave_event(event: LeaveEvent, line_bot_api_messaging: MessagingApi): # 型ヒントを LeaveEvent に修正
    print(f"DEBUG: Leave event received: {event}")
    # グループ退室イベントでは返信できない
    pass

def handle_member_joined_event(event: MemberJoinedEvent, line_bot_api_messaging: MessagingApi): # 型ヒントを MemberJoinedEvent に修正
    print(f"DEBUG: Member joined event received: {event}")
    reply_token = event.reply_token
    messages = [TextMessage(text="新しいメンバーが参加しました！")]
    line_bot_api_messaging.reply_message(
        ReplyMessageRequest(
            reply_token=reply_token,
            messages=messages
        )
    )

def handle_member_left_event(event: MemberLeftEvent, line_bot_api_messaging: MessagingApi): # 型ヒントを MemberLeftEvent に修正
    print(f"DEBUG: Member left event received: {event}")
    # メンバー退出イベントでは返信できない
    pass

def handle_beacon_event(event: BeaconEvent, line_bot_api_messaging: MessagingApi): # 型ヒントを BeaconEvent に修正
    print(f"DEBUG: Beacon event received: {event}")
    user_id = event.source.user_id
    reply_token = event.reply_token
    messages = [TextMessage(text=f"ビーコンイベント: {event.beacon.hwid} - {event.beacon.type}")]
    line_bot_api_messaging.reply_message(
        ReplyMessageRequest(
            reply_token=reply_token,
            messages=messages
        )
    )

def handle_account_link_event(event: AccountLinkEvent, line_bot_api_messaging: MessagingApi): # 型ヒントを AccountLinkEvent に修正
    print(f"DEBUG: Account link event received: {event}")
    user_id = event.source.user_id
    reply_token = event.reply_token
    messages = [TextMessage(text=f"アカウント連携イベント: {event.link.result}")]
    line_bot_api_messaging.reply_message(
        ReplyMessageRequest(
            reply_token=reply_token,
            messages=messages
        )
    )

def handle_things_event(event: ThingsEvent, line_bot_api_messaging: MessagingApi): # 型ヒントを ThingsEvent に修正
    print(f"DEBUG: Things event received: {event}")
    user_id = event.source.user_id
    reply_token = event.reply_token
    messages = [TextMessage(text=f"Thingsイベント: {event.things.type}")]
    line_bot_api_messaging.reply_message(
        ReplyMessageRequest(
            reply_token=reply_token,
            messages=messages
        )
    )
