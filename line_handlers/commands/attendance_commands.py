import pandas as pd
from datetime import datetime
from linebot.v3.messaging import MessagingApi, ReplyMessageRequest, TextMessage

from config import Config, SessionState
from google_sheets.utils import (
    get_all_records,
    update_or_add_attendee,
    delete_row_by_criteria
)
# utils/session_managerからセッション操作関数をインポート
from utils.session_manager import get_user_session_data, set_user_session_data, delete_user_session_data


# 参加予定一覧表示（ユーザーのIDに紐づく参加予定）
def list_user_attendees(user_id, reply_token, line_bot_api_messaging: MessagingApi):
    all_attendees_df = get_all_records(Config.GOOGLE_SHEETS_ATTENDEES_WORKSHEET_NAME)

    if all_attendees_df.empty:
        reply_message = "登録されている参加予定はありません。"
    else:
        # ユーザーIDでフィルタリング
        user_attendees_df = all_attendees_df[all_attendees_df['ユーザーID'] == user_id]

        if user_attendees_df.empty:
            reply_message = "あなたの参加予定は登録されていません。"
        else:
            reply_message = "【あなたの参加予定一覧】\n"
            # 日付でソート（日付がdatetime型であると仮定）
            user_attendees_df = user_attendees_df.sort_values(by='日付', ascending=True)
            for index, row in user_attendees_df.iterrows():
                date_str = row['日付'].strftime('%Y/%m/%d') if pd.notna(row['日付']) else '日付未定'
                reply_message += f"日付: {date_str}, タイトル: {row['タイトル']}\n"
                reply_message += f"  出欠: {row.get('出欠', '未回答')}, 備考: {row.get('備考', 'なし')}\n\n"

    line_bot_api_messaging.reply_message(
        ReplyMessageRequest(
            reply_token=reply_token,
            messages=[TextMessage(text=reply_message)]
        )
    )

# 参加者一覧表示（イベントごとの参加者）
def list_attendees(user_id, reply_token, line_bot_api_messaging: MessagingApi):
    all_attendees_df = get_all_records(Config.GOOGLE_SHEETS_ATTENDEES_WORKSHEET_NAME)

    if all_attendees_df.empty:
        reply_message = "登録されている参加者情報はありません。"
    else:
        reply_message = "【参加者一覧】\n"
        # 日付とタイトルでグループ化し、参加者人数と参加者名を表示
        # 日付をdatetime型に変換し、NaNを除外してからグループ化
        all_attendees_df['日付_dt'] = pd.to_datetime(all_attendees_df['日付'], errors='coerce')
        grouped_attendees = all_attendees_df[pd.notna(all_attendees_df['日付_dt'])].groupby(['日付_dt', 'タイトル'])

        if grouped_attendees.empty:
             reply_message = "登録されている参加者情報はありません。" # 日付が無効なデータしかない場合
        else:
            for (date, title), group in grouped_attendees:
                date_str = date.strftime('%Y/%m/%d')
                attendee_count = len(group)
                # 'ユーザーID' または '参加者名' カラムを使用
                # 現状は'ユーザーID'を想定、必要に応じて'参加者名'に変更
                attendee_names = ", ".join(group['ユーザーID'].tolist()) 

                reply_message += f"日付: {date_str}, タイトル: {title}\n"
                reply_message += f"  参加者人数: {attendee_count}\n"
                reply_message += f"  参加者名: {attendee_names}\n\n"

    line_bot_api_messaging.reply_message(
        ReplyMessageRequest(
            reply_token=reply_token,
            messages=[TextMessage(text=reply_message)]
        )
    )


# 参加予定編集開始
def start_attendee_edit(user_id, reply_token, line_bot_api_messaging: MessagingApi):
    SessionState.set_state(user_id, SessionState.ASKING_ATTENDEE_DATE)
    set_user_session_data(user_id, Config.SESSION_DATA_KEY, {'ユーザーID': user_id})
    line_bot_api_messaging.reply_message(
        ReplyMessageRequest(
            reply_token=reply_token,
            messages=[TextMessage(text="編集したい参加予定の日付をYYYY/MM/DD形式で入力してください。\n例: 2025/06/15")]
        )
    )

# 参加予定編集の次のステップ
def process_attendee_edit_step(user_id, message_text, reply_token, line_bot_api_messaging: MessagingApi):
    current_state = SessionState.get_state(user_id)
    session_data = get_user_session_data(user_id, Config.SESSION_DATA_KEY) or {}

    if current_state == SessionState.ASKING_ATTENDEE_DATE:
        try:
            pd.to_datetime(message_text, errors='raise')
            session_data['日付'] = message_text
            set_user_session_data(user_id, Config.SESSION_DATA_KEY, session_data)
            SessionState.set_state(user_id, SessionState.ASKING_ATTENDEE_TITLE)
            line_bot_api_messaging.reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[TextMessage(text="次に、編集したい参加予定のタイトルを入力してください。")]
                )
            )
        except ValueError:
            line_bot_api_messaging.reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[TextMessage(text="日付の形式が正しくありません。YYYY/MM/DD形式で入力してください。\n例: 2025/06/15")]
                )
            )
    elif current_state == SessionState.ASKING_ATTENDEE_TITLE:
        session_data['タイトル'] = message_text
        set_user_session_data(user_id, Config.SESSION_DATA_KEY, session_data)

        # 該当する参加予定が存在するか確認
        all_attendees = get_all_records(Config.GOOGLE_SHEETS_ATTENDEES_WORKSHEET_NAME)
        # 日付を正規化して比較
        try:
            search_date = pd.to_datetime(session_data['日付']).normalize()
        except ValueError:
            line_bot_api_messaging.reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[TextMessage(text="日付の形式が正しくありません。最初からやり直してください。")]
                )
            )
            SessionState.set_state(user_id, SessionState.NONE)
            delete_user_session_data(user_id, Config.SESSION_DATA_KEY)
            return

        matching_attendees = all_attendees[
            (all_attendees['ユーザーID'] == user_id) &
            (pd.notna(all_attendees['日付']) & (all_attendees['日付'].dt.normalize() == search_date)) &
            (all_attendees['タイトル'] == session_data['タイトル'])
        ]

        if not matching_attendees.empty:
            SessionState.set_state(user_id, SessionState.ASKING_ATTENDEE_CONFIRM_CANCEL)
            line_bot_api_messaging.reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[TextMessage(text="この参加予定をキャンセルしますか？（はい/いいえ）\n「いいえ」の場合、備考を編集します。")]
                )
            )
        else:
            SessionState.set_state(user_id, SessionState.NONE)
            delete_user_session_data(user_id, Config.SESSION_DATA_KEY)
            line_bot_api_messaging.reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[TextMessage(text="指定された参加予定は見つかりませんでした。最初からやり直してください。")]
                )
            )
    elif current_state == SessionState.ASKING_ATTENDEE_CONFIRM_CANCEL:
        if message_text.lower() == 'はい':
            # 参加予定を削除
            criteria = {
                'ユーザーID': user_id,
                '日付': session_data['日付'],
                'タイトル': session_data['タイトル']
            }
            if delete_row_by_criteria(Config.GOOGLE_SHEETS_ATTENDEES_WORKSHEET_NAME, criteria):
                reply_message = "参加予定をキャンセルしました。\n他に編集したい予定はありますか？（はい/いいえ）"
                SessionState.set_state(user_id, SessionState.ASKING_FOR_ANOTHER_ATTENDEE_EDIT)
            else:
                reply_message = "参加予定のキャンセルに失敗しました。最初からやり直してください。"
                SessionState.set_state(user_id, SessionState.NONE)
            delete_user_session_data(user_id, Config.SESSION_DATA_KEY)
            line_bot_api_messaging.reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[TextMessage(text=reply_message)]
                )
            )
        else: # 'いいえ' の場合、備考編集へ
            SessionState.set_state(user_id, SessionState.ASKING_ATTENDEE_EDIT_NOTES)
            line_bot_api_messaging.reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[TextMessage(text="新しい備考を入力してください。（ない場合は「なし」）")]
                )
            )
    elif current_state == SessionState.ASKING_ATTENDEE_EDIT_NOTES:
        new_notes = message_text
        session_data['備考'] = new_notes

        # 参加者情報を更新（備考のみ）
        if update_or_add_attendee(session_data): # update_or_add_attendeeは既存があれば更新する
            reply_message = "備考を更新しました。\n他に編集したい予定はありますか？（はい/いいえ）"
            SessionState.set_state(user_id, SessionState.ASKING_FOR_ANOTHER_ATTENDEE_EDIT)
        else:
            reply_message = "備考の更新に失敗しました。最初からやり直してください。"
            SessionState.set_state(user_id, SessionState.NONE)
        delete_user_session_data(user_id, Config.SESSION_DATA_KEY)
        line_bot_api_messaging.reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[TextMessage(text=reply_message)]
            )
        )
    elif current_state == SessionState.ASKING_FOR_ANOTHER_ATTENDEE_EDIT:
        if message_text.lower() == 'はい':
            start_attendee_edit(user_id, reply_token, line_bot_api_messaging)
        else:
            SessionState.set_state(user_id, SessionState.NONE)
            delete_user_session_data(user_id, Config.SESSION_DATA_KEY)
            line_bot_api_messaging.reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[TextMessage(text="参加予定編集を終了します。")]
                )
            )

# 参加予定登録開始
def start_attendee_registration(user_id, reply_token, line_bot_api_messaging: MessagingApi):
    SessionState.set_state(user_id, SessionState.ASKING_ATTENDEE_REGISTRATION_DATE)
    set_user_session_data(user_id, Config.SESSION_DATA_KEY, {'ユーザーID': user_id})
    line_bot_api_messaging.reply_message(
        ReplyMessageRequest(
            reply_token=reply_token,
            messages=[TextMessage(text="参加したいスケジュールの日付をYYYY/MM/DD形式で入力してください。\n例: 2025/06/15")]
        )
    )

# 参加予定登録の次のステップ
def process_attendee_registration_step(user_id, message_text, reply_token, line_bot_api_messaging: MessagingApi):
    current_state = SessionState.get_state(user_id)
    session_data = get_user_session_data(user_id, Config.SESSION_DATA_KEY) or {}

    if current_state == SessionState.ASKING_ATTENDEE_REGISTRATION_DATE:
        try:
            pd.to_datetime(message_text, errors='raise')
            session_data['日付'] = message_text
            set_user_session_data(user_id, Config.SESSION_DATA_KEY, session_data)
            SessionState.set_state(user_id, SessionState.ASKING_ATTENDEE_REGISTRATION_TITLE)
            line_bot_api_messaging.reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[TextMessage(text="次に、参加したいスケジュールのタイトルを入力してください。")]
                )
            )
        except ValueError:
            line_bot_api_messaging.reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[TextMessage(text="日付の形式が正しくありません。YYYY/MM/DD形式で入力してください。\n例: 2025/06/15")]
                )
            )
    elif current_state == SessionState.ASKING_ATTENDEE_REGISTRATION_TITLE:
        session_data['タイトル'] = message_text
        set_user_session_data(user_id, Config.SESSION_DATA_KEY, session_data)
        SessionState.set_state(user_id, SessionState.ASKING_ATTENDEE_STATUS)
        line_bot_api_messaging.reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[TextMessage(text="出欠を入力してください。（例: 〇、✕、△）")]
            )
        )
    elif current_state == SessionState.ASKING_ATTENDEE_STATUS:
        attendee_status = message_text
        if attendee_status in ['〇', '○', 'x', 'X', '✕', '△', '▲']: # 許容される出欠の文字
            session_data['出欠'] = attendee_status
            set_user_session_data(user_id, Config.SESSION_DATA_KEY, session_data)
            SessionState.set_state(user_id, SessionState.ASKING_ATTENDEE_NOTES)
            line_bot_api_messaging.reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[TextMessage(text="備考を入力してください。（ない場合は「なし」）")]
                )
            )
        else:
            line_bot_api_messaging.reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[TextMessage(text="出欠は「〇」「✕」「△」のいずれかで入力してください。")]
                )
            )
    elif current_state == SessionState.ASKING_ATTENDEE_NOTES:
        session_data['備考'] = message_text
        set_user_session_data(user_id, Config.SESSION_DATA_KEY, session_data)
        SessionState.set_state(user_id, SessionState.ASKING_CONFIRM_ATTENDEE_REGISTRATION)

        confirm_message = "以下の内容で参加予定を登録します。よろしいですか？\n"
        for key, value in session_data.items():
            confirm_message += f"{key}: {value}\n"
        confirm_message += "はい / いいえ"

        line_bot_api_messaging.reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[TextMessage(text=confirm_message)]
            )
        )
    elif current_state == SessionState.ASKING_CONFIRM_ATTENDEE_REGISTRATION:
        if message_text.lower() == 'はい':
            if update_or_add_attendee(session_data): # 新規登録も更新もこの関数で対応
                reply_message = "参加予定を登録しました。\n他に登録したい参加予定はありますか？（はい/いいえ）"
                SessionState.set_state(user_id, SessionState.ASKING_FOR_ANOTHER_ATTENDEE_REGISTRATION)
            else:
                reply_message = "参加予定の登録に失敗しました。最初からやり直してください。"
                SessionState.set_state(user_id, SessionState.NONE)
            delete_user_session_data(user_id, Config.SESSION_DATA_KEY)
            line_bot_api_messaging.reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[TextMessage(text=reply_message)]
                )
            )
        else:
            SessionState.set_state(user_id, SessionState.NONE)
            delete_user_session_data(user_id, Config.SESSION_DATA_KEY)
            line_bot_api_messaging.reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[TextMessage(text="参加予定登録をキャンセルしました。")]
                )
            )
    elif current_state == SessionState.ASKING_FOR_ANOTHER_ATTENDEE_REGISTRATION:
        if message_text.lower() == 'はい':
            start_attendee_registration(user_id, reply_token, line_bot_api_messaging)
        else:
            SessionState.set_state(user_id, SessionState.NONE)
            delete_user_session_data(user_id, Config.SESSION_DATA_KEY)
            line_bot_api_messaging.reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[TextMessage(text="参加予定登録を終了します。")]
                )
            )
