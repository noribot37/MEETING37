from linebot.v3.messaging import MessagingApi, ReplyMessageRequest, TextMessage

from config import Config, SessionState
from line_handlers.commands import (
    schedule_commands,
    attendance_commands,
    # qa_commands # QAコマンドは現在コメントアウトされているが、今後使用する場合は追加
)
# attendance_qnaモジュールをインポート
from line_handlers.qna import attendance_qna

# utils/session_managerからセッション操作関数をインポート
from utils.session_manager import get_user_session_data, set_user_session_data, delete_user_session_data

# LINE Messaging APIクライアントの初期化（実際はメインファイルで初期化して渡されることを想定）
# messaging_api = MessagingApi(ChannelAccessToken(Config.CHANNEL_ACCESS_TOKEN))


def process_message(user_id: str, message_text: str, reply_token: str, line_bot_api_messaging: MessagingApi):
    current_state = SessionState.get_state(user_id)
    session_data = get_user_session_data(user_id, Config.SESSION_DATA_KEY) or {}

    # 終了コマンドのチェック（常に優先）
    if message_text == "終了":
        SessionState.set_state(user_id, SessionState.NONE)
        delete_user_session_data(user_id, Config.SESSION_DATA_KEY)
        line_bot_api_messaging.reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[TextMessage(text="セッションを終了します。")]
            )
        )
        return

    # 状態に応じた処理
    if current_state == SessionState.NONE:
        # コマンドの振り分け
        if message_text == "スケジュール登録":
            schedule_commands.start_schedule_registration(user_id, reply_token, line_bot_api_messaging)
        elif message_text == "スケジュール一覧":
            schedule_commands.list_schedules(user_id, reply_token, line_bot_api_messaging)
        elif message_text == "スケジュール編集":
            schedule_commands.start_schedule_edit(user_id, reply_token, line_bot_api_messaging)
        elif message_text == "スケジュール削除":
            schedule_commands.start_schedule_deletion(user_id, reply_token, line_bot_api_messaging)
        elif message_text == "参加予定登録":
            attendance_commands.start_attendee_registration(user_id, reply_token, line_bot_api_messaging)
        elif message_text == "参加予定一覧":
            attendance_commands.list_user_attendees(user_id, reply_token, line_bot_api_messaging)
        elif message_text == "参加予定編集":
            attendance_commands.start_attendee_edit(user_id, reply_token, line_bot_api_messaging)
        elif message_text == "参加者一覧":
            attendance_commands.list_attendees(user_id, reply_token, line_bot_api_messaging)
        # elif message_text == "QA登録": # QA機能が有効な場合
        #     qa_commands.start_qa_registration(user_id, reply_token, line_bot_api_messaging)
        else:
            line_bot_api_messaging.reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[TextMessage(text=Config.DEFAULT_REPLY_MESSAGE)]
                )
            )
    # スケジュール登録
    elif current_state.startswith("asking_schedule_") and current_state != SessionState.ASKING_ATTENDEE_REGISTRATION_CONFIRMATION:
        schedule_commands.process_schedule_registration_step(user_id, message_text, reply_token, line_bot_api_messaging)
    # スケジュール編集
    elif current_state.startswith("asking_schedule_edit_"):
        schedule_commands.process_schedule_edit_step(user_id, message_text, reply_token, line_bot_api_messaging)
    # スケジュール削除
    elif current_state.startswith("asking_schedule_delete_"):
        schedule_commands.process_schedule_deletion_step(user_id, message_text, reply_token, line_bot_api_messaging)
    # 参加希望登録の確認
    elif current_state == SessionState.ASKING_ATTENDEE_REGISTRATION_CONFIRMATION:
        attendance_qna.handle_attendee_registration_confirmation(user_id, message_text, reply_token, line_bot_api_messaging)
    # 参加予定登録
    elif current_state.startswith("asking_attendee_registration_"):
        attendance_commands.process_attendee_registration_step(user_id, message_text, reply_token, line_bot_api_messaging)
    # 参加予定編集
    elif current_state.startswith("asking_attendee_"): # ATTENDEE_DATE, ATTENDEE_TITLE, CONFIRM_CANCEL, EDIT_NOTES, ANOTHER_ATTENDEE_EDIT
        attendance_commands.process_attendee_edit_step(user_id, message_text, reply_token, line_bot_api_messaging)
    # QA登録
    # elif current_state.startswith("asking_qa_"): # QA機能が有効な場合
    #     qa_commands.process_qa_registration_step(user_id, message_text, reply_token, line_bot_api_messaging)
    else:
        # 未定義の状態の場合、セッションをリセット
        SessionState.set_state(user_id, SessionState.NONE)
        delete_user_session_data(user_id, Config.SESSION_DATA_KEY)
        line_bot_api_messaging.reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[TextMessage(text="不明な状態です。セッションをリセットしました。\n" + Config.DEFAULT_REPLY_MESSAGE)]
            )
        )
