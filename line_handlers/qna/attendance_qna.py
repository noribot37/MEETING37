# line_handlers/qna/attendance_qna.py

import os
from datetime import datetime
import re
import pandas as pd # 追加: pandasをインポート

from linebot.v3.messaging import (
    MessagingApi,
    ReplyMessageRequest,
    TextMessage
)
from linebot.v3.messaging.models import QuickReply, QuickReplyItem, MessageAction

from config import Config, SessionState
# get_all_records, update_or_add_attendee, get_attendees_for_user を utils.py からインポート
from google_sheets.utils import get_all_records, update_or_add_attendee, get_attendees_for_user

# utils/session_managerからセッション操作関数をインポート
from utils.session_manager import get_user_session_data, set_user_session_data, delete_user_session_data


# start_attendance_qa関数の修正
def start_attendance_qa(user_id, reply_token, line_bot_api_messaging: MessagingApi): # user_sessions 引数を削除
    """
    「参加予定登録」コマンドの開始処理。
    ユーザーに未登録のイベントを提示し、参加予定を尋ねる。
    """
    try:
        # 修正箇所: Config.SCHEDULE_WORKSHEET_NAME を Config.GOOGLE_SHEETS_SCHEDULE_WORKSHEET_NAME に変更
        all_meetings_df = get_all_records(Config.GOOGLE_SHEETS_SCHEDULE_WORKSHEET_NAME)

        if all_meetings_df.empty:
            line_bot_api_messaging.reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[TextMessage(text="現在、登録されているスケジュールはありません。\nまずは「スケジュール登録」でイベントを作成してください。")]
                )
            )
            # セッションデータをクリア
            delete_user_session_data(user_id, Config.SESSION_DATA_KEY)
            SessionState.set_state(user_id, SessionState.NONE) # 状態もリセット
            return

        # 追加: 日付列をPandasのdatetime型に変換（エラーを無視して変換できないものはNaTとする）
        all_meetings_df['日付'] = pd.to_datetime(all_meetings_df['日付'], errors='coerce')


        # ユーザーの既存の参加予定を取得
        user_attendees = get_attendees_for_user(user_id)
        # 追加: attendance_qna.py 内で、attended_events のキーとして `Timestamp` と `str` が混在しないように調整
        # user_attendees の '日付' も datetime オブジェクトに変換して比較する
        processed_attended_events = set()
        for att in user_attendees:
            att_date_str = att.get('日付')
            att_title = att.get('タイトル')
            if att_date_str and att_title:
                try:
                    # strptime() で文字列から datetime オブジェクトに変換し、Timestamp と比較できるようにする
                    att_date_obj = datetime.strptime(att_date_str, '%Y/%m/%d').date()
                    processed_attended_events.add((att_date_obj, att_title))
                except ValueError:
                    print(f"DEBUG: Skipping invalid date format in user_attendees: {att_date_str}")
                    continue

        # 未登録のスケジュールのみをフィルタリング
        unregistered_meetings = []
        for index, meeting_series in all_meetings_df.iterrows():
            meeting = meeting_series.to_dict()
            date_timestamp = meeting.get('日付') # ここはすでにTimestampかNaT
            title = meeting.get('タイトル')

            # 日付が有効なTimestampオブジェクトであり、タイトルも存在することを確認
            if pd.notna(date_timestamp) and title: # 修正: pd.notna()でNaTをチェック
                # Timestampオブジェクトの日付部分だけを取り出して比較
                if (date_timestamp.date(), title) not in processed_attended_events: # .date() で日付部分のみ比較
                    unregistered_meetings.append((date_timestamp, meeting)) # Timestampオブジェクトのまま追加

        # 日付でソートし、最も近い未登録スケジュールを抽出
        unregistered_meetings.sort(key=lambda x: x[0]) # Timestampオブジェクトでそのままソート可能

        if not unregistered_meetings:
            line_bot_api_messaging.reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[TextMessage(text="現在、登録可能な未参加予定のスケジュールはありません。\n「参加予定一覧」で現在の参加予定状況を確認できます。")]
                )
            )
            # セッションデータをクリア
            delete_user_session_data(user_id, Config.SESSION_DATA_KEY)
            SessionState.set_state(user_id, SessionState.NONE) # 状態もリセット
            return

        # 次に処理すべきイベントをセッションに保存
        # 直接set_user_session_dataを使用
        session_data = {
            'state': SessionState.ASKING_ATTENDANCE_STATUS, # この状態はattendance_qna内で管理される
            'data': {
                'unregistered_events': [
                    # ここでdatetimeオブジェクトを文字列に変換して保存
                    {'date': meeting[0].strftime('%Y/%m/%d'), 'title': meeting[1].get('タイトル')}
                    for meeting in unregistered_meetings
                ],
                'current_event_index': 0 # 現在処理中のイベントのインデックスを追加
            }
        }
        set_user_session_data(user_id, Config.SESSION_DATA_KEY, session_data)
        SessionState.set_state(user_id, SessionState.ASKING_ATTENDANCE_STATUS) # Globalな状態も設定

        # 最初の未登録イベントを取得
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
        # エラー発生時もセッションをリセット
        delete_user_session_data(user_id, Config.SESSION_DATA_KEY)
        SessionState.set_state(user_id, SessionState.NONE)


# handle_attendance_qa_response関数の修正
# user_sessionsとcurrent_session引数を削除し、session_managerから取得
def handle_attendance_qa_response(user_id, user_display_name, user_message, reply_token, line_bot_api_messaging: MessagingApi):
    """
    参加予定登録Q&Aフロー中のユーザー応答を処理する。
    """
    # セッションデータをsession_managerから直接取得
    current_session_data = get_user_session_data(user_id, Config.SESSION_DATA_KEY)
    if not current_session_data:
        # セッションデータがない場合はエラーメッセージを返して終了
        line_bot_api_messaging.reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[TextMessage(text="現在、参加予定登録の処理が中断されているようです。\n「参加予定登録」と入力して最初からやり直してください。")]
            )
        )
        SessionState.set_state(user_id, SessionState.NONE)
        return

    state = SessionState.get_state(user_id) # グローバルな状態を取得
    data = current_session_data.get('data', {})
    messages = []

    print(f"DEBUG: Handling attendance Q&A. State: {state}, Message: {user_message}")

    if state == SessionState.ASKING_ATTENDANCE_STATUS:
        status = user_message
        if status in ['〇', '△', '×']:
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

            try:
                success, msg = update_or_add_attendee(
                    date=event_date,
                    title=event_title,
                    user_id=user_id,
                    username=user_display_name,
                    attendance_status=status,
                    notes=data.get('attendance_remarks', '') # 備考は空文字として初期化、または既存のデータがあればそれを使用
                )
                if success:
                    messages.append(TextMessage(text=f"{event_date} の「{event_title}」の参加予定を登録しました！"))

                    # 次のイベントへインデックスを進める
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
                    else:
                        messages.append(TextMessage(text="全ての未登録イベントの参加予定登録が完了しました！\nありがとうございました。"))
                        delete_user_session_data(user_id, Config.SESSION_DATA_KEY)
                        SessionState.set_state(user_id, SessionState.NONE) # 状態をリセット

                else:
                    messages.append(TextMessage(text=f"参加予定登録中にエラーが発生しました: {msg}"))
                    delete_user_session_data(user_id, Config.SESSION_DATA_KEY)
                    SessionState.set_state(user_id, SessionState.NONE)
            except Exception as e:
                messages.append(TextMessage(text=f"参加予定登録中に予期せぬエラーが発生しました: {e}"))
                delete_user_session_data(user_id, Config.SESSION_DATA_KEY)
                SessionState.set_state(user_id, SessionState.NONE)
        else:
            messages.append(TextMessage(text="参加予定は「〇」「△」「×」のいずれかで入力してください。",
                quick_reply=QuickReply(items=[
                    QuickReplyItem(action=MessageAction(label='〇', text='〇')),
                    QuickReplyItem(action=MessageAction(label='△', text='△')),
                    QuickReplyItem(action=MessageAction(label='×', text='×'))
                ])
            ))
    else:
        messages.append(TextMessage(text="現在、参加予定登録の処理が中断されているようです。\n「参加予定登録」と入力して最初からやり直してください。"))
        delete_user_session_data(user_id, Config.SESSION_DATA_KEY)
        SessionState.set_state(user_id, SessionState.NONE)


    line_bot_api_messaging.reply_message(
        ReplyMessageRequest(
            reply_token=reply_token,
            messages=messages
        )
    )
