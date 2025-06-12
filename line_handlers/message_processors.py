import re
from linebot.v3.messaging import Configuration, ApiClient, MessagingApi, ReplyMessageRequest, TextMessage
from linebot.v3.webhooks import MessageEvent, TextMessageContent

from config import Config, SessionState
from line_handlers.commands import (
    general_commands,
    schedule_commands,
    attendance_commands
)
from line_handlers.qna import attendance_qna
from utils.session_manager import get_user_session_data, set_user_session_data, delete_user_session_data

# LINE Messaging APIクライアントの初期化
configuration = Configuration(access_token=Config.LINE_CHANNEL_ACCESS_TOKEN)
line_bot_api_messaging = MessagingApi(ApiClient(configuration))

def process_message(event: MessageEvent):
    """
    受信したメッセージイベントを処理し、適切なハンドラーにルーティングします。
    """
    user_id = event.source.user_id
    message_text = event.message.text
    reply_token = event.reply_token

    print(f"DEBUG: --- Webhook Received ---")
    print(f"DEBUG: User ID: {user_id}")
    print(f"DEBUG: Received Message Text: '{message_text}' (Type: {type(message_text)})")

    current_state = SessionState.get_state(user_id)
    print(f"DEBUG: Current Session State: {current_state}")

    # セッションデータは session_manager から取得
    session_data = get_user_session_data(user_id) # 修正箇所: SessionState.get_data を削除

    # 既存のセッション状態に基づいて処理を続行
    if current_state != SessionState.NONE:
        # スケジュール登録のフロー
        if current_state.startswith("asking_schedule_"):
            if message_text.lower() == 'キャンセル':
                SessionState.clear_state(user_id)
                delete_user_session_data(user_id) # 修正箇所: Config.SESSION_DATA_KEY を削除
                line_bot_api_messaging.reply_message(
                    ReplyMessageRequest(
                        reply_token=reply_token,
                        messages=[TextMessage(text="スケジュール登録をキャンセルしました。")]
                    )
                )
                return
            schedule_commands.process_schedule_registration_step(user_id, message_text, reply_token, line_bot_api_messaging)
            return

        # スケジュール編集のフロー
        elif current_state.startswith("asking_schedule_edit_") or current_state == SessionState.ASKING_FOR_ANOTHER_SCHEDULE_EDIT:
            if message_text.lower() == 'キャンセル':
                SessionState.clear_state(user_id)
                delete_user_session_data(user_id) # 修正箇所: Config.SESSION_DATA_KEY を削除
                line_bot_api_messaging.reply_message(
                    ReplyMessageRequest(
                        reply_token=reply_token,
                        messages=[TextMessage(text="スケジュール編集をキャンセルしました。")]
                    )
                )
                return
            schedule_commands.process_schedule_edit_step(user_id, message_text, reply_token, line_bot_api_messaging)
            return

        # スケジュール削除のフロー
        elif current_state.startswith("asking_schedule_delete_") or current_state == SessionState.ASKING_FOR_NEXT_SCHEDULE_DELETION:
            if message_text.lower() == 'キャンセル':
                SessionState.clear_state(user_id)
                delete_user_session_data(user_id) # 修正箇所: Config.SESSION_DATA_KEY を削除
                line_bot_api_messaging.reply_message(
                    ReplyMessageRequest(
                        reply_token=reply_token,
                        messages=[TextMessage(text="スケジュール削除をキャンセルしました。")]
                    )
                )
                return
            schedule_commands.process_schedule_deletion_step(user_id, message_text, reply_token, line_bot_api_messaging)
            return

        # 参加予定登録Q&Aのフロー (message_processors.py のみで使用される状態)
        elif current_state == SessionState.ASKING_ATTENDEE_REGISTRATION_CONFIRMATION:
            attendance_qna.process_attendance_qna_step(user_id, message_text, reply_token, line_bot_api_messaging)
            return

        # 参加予定登録フロー (attendance_commands.py が使用する状態)
        elif current_state.startswith("asking_attendee_registration_") or current_state == SessionState.ASKING_FOR_ANOTHER_ATTENDEE_REGISTRATION:
            if message_text.lower() == 'キャンセル':
                SessionState.clear_state(user_id)
                delete_user_session_data(user_id) # 修正箇所: Config.SESSION_DATA_KEY を削除
                line_bot_api_messaging.reply_message(
                    ReplyMessageRequest(
                        reply_token=reply_token,
                        messages=[TextMessage(text="参加予定登録をキャンセルしました。")]
                    )
                )
                return
            attendance_commands.process_attendee_registration_step(user_id, message_text, reply_token, line_bot_api_messaging)
            return

        # 参加予定編集フロー
        elif current_state.startswith("asking_attendee_") or current_state == SessionState.ASKING_FOR_ANOTHER_ATTENDEE_EDIT:
            if message_text.lower() == 'キャンセル':
                SessionState.clear_state(user_id)
                delete_user_session_data(user_id) # 修正箇所: Config.SESSION_DATA_KEY を削除
                line_bot_api_messaging.reply_message(
                    ReplyMessageRequest(
                        reply_token=reply_token,
                        messages=[TextMessage(text="参加予定編集をキャンセルしました。")]
                    )
                )
                return
            attendance_commands.process_attendee_edit_step(user_id, message_text, reply_token, line_bot_api_messaging)
            return


    # 新しいコマンドの開始
    print(f"DEBUG: Current state is NONE for user {user_id}")
    if message_text == 'スケジュール登録':
        print(f"DEBUG: Calling start_schedule_registration")
        schedule_commands.start_schedule_registration(user_id, reply_token, line_bot_api_messaging)
    elif message_text == 'スケジュール一覧':
        print(f"DEBUG: Calling list_schedules")
        schedule_commands.list_schedules(user_id, reply_token, line_bot_api_messaging)
    elif message_text == 'スケジュール編集':
        print(f"DEBUG: Calling start_schedule_edit")
        schedule_commands.start_schedule_edit(user_id, reply_token, line_bot_api_messaging)
    elif message_text == 'スケジュール削除':
        print(f"DEBUG: Calling start_schedule_deletion")
        schedule_commands.start_schedule_deletion(user_id, reply_token, line_bot_api_messaging)
    elif message_text == '参加希望登録':
        print(f"DEBUG: Calling start_attendance_registration_qna")
        attendance_qna.start_attendance_registration_qna(user_id, reply_token, line_bot_api_messaging)
    elif message_text == '参加予定一覧':
        print(f"DEBUG: Calling list_user_attendances")
        attendance_commands.list_user_attendances(user_id, reply_token, line_bot_api_messaging)
    elif message_text == '参加者一覧':
        print(f"DEBUG: Calling list_all_attendees")
        attendance_commands.list_all_attendees(user_id, reply_token, line_bot_api_messaging)
    elif message_text == '参加予定編集':
        print(f"DEBUG: Calling start_attendee_edit")
        attendance_commands.start_attendee_edit(user_id, reply_token, line_bot_api_messaging)
    elif message_text == 'ヘルプ':
        print(f"DEBUG: Calling send_help_message")
        general_commands.send_help_message(reply_token, line_bot_api_messaging)
    else:
        # どのコマンドにも該当しない場合、デフォルトメッセージを送信
        print(f"DEBUG: Sending default reply message.")
        line_bot_api_messaging.reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[TextMessage(text=Config.DEFAULT_REPLY_MESSAGE)]
            )
        )

