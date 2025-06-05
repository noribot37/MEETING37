import re
# LINE Bot SDK v3 のインポート
from linebot.v3.messaging import MessagingApi, ReplyMessageRequest
from linebot.v3.messaging.models import TextMessage # TextMessageを直接インポート
from linebot.v3.webhooks import MessageEvent, TextMessageContent # WebhookMessageEvent を MessageEvent に修正

from config import SessionState

# 各コマンドモジュールから必要な関数を直接インポート
from line_handlers.commands import (
    start_schedule_registration, handle_schedule_registration,
    start_schedule_deletion, handle_schedule_deletion,
    start_schedule_editing, handle_schedule_editing,
    list_schedules,
    list_participants,
    list_my_planned_events,
    start_attendance_editing,
    handle_attendance_editing
)

# 各Q&Aモジュールから必要な関数を直接インポート
from line_handlers.qna.attendance_qna import (
    start_attendance_qa,
    handle_attendance_qa_response
)

# グローバルなセッション管理用の辞書
user_sessions = {}

# process_message 関数の型ヒントを MessageEvent に修正
def process_message(event: MessageEvent, line_bot_api_messaging: MessagingApi):
    user_id = event.source.user_id
    # v3 SDKのget_profileはMessagingApiのメソッド
    try:
        profile = line_bot_api_messaging.get_profile(user_id)
        user_display_name = profile.display_name
    except Exception as e:
        print(f"ERROR: Could not get profile for user {user_id}: {e}")
        user_display_name = "ユーザー" # エラーの場合のフォールバック

    # event.message は TextMessageContent 型
    user_message = event.message.text
    reply_token = event.reply_token

    print(f"DEBUG: Received message from {user_display_name} ({user_id}): {user_message}")

    current_session = user_sessions.get(user_id, {'state': SessionState.NONE, 'data': {}})
    state = current_session['state']
    print(f"DEBUG: Current session state for {user_id}: {state}")

    # 緊急停止/セッションリセットコマンドを最優先で処理
    if user_message == "キャンセル" or user_message == "リセット":
        if user_id in user_sessions:
            user_sessions.pop(user_id) # セッションをクリア
            messages = [TextMessage(text="現在の操作をキャンセルしました。")] # TextMessageを直接使用
            line_bot_api_messaging.reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=messages
                )
            )
            print(f"DEBUG: Session for {user_id} cancelled and replied.")
            return

    # コマンドメッセージリスト
    command_messages = [
        "スケジュール登録", "スケジュール削除", "スケジュール編集", "スケジュール一覧",
        "参加者一覧", "参加予定一覧", "参加予定編集", "出欠登録", "ヘルプ"
    ]

    # アクティブなセッションが存在しても、コマンドメッセージが送られた場合は、
    # セッションをクリアしてコマンドを優先的に処理する
    if user_message in command_messages and state != SessionState.NONE:
        print(f"DEBUG: Command '{user_message}' received during active session ({state}). Clearing session.")
        user_sessions.pop(user_id) # 現在のセッションを破棄
        current_session = {'state': SessionState.NONE, 'data': {}} # 新しいセッションを開始
        state = SessionState.NONE # 状態をリセット

    # セッション状態に応じたフロー処理
    if state == SessionState.ASKING_TITLE or \
       state == SessionState.ASKING_DATE or \
       state == SessionState.ASKING_TIME or \
       state == SessionState.ASKING_LOCATION or \
       state == SessionState.ASKING_DETAIL or \
       state == SessionState.ASKING_DEADLINE or \
       state == SessionState.ASKING_DURATION:
        print(f"DEBUG: Entering schedule registration flow.")
        handle_schedule_registration(user_id, user_message, reply_token, line_bot_api_messaging, user_sessions, current_session)
        return

    if state == SessionState.DELETING_SCHEDULE_DATE or \
       state == SessionState.DELETING_SCHEDULE_TITLE or \
       state == SessionState.AWAITING_DELETE_CONFIRMATION:
        print(f"DEBUG: Entering schedule deletion flow.")
        handle_schedule_deletion(user_id, user_message, reply_token, line_bot_api_messaging, user_sessions, current_session)
        return

    if state == SessionState.EDITING_SCHEDULE_DATE or \
       state == SessionState.EDITING_SCHEDULE_TITLE or \
       state == SessionState.SELECTING_EDIT_ITEM or \
       state == SessionState.ASKING_NEW_VALUE:
        print(f"DEBUG: Entering schedule editing flow.")
        handle_schedule_editing(user_id, user_message, reply_token, line_bot_api_messaging, user_sessions, current_session)
        return

    if state == SessionState.EDITING_ATTENDANCE_DATE or \
       state == SessionState.EDITING_ATTENDANCE_TITLE or \
       state == SessionState.CONFIRM_ATTENDANCE_ACTION or \
       state == SessionState.EDITING_ATTENDANCE_NOTE or \
       state == SessionState.ASK_ANOTHER_ATTENDANCE_EDIT:
        print(f"DEBUG: Entering attendance editing flow.")
        handle_attendance_editing(user_id, user_display_name, user_message, reply_token, line_bot_api_messaging, user_sessions, current_session)
        return

    if state == SessionState.ASKING_ATTENDANCE_STATUS or \
       state == SessionState.AWAITING_ATTENDANCE_CONFIRMATION or \
       state == SessionState.ASKING_ATTENDANCE_TARGET_EVENT:
        print(f"DEBUG: Entering attendance Q&A flow.")
        handle_attendance_qa_response(user_id, user_display_name, user_message, reply_token, line_bot_api_messaging, user_sessions, current_session)
        return

    # --- 出欠登録の意向確認の処理 ---
    if state == SessionState.ASKING_ATTENDANCE_INTENTION:
        print(f"DEBUG: Current state: {state}")
        print(f"DEBUG: ASKING_ATTENDANCE_INTENTION: {SessionState.ASKING_ATTENDANCE_INTENTION}")
        print(f"DEBUG: State comparison: {state == SessionState.ASKING_ATTENDANCE_INTENTION}")
        print(f"DEBUG: Processing ASKING_ATTENDANCE_INTENTION for user {user_id}, message: {user_message}")

        if user_message == "はい":
            print(f"DEBUG: User {user_id} wants to register attendance.")
            start_attendance_qa(user_id, reply_token, line_bot_api_messaging, user_sessions)
            return
        elif user_message == "いいえ":
            print(f"DEBUG: User {user_id} declined attendance registration.")
            messages = [TextMessage(text="了解しました。")]
            line_bot_api_messaging.reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=messages
                )
            )
            user_sessions.pop(user_id, None) # セッションをクリア
            return
        else:
            print(f"DEBUG: Invalid response for attendance intention: {user_message}")
            messages = [TextMessage(text="「はい」または「いいえ」で答えてください。")]
            line_bot_api_messaging.reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=messages
                )
            )
            return

    # セッションがない場合のコマンド処理
    print(f"DEBUG: No active session. Processing command: {user_message}")
    if user_message == "スケジュール登録":
        start_schedule_registration(user_id, reply_token, line_bot_api_messaging, user_sessions)
    elif user_message == "スケジュール削除":
        start_schedule_deletion(user_id, reply_token, line_bot_api_messaging, user_sessions)
    elif user_message == "スケジュール編集":
        start_schedule_editing(user_id, reply_token, line_bot_api_messaging, user_sessions)
    elif user_message == "スケジュール一覧":
        # list_schedulesの引数を修正
        list_schedules(user_id, reply_token, line_bot_api_messaging, user_sessions)
    elif user_message == "参加者一覧":
        list_participants(user_id, reply_token, line_bot_api_messaging)
    elif user_message == "参加予定一覧":
        list_my_planned_events(user_id, user_display_name, reply_token, line_bot_api_messaging)
    elif user_message == "参加予定編集":
        start_attendance_editing(user_id, reply_token, line_bot_api_messaging, user_sessions)
    elif user_message == "出欠登録":
        start_attendance_qa(user_id, reply_token, line_bot_api_messaging, user_sessions)
    elif user_message == "ヘルプ":
        messages = [TextMessage(text="ヘルプ機能は現在開発中です。\n利用可能なコマンド:\n・スケジュール登録\n・スケジュール削除\n・スケジュール編集\n・スケジュール一覧\n・参加者一覧\n・参加予定一覧\n・参加予定編集\n・出欠登録")] # TextMessageを直接使用
        line_bot_api_messaging.reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=messages
            )
        )
    else:
        # デフォルト応答
        print(f"DEBUG: No matching command or active session. Sending default response.")
        response_text = "どのようなご用件でしょうか？\n\n" \
                        "利用可能なコマンド:\n" \
                        "・スケジュール登録\n" \
                        "・スケジュール削除\n" \
                        "・スケジュール編集\n" \
                        "・スケジュール一覧\n" \
                        "・参加者一覧\n" \
                        "・参加予定一覧\n" \
                        "・参加予定編集\n" \
                        "・出欠登録\n" \
                        "・ヘルプ"
        messages = [TextMessage(text=response_text)] # TextMessageを直接使用
        line_bot_api_messaging.reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=messages
            )
        )