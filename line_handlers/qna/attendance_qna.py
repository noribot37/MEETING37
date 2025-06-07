import os
from datetime import datetime
import re
from linebot.v3.messaging import (
    MessagingApi,
    ReplyMessageRequest,
    TextMessage
)
from linebot.v3.messaging.models import QuickReply, QuickReplyItem, MessageAction

from config import Config, SessionState
# get_all_records, update_or_add_attendee, get_attendees_for_user を utils.py からインポート
from google_sheets.utils import get_all_records, update_or_add_attendee, get_attendees_for_user

def start_attendance_qa(user_id, reply_token, line_bot_api_messaging: MessagingApi, user_sessions):
    """
    「参加予定登録」コマンドの開始処理。
    ユーザーに未登録のイベントを提示し、参加予定を尋ねる。
    """
    try:
        # 修正: get_all_records は worksheet_name のみを受け取る
        all_meetings_df = get_all_records(Config.SCHEDULE_WORKSHEET_NAME)

        if all_meetings_df.empty:
            line_bot_api_messaging.reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[TextMessage(text="現在、登録されているスケジュールはありません。\nまずは「スケジュール登録」でイベントを作成してください。")]
                )
            )
            user_sessions.pop(user_id, None)
            return

        # ユーザーの既存の参加予定を取得
        # 修正: get_attendees_for_user は user_id のみを受け取る (utils.pyの定義による)
        user_attendees = get_attendees_for_user(user_id)
        # DataFrameのto_dict()を使ってrecords形式に変換してからセットを作成
        attended_events = {(att.get('日付'), att.get('タイトル')) for att in user_attendees}

        # 未登録のスケジュールのみをフィルタリング
        unregistered_meetings = []
        # DataFrameの各行を辞書としてイテレート
        for index, meeting_series in all_meetings_df.iterrows():
            meeting = meeting_series.to_dict() # Seriesをdictに変換
            date = meeting.get('日付')
            title = meeting.get('タイトル')
            if date and title and (date, title) not in attended_events:
                # 日付の形式を 'YYYY/MM/DD' に統一し、datetimeオブジェクトに変換可能か確認
                try:
                    meeting_date_obj = datetime.strptime(date, '%Y/%m/%d')
                    unregistered_meetings.append((meeting_date_obj, meeting)) # 日付オブジェクトと元データを保存
                except ValueError:
                    print(f"DEBUG: 無効な日付形式をスキップしました: {date}")
                    continue

        # 日付でソートし、最も近い未登録スケジュールを抽出
        unregistered_meetings.sort(key=lambda x: x[0]) # 日付オブジェクトでソート

        if not unregistered_meetings:
            line_bot_api_messaging.reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[TextMessage(text="現在、登録可能な未参加予定のスケジュールはありません。\n「参加予定一覧」で現在の参加予定状況を確認できます。")]
                )
            )
            user_sessions.pop(user_id, None)
            return

        # 次に処理すべきイベントをセッションに保存
        user_sessions[user_id] = {
            'state': SessionState.ASKING_ATTENDANCE_STATUS,
            'data': {
                'unregistered_events': [
                    {'date': meeting[1].get('日付'), 'title': meeting[1].get('タイトル')}
                    for meeting in unregistered_meetings
                ]
            }
        }

        # 最初の未登録イベントを取得
        current_event = user_sessions[user_id]['data']['unregistered_events'][0]

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
        user_sessions.pop(user_id, None)


def handle_attendance_qa_response(user_id, user_display_name, user_message, reply_token, line_bot_api_messaging: MessagingApi, user_sessions, current_session):
    """
    参加予定登録Q&Aフロー中のユーザー応答を処理する。
    """
    state = current_session['state']
    data = current_session['data']
    messages = []

    print(f"DEBUG: Handling attendance Q&A. State: {state}, Message: {user_message}")

    if state == SessionState.ASKING_ATTENDANCE_STATUS:
        status = user_message
        if status in ['〇', '△', '×']:
            unregistered_events = data.get('unregistered_events', [])

            if not unregistered_events:
                messages.append(TextMessage(text="処理すべきイベントが見つかりませんでした。\n「参加予定登録」と入力してやり直してください。"))
                user_sessions.pop(user_id, None)
                line_bot_api_messaging.reply_message(ReplyMessageRequest(reply_token=reply_token, messages=messages))
                return

            current_event = unregistered_events[0]
            event_date = current_event['date']
            event_title = current_event['title']

            try:
                # 修正: update_or_add_attendee の引数順序と数を確認し、utils.pyの定義に合わせる
                # update_or_add_attendee(date, title, user_id, username, attendance_status, notes="")
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

                    unregistered_events.pop(0) 

                    if unregistered_events:
                        next_event = unregistered_events[0]
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
                        user_sessions.pop(user_id, None)

                else:
                    messages.append(TextMessage(text=f"参加予定登録中にエラーが発生しました: {msg}"))
                    user_sessions.pop(user_id, None)
            except Exception as e:
                messages.append(TextMessage(text=f"参加予定登録中に予期せぬエラーが発生しました: {e}"))
                user_sessions.pop(user_id, None)
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
        user_sessions.pop(user_id, None)


    line_bot_api_messaging.reply_message(
        ReplyMessageRequest(
            reply_token=reply_token,
            messages=messages
        )
    )
