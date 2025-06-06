import os
from datetime import datetime
import re
# LINE Bot SDK v3 のインポート
from linebot.v3.messaging import ( # MessagingApiとReplyMessageRequestを直接インポート
    MessagingApi,
    ReplyMessageRequest,
    TextMessage # TextMessageを直接インポート
)
# 追加: Quick Reply 関連のインポート
from linebot.v3.messaging.models import QuickReply, QuickReplyItem, MessageAction

from config import Config, SessionState
# ★★★ここを修正します★★★
# 修正箇所: add_record を add_schedule_record と sort_sheet_by_date に変更
from google_sheets.utils import get_all_records, add_schedule_record, delete_record, update_record, sort_sheet_by_date
from google_sheets.api_client import get_google_sheets_client # 追加
# 修正: attendance_commands モジュールからではなく、qna/attendance_qna モジュールから start_attendance_qa 関数をインポート
from line_handlers.qna.attendance_qna import start_attendance_qa

# --- Google Sheetsクライアントの初期化 ---
# utils.py と同様に、schedule_commands.py 内でも gc を利用できるよう宣言します。
# 実際の運用では、gc はアプリケーションの起動時に一度だけ認証され、
# その後、必要な関数に引数として渡されるか、グローバルにアクセス可能な状態にすることが推奨されます。
# ここでは、utils.py の import と同様に、gspread の認証を想定した gc 変数を定義します。
# この gc は、main.py など、アプリケーションのエントリポイントで実際に認証され、
# 各関数に渡されることを前提とします。
# 現状のコードでは、main.pyからgcが渡されていないため、
# ここで仮にNoneを定義しておきます。実際の運用では適切なgcオブジェクトが渡されるようにしてください。
# 修正箇所: gc = None を get_google_sheets_client() の呼び出しに変更
gc = get_google_sheets_client() # gcを適切に初期化

# --- スケジュール登録フロー ---

def start_schedule_registration(user_id, reply_token, line_bot_api_messaging: MessagingApi, user_sessions):
    """
    スケジュール登録の開始処理
    """
    user_sessions[user_id] = {'state': SessionState.ASKING_TITLE, 'data': {}}
    # MessagingTextMessage の代わりに TextMessage を使用
    messages = [TextMessage(text='新しいスケジュールのタイトルを教えてください。')]
    line_bot_api_messaging.reply_message(
        ReplyMessageRequest(
            reply_token=reply_token,
            messages=messages
        )
    )
    print(f"DEBUG: Started schedule registration for user {user_id}")

def handle_schedule_registration(user_id, user_message, reply_token, line_bot_api_messaging: MessagingApi, user_sessions, current_session):
    """
    スケジュール登録フロー中のユーザー応答を処理
    """
    state = current_session['state']
    data = current_session['data']
    messages = []

    print(f"DEBUG: Handling schedule registration. State: {state}, Message: {user_message}")

    if state == SessionState.ASKING_TITLE:
        data['title'] = user_message
        current_session['state'] = SessionState.ASKING_DATE
        # MessagingTextMessage の代わりに TextMessage を使用
        messages.append(TextMessage(text='開催日を教えてください。例: 2025/06/15'))
    elif state == SessionState.ASKING_DATE:
        if not re.match(r'^\d{4}/\d{2}/\d{2}$', user_message):
            # MessagingTextMessage の代わりに TextMessage を使用
            messages.append(TextMessage(text='日付の形式が正しくありません。YYYY/MM/DD形式で入力してください。例: 2025/06/15'))
        else:
            data['date'] = user_message
            current_session['state'] = SessionState.ASKING_TIME
            # MessagingTextMessage の代わりに TextMessage を使用
            messages.append(TextMessage(text='開催時間を教えてください。例: 10:00 (時間のみでも可)'))
    elif state == SessionState.ASKING_TIME:
        # 時間の正規表現をより厳密に HH:MM または HH の形式に調整
        # 例: '10:30' はOK, '10' はOK, '1030' はNG
        if not re.match(r'^([01]?[0-9]|2[0-3])(:[0-5][0-9])?$', user_message):
            # MessagingTextMessage の代わりに TextMessage を使用
            messages.append(TextMessage(text='時間の形式が正しくありません。例: 10:00 または 10'))
        else:
            data['time'] = user_message
            current_session['state'] = SessionState.ASKING_DURATION
            # MessagingTextMessage の代わりに TextMessage を使用
            messages.append(TextMessage(text='所要時間を教えてください（例: 2時間, 30分, 1時間半など）。'))
    elif state == SessionState.ASKING_DURATION:
        data['duration'] = user_message
        current_session['state'] = SessionState.ASKING_LOCATION
        # MessagingTextMessage の代わりに TextMessage を使用
        messages.append(TextMessage(text='開催場所を教えてください。'))
    elif state == SessionState.ASKING_LOCATION:
        data['location'] = user_message
        current_session['state'] = SessionState.ASKING_DETAIL
        # MessagingTextMessage の代わりに TextMessage を使用
        messages.append(TextMessage(text='詳細情報があれば教えてください（例: 持ち物、服装など）。'))
    elif state == SessionState.ASKING_DETAIL:
        data['detail'] = user_message
        current_session['state'] = SessionState.ASKING_DEADLINE
        # MessagingTextMessage の代わりに TextMessage を使用
        messages.append(TextMessage(text='出欠締切日を教えてください。例: 2025/06/10'))
    elif state == SessionState.ASKING_DEADLINE:
        if not re.match(r'^\d{4}/\d{2}/\d{2}$', user_message):
            # MessagingTextMessage の代わりに TextMessage を使用
            messages.append(TextMessage(text='締切日の形式が正しくありません。YYYY/MM/DD形式で入力してください。例: 2025/06/10'))
        else:
            data['deadline'] = user_message
            # 全ての情報が揃ったのでGoogle Sheetsに登録
            try:
                record = {
                    'タイトル': data['title'],
                    '日付': data['date'],
                    '時間': data['time'],
                    '尺': data['duration'], # 修正: '所要時間'から'尺'に変更
                    '場所': data['location'],
                    '詳細': data['detail'],
                    '申込締切日': data['deadline'] # 修正: '出欠締切日'から'申込締切日'に変更
                }
                # ★★★ここを修正します★★★
                # add_record の代わりに add_schedule_record を使用し、引数を調整
                add_schedule_record(
                    date=data['date'],
                    time=data['time'],
                    place=data['location'],
                    title=data['title'],
                    detail=data['detail'],
                    deadline=data['deadline'],
                    duration=data['duration'],
                    worksheet_name=Config.SCHEDULE_WORKSHEET_NAME # このworksheet_nameが「シート1」を指している想定
                )

                # ★★★ここを追加します★★★
                # 登録後にシートを日付で自動並べ替え
                sort_success, sort_message = sort_sheet_by_date(
                    date_column_name='日付',
                    worksheet_name=Config.SCHEDULE_WORKSHEET_NAME
                )

                if sort_success:
                    messages.append(TextMessage(text='スケジュールを登録し、シートを日付順に並べ替えました！'))
                else:
                    messages.append(TextMessage(text=f'スケジュールを登録しましたが、並べ替えに失敗しました: {sort_message}'))

                user_sessions.pop(user_id) # セッションをクリア
            except Exception as e:
                # MessagingTextMessage の代わりに TextMessage を使用
                messages.append(TextMessage(text=f'スケジュールの登録中にエラーが発生しました: {e}'))
                user_sessions.pop(user_id) # エラー時はセッションをクリア

    line_bot_api_messaging.reply_message(
        ReplyMessageRequest(
            reply_token=reply_token,
            messages=messages
        )
    )

def start_schedule_deletion(user_id, reply_token, line_bot_api_messaging: MessagingApi, user_sessions):
    """
    スケジュール削除の開始処理
    """
    user_sessions[user_id] = {'state': SessionState.DELETING_SCHEDULE_DATE, 'data': {}}
    # MessagingTextMessage の代わりに TextMessage を使用
    messages = [TextMessage(text='削除したいスケジュールの開催日を教えてください。例: 2025/06/15')]
    line_bot_api_messaging.reply_message(
        ReplyMessageRequest(
            reply_token=reply_token,
            messages=messages
        )
    )
    print(f"DEBUG: Started schedule deletion for user {user_id}")

def handle_schedule_deletion(user_id, user_message, reply_token, line_bot_api_messaging: MessagingApi, user_sessions, current_session):
    """
    スケジュール削除フロー中のユーザー応答を処理
    """
    state = current_session['state']
    data = current_session['data']
    messages = []

    print(f"DEBUG: Handling schedule deletion. State: {state}, Message: {user_message}")

    if state == SessionState.DELETING_SCHEDULE_DATE:
        if not re.match(r'^\d{4}/\d{2}/\d{2}$', user_message):
            # MessagingTextMessage の代わりに TextMessage を使用
            messages.append(TextMessage(text='日付の形式が正しくありません。YYYY/MM/DD形式で入力してください。例: 2025/06/15'))
        else:
            data['date'] = user_message
            current_session['state'] = SessionState.DELETING_SCHEDULE_TITLE
            # MessagingTextMessage の代わりに TextMessage を使用
            messages.append(TextMessage(text='次に、削除したいスケジュールのタイトルを教えてください。'))
    elif state == SessionState.DELETING_SCHEDULE_TITLE:
        data['title'] = user_message
        current_session['state'] = SessionState.AWAITING_DELETE_CONFIRMATION
        # MessagingTextMessage の代わりに TextMessage を使用
        messages.append(TextMessage(text=f"「{data['date']} {data['title']}」を削除しますか？\n「はい」または「いいえ」と入力してください。"))
    elif state == SessionState.AWAITING_DELETE_CONFIRMATION:
        if user_message == 'はい':
            try:
                # 修正箇所: gc引数を追加
                success = delete_record(gc, Config.SPREADSHEET_NAME, data['date'], data['title'], worksheet_name=Config.SCHEDULE_WORKSHEET_NAME)
                if success:
                    # MessagingTextMessage の代わりに TextMessage を使用
                    messages.append(TextMessage(text='スケジュールを削除しました。'))
                else:
                    # MessagingTextMessage の代わりに TextMessage を使用
                    messages.append(TextMessage(text='指定されたスケジュールは見つかりませんでした。'))
            except Exception as e:
                # MessagingTextMessage の代わりに TextMessage を使用
                messages.append(TextMessage(text=f'スケジュールの削除中にエラーが発生しました: {e}'))
            finally:
                user_sessions.pop(user_id) # セッションをクリア
        elif user_message == 'いいえ':
            # MessagingTextMessage の代わりに TextMessage を使用
            messages.append(TextMessage(text='スケジュール削除をキャンセルしました。'))
            user_sessions.pop(user_id) # セッションをクリア
        else:
            # MessagingTextMessage の代わりに TextMessage を使用
            messages.append(TextMessage(text='「はい」または「いいえ」で答えてください。'))

    line_bot_api_messaging.reply_message(
        ReplyMessageRequest(
            reply_token=reply_token,
            messages=messages
        )
    )

def start_schedule_editing(user_id, reply_token, line_bot_api_messaging: MessagingApi, user_sessions):
    """
    スケジュール編集の開始処理
    """
    user_sessions[user_id] = {'state': SessionState.EDITING_SCHEDULE_DATE, 'data': {}}
    # MessagingTextMessage の代わりに TextMessage を使用
    messages = [TextMessage(text='編集したいスケジュールの開催日を教えてください。例: 2025/06/15')]
    line_bot_api_messaging.reply_message(
        ReplyMessageRequest(
            reply_token=reply_token,
            messages=messages
        )
    )
    print(f"DEBUG: Started schedule editing for user {user_id}")

def handle_schedule_editing(user_id, user_message, reply_token, line_bot_api_messaging: MessagingApi, user_sessions, current_session):
    """
    スケジュール編集フロー中のユーザー応答を処理
    """
    state = current_session['state']
    data = current_session['data']
    messages = []

    print(f"DEBUG: Handling schedule editing. State: {state}, Message: {user_message}")

    if state == SessionState.EDITING_SCHEDULE_DATE:
        if not re.match(r'^\d{4}/\d{2}/\d{2}$', user_message):
            # MessagingTextMessage の代わりに TextMessage を使用
            messages.append(TextMessage(text='日付の形式が正しくありません。YYYY/MM/DD形式で入力してください。例: 2025/06/15'))
        else:
            data['date'] = user_message
            current_session['state'] = SessionState.EDITING_SCHEDULE_TITLE
            # MessagingTextMessage の代わりに TextMessage を使用
            messages.append(TextMessage(text='次に、編集したいスケジュールのタイトルを教えてください。'))
    elif state == SessionState.EDITING_SCHEDULE_TITLE:
        data['title'] = user_message

        # 既存のスケジュールを検索
        # 修正箇所: gc引数を追加
        all_schedules = get_all_records(gc, Config.SPREADSHEET_NAME, worksheet_name=Config.SCHEDULE_WORKSHEET_NAME)
        found_schedule = None
        for schedule in all_schedules:
            if schedule.get('日付') == data['date'] and schedule.get('タイトル') == data['title']:
                found_schedule = schedule
                break

        if found_schedule:
            data['original_schedule'] = found_schedule # 元のスケジュールデータを保存
            current_session['state'] = SessionState.SELECTING_EDIT_ITEM
            # 修正: valid_items のキー名をシートに合わせて変更
            messages.append(TextMessage(text='どの項目を編集しますか？ (タイトル, 日付, 時間, 尺, 場所, 詳細, 申込締切日)'))
        else:
            # MessagingTextMessage の代わりに TextMessage を使用
            messages.append(TextMessage(text='指定された日付とタイトルのスケジュールは見つかりませんでした。'))
            user_sessions.pop(user_id) # 見つからなければセッション終了

    elif state == SessionState.SELECTING_EDIT_ITEM:
        edit_item = user_message
        # 修正: valid_items のキー名をシートに合わせて変更
        valid_items = ['タイトル', '日付', '時間', '尺', '場所', '詳細', '申込締切日']
        if edit_item in valid_items:
            data['edit_item'] = edit_item
            current_session['state'] = SessionState.ASKING_NEW_VALUE
            # MessagingTextMessage の代わりに TextMessage を使用
            messages.append(TextMessage(text=f'{edit_item} の新しい値を入力してください。'))
        else:
            # MessagingTextMessage の代わりに TextMessage を使用
            messages.append(TextMessage(text='編集したい項目が正しくありません。「タイトル, 日付, 時間, 尺, 場所, 詳細, 申込締切日」の中から選んでください。'))

    elif state == SessionState.ASKING_NEW_VALUE:
        new_value = user_message
        edit_item = data['edit_item']

        # 日付や締切日の形式チェック
        # 修正: '出欠締切日' を '申込締切日' に変更
        if edit_item in ['日付', '申込締切日']:
            if not re.match(r'^\d{4}/\d{2}/\d{2}$', new_value):
                # MessagingTextMessage の代わりに TextMessage を使用
                messages.append(TextMessage(text=f'{edit_item} の形式が正しくありません。YYYY/MM/DD形式で入力してください。'))
                line_bot_api_messaging.reply_message(
                    ReplyMessageRequest(
                        reply_token=reply_token,
                        messages=messages
                    )
                )
                return

        # 時間の形式チェック
        if edit_item == '時間':
            # より厳密な正規表現に調整
            if not re.match(r'^([01]?[0-9]|2[0-3])(:[0-5][0-9])?$', new_value):
                # MessagingTextMessage の代わりに TextMessage を使用
                messages.append(TextMessage(text='時間の形式が正しくありません。例: 10:00 または 10'))
                line_bot_api_messaging.reply_message(
                    ReplyMessageRequest(
                        reply_token=reply_token,
                        messages=messages
                    )
                )
                return

        try:
            # 元のスケジュールタイトルと日付を使って更新
            original_date = data['date']
            original_title = data['title']

            # update_recordの呼び出し方を確認し、適切に修正
            # update_record(gc, spreadsheet_name, search_criteria, update_data, worksheet_name)
            # として定義されているため、引数の順序と型を合わせる
            search_criteria = {'日付': original_date, 'タイトル': original_title}
            update_data = {edit_item: new_value}

            # 修正箇所: gc引数を追加
            update_success = update_record(
                gc, # ここにgcを追加
                Config.SPREADSHEET_NAME,
                search_criteria,
                update_data,
                Config.SCHEDULE_WORKSHEET_NAME
            )

            if update_success:
                # MessagingTextMessage の代わりに TextMessage を使用
                messages.append(TextMessage(text=f'スケジュールを更新しました！'))
            else:
                # MessagingTextMessage の代わりに TextMessage を使用
                messages.append(TextMessage(text=f'スケジュールの更新に失敗しました。元のスケジュールが見つからないか、処理に問題がありました。'))

            user_sessions.pop(user_id) # セッションをクリア

        except Exception as e:
            # MessagingTextMessage の代わりに TextMessage を使用
            messages.append(TextMessage(text=f'スケジュールの更新中にエラーが発生しました: {e}'))
            user_sessions.pop(user_id) # エラー時はセッションをクリア

    line_bot_api_messaging.reply_message(
        ReplyMessageRequest(
            reply_token=reply_token,
            messages=messages
        )
    )


# list_schedules 関数に user_id と user_sessions 引数を追加
def list_schedules(user_id, reply_token, line_bot_api_messaging: MessagingApi, user_sessions):
    """
    「スケジュール一覧」コマンドの処理。
    """
    print(f"DEBUG: Executing list_schedules for user: {user_id}")
    try:
        # 修正箇所: gc引数を追加
        all_meetings = get_all_records(gc, Config.SPREADSHEET_NAME, worksheet_name=Config.SCHEDULE_WORKSHEET_NAME)

        schedule_list_text = "" # response_textをschedule_list_textに名称変更

        if all_meetings:
            # 日付とタイトルでソート
            sorted_meetings = sorted(all_meetings, key=lambda x: (x.get('日付', '9999/12/31'), x.get('タイトル', '')))

            schedule_list_text += "【登録済みのスケジュール一覧】\n\n"
            for meeting in sorted_meetings:
                title = meeting.get('タイトル', 'N/A')
                date = meeting.get('日付', 'N/A')
                time = meeting.get('時間', 'N/A')
                duration = meeting.get('尺', 'N/A') # 修正: '所要時間'から'尺'に変更
                location = meeting.get('場所', 'N/A')
                detail = meeting.get('詳細', 'N/A')
                deadline = meeting.get('申込締切日', 'N/A') # 修正: '出欠締切日'から'申込締切日'に変更

                schedule_list_text += (
                    f"タイトル: {title}\n"
                    f"日付: {date}\n"
                    f"時間: {time}\n"
                    f"所要時間: {duration}\n" # 所要時間を表示 (表示は所要時間でOK)
                    f"場所: {location}\n"
                    f"詳細: {detail}\n"
                    f"出欠締切日: {deadline}\n" # 出欠締切日を表示 (表示は出欠締切日でOK)
                    f"--------------------\n"
                )

            # 1つ目: スケジュール一覧のみ
            # schedule_list_textは既に上で作成されている
            # セッション状態を設定（出欠登録の意向確認待ち）
            user_sessions[user_id] = {'state': SessionState.ASKING_ATTENDANCE_INTENTION, 'data': {}}
            print(f"DEBUG: Asked attendance intention for user {user_id}")

            # 2つ目: 参加予定の質問のみ（Quick Reply付き）
            question_message = TextMessage(
                text="参加予定を入力しますか？",
                quick_reply=QuickReply(items=[
                    QuickReplyItem(action=MessageAction(label='はい', text='はい')),
                    QuickReplyItem(action=MessageAction(label='いいえ', text='いいえ'))
                ])
            )
            messages = [TextMessage(text=schedule_list_text), question_message]

        else:
            schedule_list_text = "現在、登録されているスケジュールはありません。\n「スケジュール登録」でイベントを作成してください。"
            # スケジュールがない場合は、意向確認は不要なのでセッション状態は変更しない
            messages = [TextMessage(text=schedule_list_text)] # スケジュールがない場合は1つのメッセージで応答

        line_bot_api_messaging.reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=messages
            )
        )
        print(f"DEBUG: Finished listing schedules for user {user_id}")

    except Exception as e:
        reply_text = f"スケジュール一覧の取得中にエラーが発生しました。\nエラー: {e}"
        print(f"Error processing schedule list: {e}")
        # MessagingTextMessage の代わりに TextMessage を使用
        messages = [TextMessage(text=reply_text)]
        line_bot_api_messaging.reply_message(
            ReplyMessageRequest(
                _あむよreply_token=reply_token,
                messages=messages
            )
        )
