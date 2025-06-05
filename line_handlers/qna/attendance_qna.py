import os
# LINE Bot SDK v3 のモデルをインポート
from linebot.v3.messaging.models import TextMessage as TextSendMessage
from linebot.v3.messaging.models import QuickReply, QuickReplyItem, MessageAction
from linebot.v3.messaging import ReplyMessageRequest
from linebot.v3.messaging import MessagingApi # MessagingApi をインポートリストに追加

from config import Config, SessionState
from google_sheets.utils import get_all_records, update_or_add_attendee, get_attendees_for_user
from google_sheets.api_client import get_google_sheets_client
from datetime import datetime

# gc の初期化
gc = get_google_sheets_client()

def start_attendance_qa(user_id, reply_token, line_bot_api_messaging: MessagingApi, user_sessions):
    """
    「出欠登録」コマンドの開始処理。
    ユーザーに未登録のイベントを提示し、出欠を尋ねる。
    """
    try:
        all_meetings = get_all_records(gc, Config.SPREADSHEET_NAME, Config.SCHEDULE_WORKSHEET_NAME)

        if not all_meetings:
            line_bot_api_messaging.reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[TextSendMessage(text="現在、登録されているスケジュールはありません。\nまずは「スケジュール登録」でイベントを作成してください。")]
                )
            )
            user_sessions.pop(user_id, None)
            return

        # ユーザーの既存の参加予定を取得
        user_attendees = get_attendees_for_user(gc, Config.SPREADSHEET_NAME, Config.ATTENDEES_WORKSHEET_NAME, user_id)
        attended_events = {(att.get('日付'), att.get('タイトル')) for att in user_attendees}

        # 未登録のスケジュールのみをフィルタリング
        unregistered_meetings = []
        for meeting in all_meetings:
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
                    messages=[TextSendMessage(text="現在、登録可能な未出欠のスケジュールはありません。\n「参加予定一覧」で現在の出欠状況を確認できます。")]
                )
            )
            user_sessions.pop(user_id, None)
            return

        # 次に処理すべきイベントをセッションに保存
        # 未処理のイベントリスト全体を保存し、完了したものはリストから削除していく方式に変更
        # 日付オブジェクトはJSONシリアライズできないため、日付文字列に戻して保存
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

        response_text = f"こちらのイベントの出欠を登録します。\n\n{current_event['date']} の「{current_event['title']}」\n\n出欠を教えてください（〇, △, ×）"

        line_bot_api_messaging.reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[TextSendMessage(
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
        error_msg = f"出欠登録の開始中にエラーが発生しました: {e}"
        print(f"ERROR: {error_msg}")
        line_bot_api_messaging.reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[TextSendMessage(text=error_msg)]
            )
        )
        user_sessions.pop(user_id, None)


def handle_attendance_qa_response(user_id, user_display_name, user_message, reply_token, line_bot_api_messaging: MessagingApi, user_sessions, current_session):
    """
    出欠登録Q&Aフロー中のユーザー応答を処理する。
    """
    state = current_session['state']
    data = current_session['data']
    messages = []

    print(f"DEBUG: Handling attendance Q&A. State: {state}, Message: {user_message}")

    # ASKING_ATTENDANCE_TARGET_EVENT の処理は start_attendance_qa でスキップされるため、
    # ここでは ASKING_ATTENDANCE_STATUS の処理に直接進む。
    # 以前のASING_ATTENDANCE_TARGET_EVENTのロジックは削除またはコメントアウト。

    if state == SessionState.ASKING_ATTENDANCE_STATUS:
        status = user_message
        if status in ['〇', '△', '×']:
            unregistered_events = data.get('unregistered_events', [])

            if not unregistered_events:
                # ここに到達することは通常ないが、念のため
                messages.append(TextSendMessage(text="処理すべきイベントが見つかりませんでした。\n「出欠登録」と入力してやり直してください。"))
                user_sessions.pop(user_id, None)
                line_bot_api_messaging.reply_message(ReplyMessageRequest(reply_token=reply_token, messages=messages))
                return

            # 現在処理中のイベントはリストの先頭
            current_event = unregistered_events[0]
            event_date = current_event['date']
            event_title = current_event['title']

            try:
                # 問題1: 引数エラーの修正
                # user_display_name は update_or_add_attendee に渡さない
                success, msg = update_or_add_attendee(
                    gc,
                    Config.SPREADSHEET_NAME,
                    user_id,
                    event_date,
                    event_title,
                    status,
                    data.get('attendance_remarks', ''), # 備考は空文字として初期化、または既存のデータがあればそれを使用
                    Config.ATTENDEES_WORKSHEET_NAME
                )
                if success:
                    messages.append(TextSendMessage(text=f"{event_date} の「{event_title}」の出欠を登録しました！"))

                    # 処理したイベントをリストから削除
                    unregistered_events.pop(0) 

                    if unregistered_events:
                        # 次の未登録イベントがあれば続けて表示
                        next_event = unregistered_events[0]
                        messages.append(TextSendMessage(
                            text=f"続けてこちらのイベントの出欠を登録します。\n\n{next_event['date']} の「{next_event['title']}」\n\n出欠を教えてください（〇, △, ×）",
                            quick_reply=QuickReply(items=[
                                QuickReplyItem(action=MessageAction(label='〇', text='〇')),
                                QuickReplyItem(action=MessageAction(label='△', text='△')),
                                QuickReplyItem(action=MessageAction(label='×', text='×'))
                            ])
                        ))
                    else:
                        # 全ての未登録イベントの処理が完了
                        messages.append(TextSendMessage(text="全ての未登録イベントの出欠登録が完了しました！\nありがとうございました。"))
                        user_sessions.pop(user_id, None) # 全て完了したらセッションをクリア

                else:
                    messages.append(TextSendMessage(text=f"参加予定登録中にエラーが発生しました: {msg}"))
                    user_sessions.pop(user_id, None) # エラー時もセッションをクリア
            except Exception as e:
                messages.append(TextSendMessage(text=f"参加予定登録中に予期せぬエラーが発生しました: {e}"))
                user_sessions.pop(user_id, None) # エラー時もセッションをクリア
        else:
            messages.append(TextSendMessage(text="参加予定は「〇」「△」「×」のいずれかで入力してください。",
                quick_reply=QuickReply(items=[
                    QuickReplyItem(action=MessageAction(label='〇', text='〇')),
                    QuickReplyItem(action=MessageAction(label='△', text='△')),
                    QuickReplyItem(action=MessageAction(label='×', text='×'))
                ])
            ))
    else:
        # 想定外の状態の場合、セッションをクリアして再開を促す
        messages.append(TextSendMessage(text="現在、出欠登録の処理が中断されているようです。\n「出欠登録」と入力して最初からやり直してください。"))
        user_sessions.pop(user_id, None)


    line_bot_api_messaging.reply_message(
        ReplyMessageRequest(
            reply_token=reply_token,
            messages=messages
        )
    )

