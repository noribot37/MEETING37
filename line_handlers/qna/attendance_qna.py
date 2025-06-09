import os
from datetime import datetime
import re
import pandas as pd 

from linebot.v3.messaging import (
    MessagingApi,
    ReplyMessageRequest,
    TextMessage
)
from linebot.v3.messaging.models import QuickReply, QuickReplyItem, MessageAction

from config import Config, SessionState
from google_sheets.utils import get_all_records, update_or_add_attendee, get_attendees_for_user

from utils.session_manager import get_user_session_data, set_user_session_data, delete_user_session_data


def start_attendance_qa(user_id, user_display_name, reply_token, line_bot_api_messaging: MessagingApi):
    try:
        all_meetings_df = get_all_records(Config.GOOGLE_SHEETS_SCHEDULE_WORKSHEET_NAME)

        if all_meetings_df.empty:
            line_bot_api_messaging.reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[TextMessage(text="現在、登録されているスケジュールはありません。\nまずは「スケジュール登録」でイベントを作成してください。")]
                )
            )
            delete_user_session_data(user_id, Config.SESSION_DATA_KEY)
            SessionState.set_state(user_id, SessionState.NONE)
            return

        all_meetings_df['日付'] = pd.to_datetime(all_meetings_df['日付'], errors='coerce')

        user_attendees = get_attendees_for_user(user_id)
        processed_attended_events = set()
        for att in user_attendees:
            if len(att) >= 2:
                att_title = att[0]
                att_date_str = att[1]
                if att_date_str and att_title:
                    try:
                        att_date_obj = datetime.strptime(att_date_str, '%Y/%m/%d').date()
                        processed_attended_events.add((att_date_obj, att_title))
                    except ValueError:
                        print(f"DEBUG: Skipping invalid date format in user_attendees: {att_date_str}")
                        continue

        unregistered_meetings = []
        for index, meeting_series in all_meetings_df.iterrows():
            meeting = meeting_series.to_dict()
            date_timestamp = meeting.get('日付')
            title = meeting.get('タイトル')

            if pd.notna(date_timestamp) and title:
                if (date_timestamp.date(), title) not in processed_attended_events:
                    unregistered_meetings.append((date_timestamp, meeting))

        unregistered_meetings.sort(key=lambda x: x[0])

        if not unregistered_meetings:
            line_bot_api_messaging.reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[TextMessage(text="現在、登録可能な未参加予定のスケジュールはありません。\n「参加予定一覧」で現在の参加予定状況を確認できます。")]
                )
            )
            delete_user_session_data(user_id, Config.SESSION_DATA_KEY)
            SessionState.set_state(user_id, SessionState.NONE)
            return

        session_data = {
            'state': SessionState.ASKING_ATTENDANCE_STATUS,
            'data': {
                'unregistered_events': [
                    {'date': meeting[0].strftime('%Y/%m/%d'), 'title': meeting[1].get('タイトル')}
                    for meeting in unregistered_meetings
                ],
                'current_event_index': 0,
                'user_id': user_id,
                'user_display_name': user_display_name
            }
        }
        set_user_session_data(user_id, Config.SESSION_DATA_KEY, session_data)
        SessionState.set_state(user_id, SessionState.ASKING_ATTENDANCE_STATUS)

        current_event = session_data['data']['unregistered_events'][session_data['data']['current_event_index']]

        response_text = f"こちらのイベントの参加予定を登録します。\n\n{current_event['date']} の「{current_event['title']}」\n\n参加予定を教えてください（〇, △, ×）"

        line_bot_api_messaging.reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[TextMessage(
                    text=response_text,
                    quick_reply=QuickReply(items=[
                        QuickReplyItem(action=MessageAction(label='〇', text='〇')),
                        QuickReplyItem(action=MessageAction(label='△', text='△')),
                        QuickReplyItem(action=MessageAction(label='×', text='×'))
                    ])
                )]
            )
        )
        print(f"DEBUG: Started attendance Q&A for user {user_id}. State: ASKING_ATTENDANCE_STATUS. First event: {current_event['title']}")

    except Exception as e:
        error_msg = f"参加予定登録の開始中にエラーが発生しました: {e}"
        print(f"ERROR: {error_msg}")
        line_bot_api_messaging.reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[TextMessage(text=error_msg)]
            )
        )
        delete_user_session_data(user_id, Config.SESSION_DATA_KEY)
        SessionState.set_state(user_id, SessionState.NONE)


def handle_attendance_qa_response(user_id, user_message, reply_token, line_bot_api_messaging: MessagingApi):
    current_session_data = get_user_session_data(user_id, Config.SESSION_DATA_KEY)
    if not current_session_data:
        line_bot_api_messaging.reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[TextMessage(text="現在、参加予定登録の処理が中断されているようです。\n「参加予定登録」と入力して最初からやり直してください。")]
            )
        )
        SessionState.set_state(user_id, SessionState.NONE)
        return

    state = SessionState.get_state(user_id)
    data = current_session_data.get('data', {})
    messages = []

    session_user_id = data.get('user_id')
    session_user_display_name = data.get('user_display_name')

    if not session_user_id or not session_user_display_name:
        messages.append(TextMessage(text="ユーザー情報の取得に失敗しました。\n「参加予定登録」と入力して最初からやり直してください。"))
        delete_user_session_data(user_id, Config.SESSION_DATA_KEY)
        SessionState.set_state(user_id, SessionState.NONE)
        line_bot_api_messaging.reply_message(ReplyMessageRequest(reply_token=reply_token, messages=messages))
        return

    print(f"DEBUG: Handling attendance Q&A. User ID: {user_id}, Current State: {state}, Message: {user_message}")

    if state == SessionState.ASKING_ATTENDANCE_STATUS:
        status = user_message
        if status in ['〇', '△', '×']:
            data['attendance_status'] = status  # 参加ステータスをセッションデータに保存
            set_user_session_data(user_id, Config.SESSION_DATA_KEY, current_session_data)  # セッションデータを更新 (重要)
            SessionState.set_state(user_id, SessionState.ASKING_FOR_REMARKS_CONFIRMATION)  # 状態を更新

            messages.append(TextMessage(
                text="備考はありますか？",
                quick_reply=QuickReply(items=[
                    QuickReplyItem(action=MessageAction(label='はい', text='はい')),
                    QuickReplyItem(action=MessageAction(label='いいえ', text='いいえ'))
                ])
            ))
        else:
            messages.append(TextMessage(text="参加予定は「〇」「△」「×」のいずれかで入力してください。",
                quick_reply=QuickReply(items=[
                    QuickReplyItem(action=MessageAction(label='〇', text='〇')),
                    QuickReplyItem(action=MessageAction(label='△', text='△')),
                    QuickReplyItem(action=MessageAction(label='×', text='×'))
                ])
            ))

    elif state == SessionState.ASKING_FOR_REMARKS_CONFIRMATION:
        if user_message == 'はい':
            SessionState.set_state(user_id, SessionState.ASKING_ATTENDANCE_REMARKS)
            messages.append(TextMessage(text="備考を入力してください。"))
        elif user_message == 'いいえ':
            unregistered_events = data.get('unregistered_events', [])
            current_event_index = data.get('current_event_index', 0)

            if not unregistered_events or current_event_index >= len(unregistered_events):
                messages.append(TextMessage(text="処理すべきイベントが見つかりませんでした。\n「参加予定登録」と入力してやり直してください。"))
                delete_user_session_data(user_id, Config.SESSION_DATA_KEY)
                SessionState.set_state(user_id, SessionState.NONE)
                line_bot_api_messaging.reply_message(ReplyMessageRequest(reply_token=reply_token, messages=messages))
                return

            current_event = unregistered_events[current_event_index]
            event_date = current_event['date']
            event_title = current_event['title']
            attendance_status = data.get('attendance_status', '')  # 保存された参加ステータスを取得

            try:
                success, msg = update_or_add_attendee(
                    date=event_date,
                    title=event_title,
                    user_id=session_user_id,
                    username=session_user_display_name,
                    attendance_status=attendance_status,  # 保存されたステータスを使用
                    notes=''  # 備考は空
                )
                if success:
                    messages.append(TextMessage(text=f"{event_date} の「{event_title}」の参加予定を登録しました！"))

                    next_event_index = current_event_index + 1
                    if next_event_index < len(unregistered_events):
                        data['current_event_index'] = next_event_index
                        set_user_session_data(user_id, Config.SESSION_DATA_KEY, current_session_data) # セッションデータを更新

                        next_event = unregistered_events[next_event_index]
                        messages.append(TextMessage(
                            text=f"続けてこちらのイベントの参加予定を登録します。\n\n{next_event['date']} の「{next_event['title']}」\n\n参加予定を教えてください（〇, △, ×）",
                            quick_reply=QuickReply(items=[
                                QuickReplyItem(action=MessageAction(label='〇', text='〇')),
                                QuickReplyItem(action=MessageAction(label='△', text='△')),
                                QuickReplyItem(action=MessageAction(label='×', text='×'))
                            ])
                        ))
                        # !!! 修正箇所: 次のイベントがある場合、必ずこの状態に戻す !!!
                        SessionState.set_state(user_id, SessionState.ASKING_ATTENDANCE_STATUS) 
                    else:
                        messages.append(TextMessage(text="全ての未登録イベントの参加予定登録が完了しました！\nありがとうございました。"))
                        delete_user_session_data(user_id, Config.SESSION_DATA_KEY)
                        SessionState.set_state(user_id, SessionState.NONE)

                else:
                    messages.append(TextMessage(text=f"参加予定登録中にエラーが発生しました: {msg}"))
                    delete_user_session_data(user_id, Config.SESSION_DATA_KEY)
                    SessionState.set_state(user_id, SessionState.NONE)
            except Exception as e:
                messages.append(TextMessage(text=f"参加予定登録中に予期せぬエラーが発生しました: {e}"))
                delete_user_session_data(user_id, Config.SESSION_DATA_KEY)
                SessionState.set_state(user_id, SessionState.NONE)
        else:
            messages.append(TextMessage(
                text="「はい」または「いいえ」で答えてください。",
                quick_reply=QuickReply(items=[
                    QuickReplyItem(action=MessageAction(label='はい', text='はい')),
                    QuickReplyItem(action=MessageAction(label='いいえ', text='いいえ'))
                ])
            ))
            # !!! 修正箇所: 不適切な入力の場合も状態は変えない !!!
            SessionState.set_state(user_id, SessionState.ASKING_FOR_REMARKS_CONFIRMATION) 

    elif state == SessionState.ASKING_ATTENDANCE_REMARKS:
        attendance_remarks = user_message  # ユーザーのメッセージを備考として取得

        unregistered_events = data.get('unregistered_events', [])
        current_event_index = data.get('current_event_index', 0)

        if not unregistered_events or current_event_index >= len(unregistered_events):
            messages.append(TextMessage(text="処理すべきイベントが見つかりませんでした。\n「参加予定登録」と入力してやり直してください。"))
            delete_user_session_data(user_id, Config.SESSION_DATA_KEY)
            SessionState.set_state(user_id, SessionState.NONE)
            line_bot_api_messaging.reply_message(ReplyMessageRequest(reply_token=reply_token, messages=messages))
            return

        current_event = unregistered_events[current_event_index]
        event_date = current_event['date']
        event_title = current_event['title']
        attendance_status = data.get('attendance_status', '')  # 保存された参加ステータスを取得

        try:
            success, msg = update_or_add_attendee(
                date=event_date,
                title=event_title,
                user_id=session_user_id,
                username=session_user_display_name,
                attendance_status=attendance_status,  # 保存されたステータスを使用
                notes=attendance_remarks  # ユーザーからの備考を使用
            )
            if success:
                messages.append(TextMessage(text=f"{event_date} の「{event_title}」の参加予定を登録しました！"))

                next_event_index = current_event_index + 1
                if next_event_index < len(unregistered_events):
                    data['current_event_index'] = next_event_index
                    set_user_session_data(user_id, Config.SESSION_DATA_KEY, current_session_data) # セッションデータを更新

                    next_event = unregistered_events[next_event_index]
                    messages.append(TextMessage(
                        text=f"続けてこちらのイベントの参加予定を登録します。\n\n{next_event['date']} の「{next_event['title']}」\n\n参加予定を教えてください（〇, △, ×）",
                        quick_reply=QuickReply(items=[
                            QuickReplyItem(action=MessageAction(label='〇', text='〇')),
                            QuickReplyItem(action=MessageAction(label='△', text='△')),
                            QuickReplyItem(action=MessageAction(label='×', text='×'))
                        ])
                    ))
                    # !!! 修正箇所: 次のイベントがある場合、必ずこの状態に戻す !!!
                    SessionState.set_state(user_id, SessionState.ASKING_ATTENDANCE_STATUS) 
                else:
                    messages.append(TextMessage(text="全ての未登録イベントの参加予定登録が完了しました！\nありがとうございました。"))
                    delete_user_session_data(user_id, Config.SESSION_DATA_KEY)
                    SessionState.set_state(user_id, SessionState.NONE)

            else:
                messages.append(TextMessage(text=f"参加予定登録中にエラーが発生しました: {msg}"))
                delete_user_session_data(user_id, Config.SESSION_DATA_KEY)
                SessionState.set_state(user_id, SessionState.NONE)
        except Exception as e:
            messages.append(TextMessage(text=f"参加予定登録中に予期せぬエラーが発生しました: {e}"))
            delete_user_session_data(user_id, Config.SESSION_DATA_KEY)
            SessionState.set_state(user_id, SessionState.NONE)

    else: # どの状態にも当てはまらない場合（エラーまたは不明な状態）
        # この部分が、意図しない「不明な状態です」メッセージの原因となることがあるため、
        # より慎重なハンドリングが必要。基本的には、このブロックに来る前に適切な状態遷移が行われているべき。
        messages.append(TextMessage(text="現在、参加予定登録の処理が中断されているようです。\n「参加予定登録」と入力して最初からやり直してください。"))
        delete_user_session_data(user_id, Config.SESSION_DATA_KEY)
        SessionState.set_state(user_id, SessionState.NONE)

    # 応答メッセージが空の場合のガード
    if not messages:
        print(f"WARNING: No messages generated for user {user_id} at state {state} with message {user_message}. Sending default reset message.")
        messages.append(TextMessage(text="予期せぬエラーが発生しました。セッションをリセットします。\n「参加予定登録」と入力して最初からやり直してください。"))
        delete_user_session_data(user_id, Config.SESSION_DATA_KEY)
        SessionState.set_state(user_id, SessionState.NONE)

    line_bot_api_messaging.reply_message(
        ReplyMessageRequest(
            reply_token=reply_token,
            messages=messages
        )
    )
