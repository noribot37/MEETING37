import os
from linebot.v3.messaging import MessagingApi, ReplyMessageRequest, TextMessage
from linebot.v3.messaging.models import QuickReply, QuickReplyItem, MessageAction

from config import Config, SessionState
from line_handlers.commands import (
    schedule_commands,
    attendance_commands,
)
from line_handlers.qna import attendance_qna

from utils.session_manager import get_user_session_data, set_user_session_data, delete_user_session_data


def process_message(user_id: str, message_text: str, reply_token: str, user_display_name: str, line_bot_api_messaging: MessagingApi):
    print(f"DEBUG: process_message called. User ID: {user_id}, Message: '{message_text}', State: {SessionState.get_state(user_id)}")

    current_state = SessionState.get_state(user_id)
    session_data = get_user_session_data(user_id, Config.SESSION_DATA_KEY) or {}

    if message_text == "終了":
        print(f"DEBUG: '終了' command received for user {user_id}")
        SessionState.set_state(user_id, SessionState.NONE)
        delete_user_session_data(user_id, Config.SESSION_DATA_KEY)
        line_bot_api_messaging.reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[TextMessage(text="セッションを終了します。")]
            )
        )
        return

    if current_state == SessionState.NONE:
        print(f"DEBUG: Current state is NONE for user {user_id}")
        if message_text == "スケジュール登録":
            print("DEBUG: Calling start_schedule_registration")
            schedule_commands.start_schedule_registration(user_id, reply_token, line_bot_api_messaging)
        elif message_text == "スケジュール一覧":
            print("DEBUG: Calling list_schedules")
            schedule_commands.list_schedules(user_id, reply_token, line_bot_api_messaging)
        elif message_text == "スケジュール編集":
            print("DEBUG: Calling start_schedule_edit")
            schedule_commands.start_schedule_edit(user_id, reply_token, line_bot_api_messaging)
        elif message_text == "スケジュール削除":
            print("DEBUG: Calling start_schedule_deletion")
            schedule_commands.start_schedule_deletion(user_id, reply_token, line_bot_api_messaging)
        elif message_text == "参加予定登録":
            print("DEBUG: Calling start_attendance_qa")
            attendance_qna.start_attendance_qa(
                user_id,
                user_display_name,
                reply_token,
                line_bot_api_messaging
            )
        elif message_text == "参加予定一覧":
            print("DEBUG: Calling list_user_attendees")
            attendance_commands.list_user_attendees(user_id, reply_token, line_bot_api_messaging)
        elif message_text == "参加予定編集":
            print("DEBUG: Calling start_attendee_edit")
            attendance_commands.start_attendee_edit(user_id, reply_token, line_bot_api_messaging)
        elif message_text == "参加者一覧":
            print("DEBUG: Calling list_attendees")
            attendance_commands.list_attendees(user_id, reply_token, line_bot_api_messaging)
        else:
            print("DEBUG: Default reply message")
            line_bot_api_messaging.reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[TextMessage(text=Config.DEFAULT_REPLY_MESSAGE)]
                )
            )
    elif current_state == SessionState.ASKING_ATTENDANCE_STATUS or \
         current_state == SessionState.ASKING_FOR_REMARKS_CONFIRMATION or \
         current_state == SessionState.ASKING_ATTENDANCE_REMARKS:
        print(f"DEBUG: Processing attendance Q&A. State: {current_state}, Message: {message_text}")
        attendance_qna.handle_attendance_qa_response(
            user_id,
            message_text,
            reply_token,
            line_bot_api_messaging
        )
    # スケジュール登録の質問フローを処理する主要な分岐です。
    # ASKING_CONFIRM_SCHEDULE_REGISTRATION をリストから削除しました。
    elif current_state in [
        SessionState.ASKING_SCHEDULE_DATE,
        SessionState.ASKING_SCHEDULE_TITLE,
        SessionState.ASKING_SCHEDULE_START_TIME,
        SessionState.ASKING_SCHEDULE_LOCATION,
        SessionState.ASKING_SCHEDULE_DETAIL,
        SessionState.ASKING_SCHEDULE_DEADLINE,
        SessionState.ASKING_SCHEDULE_SCALE,
        # SessionState.ASKING_CONFIRM_SCHEDULE_REGISTRATION, # この行を削除
        SessionState.ASKING_FOR_ANOTHER_SCHEDULE_REGISTRATION
    ]:
        print(f"DEBUG: Processing schedule registration step. State: {current_state}")
        schedule_commands.process_schedule_registration_step(user_id, message_text, reply_token, line_bot_api_messaging)
    elif current_state.startswith("asking_schedule_edit_"):
        print(f"DEBUG: Processing schedule edit step. State: {current_state}")
        schedule_commands.process_schedule_edit_step(user_id, message_text, reply_token, line_bot_api_messaging)
    elif current_state.startswith("asking_schedule_delete_"):
        print(f"DEBUG: Processing schedule delete step. State: {current_state}")
        schedule_commands.process_schedule_deletion_step(user_id, message_text, reply_token, line_bot_api_messaging)
    elif current_state == SessionState.ASKING_ATTENDEE_REGISTRATION_CONFIRMATION:
        print(f"DEBUG: Processing attendee registration confirmation. Message: {message_text}")
        if message_text == "はい":
            print("DEBUG: Confirmation 'はい', calling start_attendance_qa")
            attendance_qna.start_attendance_qa(
                user_id,
                user_display_name,
                reply_token,
                line_bot_api_messaging
            )
        elif message_text == "いいえ":
            print("DEBUG: Confirmation 'いいえ', ending session")
            SessionState.set_state(user_id, SessionState.NONE)
            delete_user_session_data(user_id, Config.SESSION_DATA_KEY)
            line_bot_api_messaging.reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[TextMessage(text="参加希望の登録をキャンセルしました。")]
                )
            )
        else:
            print("DEBUG: Invalid confirmation input")
            line_bot_api_messaging.reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[TextMessage(
                        text="「はい」または「いいえ」でお答えください。",
                        quick_reply=QuickReply(items=[
                            QuickReplyItem(action=MessageAction(label="はい", text="はい")),
                            QuickReplyItem(action=MessageAction(label="いいえ", text="いいえ"))
                        ])
                    )]
                )
            )
    elif current_state.startswith("asking_attendee_registration_"):
        print(f"DEBUG: Processing attendee registration step. State: {current_state}")
        attendance_commands.process_attendee_registration_step(user_id, message_text, reply_token, line_bot_api_messaging)
    elif current_state.startswith("asking_attendee_"):
        print(f"DEBUG: Processing attendee edit step. State: {current_state}")
        attendance_commands.process_attendee_edit_step(user_id, message_text, reply_token, line_bot_api_messaging)
    else:
        print(f"DEBUG: Unknown state encountered: {current_state}. Resetting session.")
        SessionState.set_state(user_id, SessionState.NONE)
        delete_user_session_data(user_id, Config.SESSION_DATA_KEY)
        line_bot_api_messaging.reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[TextMessage(text="不明な状態です。セッションをリセットしました。\n" + Config.DEFAULT_REPLY_MESSAGE)]
            )
        )
