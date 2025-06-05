import os
from datetime import datetime
import re
# LINE Bot SDK v3 のインポートに統一
from linebot.v3.messaging import (
    MessagingApi,
    ReplyMessageRequest,
    TextMessage # v3 の TextMessage を使用
)

from config import Config, SessionState
# インポート文を修正
from google_sheets.utils import get_all_records, update_or_add_attendee, delete_row_by_criteria

def start_attendance_editing(user_id, reply_token, line_bot_api_messaging: MessagingApi, user_sessions):
    """
    参加予定編集の開始処理
    """
    user_sessions[user_id] = {'state': SessionState.EDITING_ATTENDANCE_DATE, 'data': {}}
    messages = [TextMessage(text='編集したい参加予定の開催日を教えてください。例: 2025/06/15')]
    line_bot_api_messaging.reply_message(
        ReplyMessageRequest(
            reply_token=reply_token,
            messages=messages
        )
    )
    print(f"DEBUG: Started attendance editing for user {user_id}")

def handle_attendance_editing(user_id, user_display_name, user_message, reply_token, line_bot_api_messaging: MessagingApi, user_sessions, current_session):
    """
    参加予定編集フロー中のユーザー応答を処理
    """
    state = current_session['state']
    data = current_session['data']
    messages = []

    print(f"DEBUG: Handling attendance editing. State: {state}, Message: {user_message}")

    if state == SessionState.EDITING_ATTENDANCE_DATE:
        if not re.match(r'^\d{4}/\d{2}/\d{2}$', user_message):
            messages.append(TextMessage(text='日付の形式が正しくありません。YYYY/MM/DD形式で入力してください。例: 2025/06/15'))
        else:
            data['event_date'] = user_message
            current_session['state'] = SessionState.EDITING_ATTENDANCE_TITLE
            messages.append(TextMessage(text='次に、編集したい参加予定のタイトルを教えてください。'))
    elif state == SessionState.EDITING_ATTENDANCE_TITLE:
        data['event_title'] = user_message

        # Google Sheetsから該当の参加予定を検索
        # ATTENDEES_WORKSHEET_NAME を使用
        attendee_records = get_all_records(Config.SPREADSHEET_NAME, worksheet_name=Config.ATTENDEES_WORKSHEET_NAME)
        found_record = None
        for record in attendee_records:
            # ユーザーIDとイベント日時、タイトルで絞り込み
            # record.get('LINE ID') は、シートのヘッダーが 'LINE ID' であることを想定
            # record.get('イベント開催日') は、シートのヘッダーが 'イベント開催日' であることを想定
            # record.get('イベントタイトル') は、シートのヘッダーが 'イベントタイトル' であることを想定
            # utils.pyの update_or_add_attendee 内では '参加者ID', '日付', 'タイトル' が使われているため、
            # ここでの検索キーもそれに合わせるか、シートのヘッダー名を統一する必要がある。
            # 今回はシートのヘッダー名が異なる可能性を考慮し、以下のように記載
            if str(record.get('参加者ID')) == user_id and \
               str(record.get('日付')) == data['event_date'] and \
               str(record.get('タイトル')) == data['event_title']:
                found_record = record
                break

        if found_record:
            data['original_attendee_record'] = found_record
            current_session['state'] = SessionState.CONFIRM_ATTENDANCE_ACTION
            messages.append(TextMessage(text=f"「{data['event_date']} {data['event_title']}」の参加予定を見つけました。\nキャンセルしますか？ (はい/いいえ)"))
        else:
            messages.append(TextMessage(text='指定されたイベントの参加予定は見つかりませんでした。日付とタイトルを確認してください。'))
            user_sessions.pop(user_id) # 見つからなければセッション終了

    elif state == SessionState.CONFIRM_ATTENDANCE_ACTION:
        if user_message == 'はい': # キャンセルする場合
            try:
                # delete_row_by_criteria を使用し、criteria 辞書を渡す
                criteria = {
                    'タイトル': data['event_title'],
                    '日付': data['event_date'],
                    '参加者ID': user_id # ユーザーIDも条件に含める
                }
                success, msg = delete_row_by_criteria(
                    Config.SPREADSHEET_NAME,
                    criteria, # criteria 辞書を渡す
                    worksheet_index=1 # シート2 (参加者シート) を指定
                )
                if success:
                    messages.append(TextMessage(text='参加予定をキャンセルしました。'))
                else:
                    messages.append(TextMessage(text=f'参加予定のキャンセルに失敗しました: {msg}'))
            except Exception as e:
                messages.append(TextMessage(text=f'参加予定のキャンセル中にエラーが発生しました: {e}'))
            finally:
                user_sessions.pop(user_id) # セッションクリア
        elif user_message == 'いいえ': # 備考を編集する場合
            current_session['state'] = SessionState.EDITING_ATTENDANCE_NOTE
            messages.append(TextMessage(text='備考を編集しますか？ (はい/いいえ)'))
        else:
            messages.append(TextMessage(text='「はい」または「いいえ」で答えてください。'))

    elif state == SessionState.EDITING_ATTENDANCE_NOTE:
        if user_message == 'はい':
            current_session['state'] = SessionState.ASK_NEW_ATTENDANCE_NOTE
            messages.append(TextMessage(text='新しい備考を入力してください。'))
        elif user_message == 'いいえ':
            messages.append(TextMessage(text='備考の編集をスキップしました。'))
            current_session['state'] = SessionState.ASK_ANOTHER_ATTENDANCE_EDIT # 次の編集を尋ねるステップへ
            messages.append(TextMessage(text='他に編集したい予定はありますか？ (はい/いいえ)'))
        else:
            messages.append(TextMessage(text='「はい」または「いいえ」で答えてください。'))

    elif state == SessionState.ASK_NEW_ATTENDANCE_NOTE:
        new_remarks = user_message
        try:
            # update_or_add_attendee を使用して備考を更新
            # attendance_status には空文字列を渡すことで、備考のみを更新するように指示
            success, msg = update_or_add_attendee(
                Config.SPREADSHEET_NAME,
                data['event_title'],
                data['event_date'],
                user_display_name, # user_display_name
                user_id,
                "", # attendance_status は空文字列で渡す（備考のみ更新のため）
                new_remarks,
                Config.ATTENDEES_WORKSHEET_NAME # シート名を渡す
            )
            if success:
                messages.append(TextMessage(text='備考を更新しました。'))
            else:
                messages.append(TextMessage(text=f'備考の更新に失敗しました: {msg}'))
        except Exception as e:
            messages.append(TextMessage(text=f'備考の更新中にエラーが発生しました: {e}'))
        finally:
            current_session['state'] = SessionState.ASK_ANOTHER_ATTENDANCE_EDIT # 次の編集を尋ねるステップへ
            messages.append(TextMessage(text='他に編集したい予定はありますか？ (はい/いいえ)'))

    elif state == SessionState.ASK_ANOTHER_ATTENDANCE_EDIT:
        if user_message == 'はい':
            # 最初からやり直し
            user_sessions[user_id] = {'state': SessionState.EDITING_ATTENDANCE_DATE, 'data': {}}
            messages.append(TextMessage(text='編集したい参加予定の開催日を教えてください。例: 2025/06/15'))
        elif user_message == 'いいえ':
            messages.append(TextMessage(text='参加予定の編集を終了します。'))
            user_sessions.pop(user_id) # セッションクリア
        else:
            messages.append(TextMessage(text='「はい」または「いいえ」で答えてください。'))

    line_bot_api_messaging.reply_message(
        ReplyMessageRequest(
            reply_token=reply_token,
            messages=messages
        )
    )

def list_my_planned_events(user_id, user_display_name, reply_token, line_bot_api_messaging: MessagingApi):
    """
    指定されたユーザーIDの参加予定イベント一覧を表示する。
    """
    print(f"DEBUG: Executing list_my_planned_events for user: {user_id} ({user_display_name})")
    try:
        # Config.ATTENDEES_WORKSHEET_NAME を使用
        all_attendees = get_all_records(Config.SPREADSHEET_NAME, worksheet_name=Config.ATTENDEES_WORKSHEET_NAME)

        my_planned_events = []
        for record in all_attendees:
            # ユーザーIDとユーザー名が一致し、かつ出欠が「〇」または「△」のものを抽出
            # ここもシートのヘッダー名とコード内でのキー名を合わせる必要がある
            if record.get('参加者ID') == user_id and \
               record.get('参加者名') == user_display_name and \
               record.get('出欠') in ['〇', '△']:
                my_planned_events.append(record)

        if my_planned_events:
            # 日付でソート
            # イベント開催日ではなく、日付カラムでソート
            sorted_events = sorted(my_planned_events, key=lambda x: (x.get('日付', '9999/12/31'), x.get('タイトル', '')))

            response_text = f"【{user_display_name}さんの参加予定イベント一覧】\n\n"
            for event in sorted_events:
                event_title = event.get('タイトル', 'N/A')
                event_date = event.get('日付', 'N/A')
                attendance_status = event.get('出欠', 'N/A')
                remarks = event.get('備考', 'N/A')

                response_text += (
                    f"タイトル: {event_title}\n"
                    f"開催日: {event_date}\n"
                    f"出欠: {attendance_status}\n"
                    f"備考: {remarks}\n"
                    f"--------------------\n"
                )
            messages = [TextMessage(text=response_text)]
        else:
            messages = [TextMessage(text="現在、あなたの参加予定イベントはありません。\n「出欠登録」でイベントに参加登録してください。")]

        line_bot_api_messaging.reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=messages
            )
        )
        print(f"DEBUG: Finished listing planned events for user {user_id}")

    except Exception as e:
        reply_text = f"参加予定イベント一覧の取得中にエラーが発生しました。\nエラー: {e}"
        print(f"Error processing my planned events list: {e}")
        messages = [TextMessage(text=reply_text)]
        line_bot_api_messaging.reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=messages
            )
        )

def list_participants(user_id, reply_token, line_bot_api_messaging: MessagingApi):
    """
    「参加者一覧」コマンドの処理。
    イベントごとの参加者情報を表示。
    """
    print(f"DEBUG: Executing list_participants for user: {user_id}")
    try:
        # Config.ATTENDEES_WORKSHEET_NAME を使用
        all_attendees = get_all_records(Config.SPREADSHEET_NAME, worksheet_name=Config.ATTENDEES_WORKSHEET_NAME)

        if not all_attendees:
            messages = [TextMessage(text="現在、登録されている参加者情報はありません。\nまずは「出欠登録」で参加者情報を登録してください。")]
            line_bot_api_messaging.reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=messages
                )
            )
            return

        # イベントごとに参加者をまとめる
        events_with_attendees = {}
        for record in all_attendees:
            event_date = record.get('日付', '不明な日付') # イベント開催日ではなく日付
            event_title = record.get('タイトル', '不明なタイトル') # イベントタイトルではなくタイトル
            attendee_name = record.get('参加者名', '不明な参加者')
            attendance_status = record.get('出欠', '不明')
            remarks = record.get('備考', '')

            event_key = (event_date, event_title)
            if event_key not in events_with_attendees:
                events_with_attendees[event_key] = {'attendees': []}

            events_with_attendees[event_key]['attendees'].append({
                'name': attendee_name,
                'status': attendance_status,
                'remarks': remarks
            })

        # 日付とタイトルでソート
        sorted_events_keys = sorted(events_with_attendees.keys(), key=lambda x: (x[0], x[1]))

        response_text = "【イベント別参加者一覧】\n\n"
        for event_date, event_title in sorted_events_keys:
            attendees_info = events_with_attendees[(event_date, event_title)]['attendees']

            response_text += f"◆イベント: {event_date} {event_title}\n"
            response_text += f"参加者数: {len(attendees_info)}名\n"

            for attendee in attendees_info:
                response_text += f"　- {attendee['name']} ({attendee['status']})"
                if attendee['remarks']:
                    response_text += f" 備考: {attendee['remarks']}"
                response_text += "\n"
            response_text += "--------------------\n"

        messages = [TextMessage(text=response_text)]
        line_bot_api_messaging.reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=messages
            )
        )
        print(f"DEBUG: Finished listing participants for user {user_id}")

    except Exception as e:
        reply_text = f"参加者一覧の取得中にエラーが発生しました。\nエラー: {e}"
        print(f"Error processing participants list: {e}")
        messages = [TextMessage(text=reply_text)]
        line_bot_api_messaging.reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=messages
            )
        )

