# line_handlers/commands/schedule_commands.py

import pandas as pd
from datetime import datetime
from linebot.v3.messaging import MessagingApi, ReplyMessageRequest, TextMessage

from config import Config, SessionState
from google_sheets.utils import (
    get_all_records,
    add_schedule,
    delete_schedule,
    edit_schedule
)
# utils/session_managerからセッション操作関数をインポート
from utils.session_manager import get_user_session_data, set_user_session_data, delete_user_session_data


# スケジュール一覧表示
def list_schedules(user_id, reply_token, line_bot_api_messaging: MessagingApi):
    # Config.GOOGLE_SHEETS_SCHEDULE_WORKSHEET_NAME を使用
    all_schedules_df = get_all_records(Config.GOOGLE_SHEETS_SCHEDULE_WORKSHEET_NAME)

    if all_schedules_df.empty:
        reply_message = "登録されているスケジュールはありません。"
    else:
        reply_message = "【スケジュール一覧】\n"
        # 日付でソート（日付がdatetime型であると仮定）
        # スプレッドシートから読み込んだ日付は文字列の場合があるため、変換を試みる
        all_schedules_df['日付'] = pd.to_datetime(all_schedules_df['日付'], errors='coerce')
        all_schedules_df = all_schedules_df.sort_values(by='日付', ascending=True)

        for index, row in all_schedules_df.iterrows():
            # スプレッドシートの列名に合わせて情報を取得
            # 日付
            date_str = row['日付'].strftime('%Y/%m/%d') if pd.notna(row['日付']) else '日付未定'
            # 時間 (シートの「時間」列から取得)
            time_str = row.get('時間', '未定')
            # 場所 (シートの「場所」列から取得)
            location = row.get('場所', '未定')
            # タイトル (シートの「タイトル」列から取得)
            title = row.get('タイトル', '未定')
            # 詳細 (シートの「詳細」列から取得)
            detail = row.get('詳細', 'なし')
            # 申込締切日 (シートの「申込締切日」列から取得)
            deadline_str = row.get('申込締切日', 'なし')
            # 尺 (シートの「尺」列から取得)
            scale = row.get('尺', 'なし')

            reply_message += f"日付: {date_str}, タイトル: {title}\n"
            reply_message += f"  時間: {time_str}\n" # 「開始時間 - 終了時間」ではなく「時間」列の値をそのまま表示
            reply_message += f"  場所: {location}\n"
            reply_message += f"  詳細: {detail}\n" # 「内容」ではなく「詳細」を表示
            reply_message += f"  申込締切日: {deadline_str}\n"
            reply_message += f"  尺: {scale}\n\n" # 「尺」を追加

    line_bot_api_messaging.reply_message(
        ReplyMessageRequest(
            reply_token=reply_token,
            messages=[TextMessage(text=reply_message)]
        )
    )

# スケジュール登録開始 (この関数は変更なし)
def start_schedule_registration(user_id, reply_token, line_bot_api_messaging: MessagingApi):
    SessionState.set_state(user_id, SessionState.ASKING_SCHEDULE_DATE)
    set_user_session_data(user_id, Config.SESSION_DATA_KEY, {}) # セッションデータを初期化
    line_bot_api_messaging.reply_message(
        ReplyMessageRequest(
            reply_token=reply_token,
            messages=[TextMessage(text="スケジュールを登録します。日付をYYYY/MM/DD形式で入力してください。\n例: 2025/06/15")]
        )
    )

# スケジュール登録の次のステップ (この関数は変更なし)
def process_schedule_registration_step(user_id, message_text, reply_token, line_bot_api_messaging: MessagingApi):
    current_state = SessionState.get_state(user_id)
    session_data = get_user_session_data(user_id, Config.SESSION_DATA_KEY) or {}

    if current_state == SessionState.ASKING_SCHEDULE_DATE:
        try:
            pd.to_datetime(message_text, errors='raise') # 日付形式の検証
            session_data['日付'] = message_text
            set_user_session_data(user_id, Config.SESSION_DATA_KEY, session_data)
            SessionState.set_state(user_id, SessionState.ASKING_SCHEDULE_TITLE)
            line_bot_api_messaging.reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[TextMessage(text="次に、スケジュールのタイトルを入力してください。")]
                )
            )
        except ValueError:
            line_bot_api_messaging.reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[TextMessage(text="日付の形式が正しくありません。YYYY/MM/DD形式で入力してください。\n例: 2025/06/15")]
                )
            )
    elif current_state == SessionState.ASKING_SCHEDULE_TITLE:
        session_data['タイトル'] = message_text
        set_user_session_data(user_id, Config.SESSION_DATA_KEY, session_data)
        # スケジュール登録ステップはシートの列に合わせて変更する必要があるかもしれません。
        # 現在のシートには「開始時間」「終了時間」「担当者」「内容」「URL」「備考」は直接ありません。
        # 「時間」「詳細」「申込締切日」「尺」に合わせるべきです。
        # ここから下のASKING_SCHEDULE_START_TIMEなどは、シートに合わせて変更が必要になります。
        # 一旦、エラーを起こさないために既存のロジックは残しますが、
        # 今後、この登録フローの質問項目もシートに合わせて調整が必要です。
        SessionState.set_state(user_id, SessionState.ASKING_SCHEDULE_START_TIME) # この部分は、シートの「時間」に一本化するなど検討が必要
        line_bot_api_messaging.reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[TextMessage(text="開始時間を入力してください。（例: 10:00）")]
            )
        )
    elif current_state == SessionState.ASKING_SCHEDULE_START_TIME:
        session_data['開始時間'] = message_text
        set_user_session_data(user_id, Config.SESSION_DATA_KEY, session_data)
        SessionState.set_state(user_id, SessionState.ASKING_SCHEDULE_END_TIME)
        line_bot_api_messaging.reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[TextMessage(text="終了時間を入力してください。（例: 11:00）")]
            )
        )
    elif current_state == SessionState.ASKING_SCHEDULE_END_TIME:
        session_data['終了時間'] = message_text
        set_user_session_data(user_id, Config.SESSION_DATA_KEY, session_data)
        SessionState.set_state(user_id, SessionState.ASKING_SCHEDULE_LOCATION)
        line_bot_api_messaging.reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[TextMessage(text="場所を入力してください。（例: 会議室A）")]
            )
        )
    elif current_state == SessionState.ASKING_SCHEDULE_LOCATION:
        session_data['場所'] = message_text
        set_user_session_data(user_id, Config.SESSION_DATA_KEY, session_data)
        SessionState.set_state(user_id, SessionState.ASKING_SCHEDULE_PERSON_IN_CHARGE)
        line_bot_api_messaging.reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[TextMessage(text="担当者を入力してください。（例: 〇〇）")]
            )
        )
    elif current_state == SessionState.ASKING_SCHEDULE_PERSON_IN_CHARGE:
        session_data['担当者'] = message_text
        set_user_session_data(user_id, Config.SESSION_DATA_KEY, session_data)
        SessionState.set_state(user_id, SessionState.ASKING_SCHEDULE_CONTENT)
        line_bot_api_messaging.reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[TextMessage(text="内容を入力してください。（ない場合は「なし」）")]
            )
        )
    elif current_state == SessionState.ASKING_SCHEDULE_CONTENT:
        session_data['内容'] = message_text
        set_user_session_data(user_id, Config.SESSION_DATA_KEY, session_data)
        SessionState.set_state(user_id, SessionState.ASKING_SCHEDULE_URL)
        line_bot_api_messaging.reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[TextMessage(text="関連URLを入力してください。（ない場合は「なし」）")]
            )
        )
    elif current_state == SessionState.ASKING_SCHEDULE_URL:
        session_data['URL'] = message_text
        set_user_session_data(user_id, Config.SESSION_DATA_KEY, session_data)
        SessionState.set_state(user_id, SessionState.ASKING_SCHEDULE_NOTES)
        line_bot_api_messaging.reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[TextMessage(text="備考を入力してください。（ない場合は「なし」）")]
            )
        )
    elif current_state == SessionState.ASKING_SCHEDULE_NOTES:
        session_data['備考'] = message_text
        set_user_session_data(user_id, Config.SESSION_DATA_KEY, session_data)
        SessionState.set_state(user_id, SessionState.ASKING_CONFIRM_SCHEDULE_REGISTRATION)

        confirm_message = "以下の内容でスケジュールを登録します。よろしいですか？\n"
        for key, value in session_data.items():
            confirm_message += f"{key}: {value}\n"
        confirm_message += "はい / いいえ"

        line_bot_api_messaging.reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[TextMessage(text=confirm_message)]
            )
        )
    elif current_state == SessionState.ASKING_CONFIRM_SCHEDULE_REGISTRATION:
        if message_text.lower() == 'はい':
            if add_schedule(session_data):
                reply_message = "スケジュールを登録しました。\n続けて別のスケジュールを登録しますか？（はい/いいえ）"
                SessionState.set_state(user_id, SessionState.ASKING_FOR_ANOTHER_SCHEDULE_REGISTRATION)
            else:
                reply_message = "スケジュールの登録に失敗しました。最初からやり直してください。"
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
                    messages=[TextMessage(text="スケジュール登録をキャンセルしました。")]
                )
            )
    elif current_state == SessionState.ASKING_FOR_ANOTHER_SCHEDULE_REGISTRATION:
        if message_text.lower() == 'はい':
            start_schedule_registration(user_id, reply_token, line_bot_api_messaging)
        else:
            SessionState.set_state(user_id, SessionState.NONE)
            delete_user_session_data(user_id, Config.SESSION_DATA_KEY)
            line_bot_api_messaging.reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[TextMessage(text="スケジュール登録を終了します。")]
                )
            )

# スケジュール編集開始 (この関数は変更なし)
def start_schedule_edit(user_id, reply_token, line_bot_api_messaging: MessagingApi):
    SessionState.set_state(user_id, SessionState.ASKING_SCHEDULE_EDIT_DATE)
    set_user_session_data(user_id, Config.SESSION_DATA_KEY, {})
    line_bot_api_messaging.reply_message(
        ReplyMessageRequest(
            reply_token=reply_token,
            messages=[TextMessage(text="編集したいスケジュールの日付をYYYY/MM/DD形式で入力してください。\n例: 2025/06/15")]
        )
    )

# スケジュール編集の次のステップ (この関数は変更なし)
def process_schedule_edit_step(user_id, message_text, reply_token, line_bot_api_messaging: MessagingApi):
    current_state = SessionState.get_state(user_id)
    session_data = get_user_session_data(user_id, Config.SESSION_DATA_KEY) or {}

    if current_state == SessionState.ASKING_SCHEDULE_EDIT_DATE:
        try:
            pd.to_datetime(message_text, errors='raise')
            session_data['日付'] = message_text
            set_user_session_data(user_id, Config.SESSION_DATA_KEY, session_data)
            SessionState.set_state(user_id, SessionState.ASKING_SCHEDULE_EDIT_TITLE)
            line_bot_api_messaging.reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[TextMessage(text="次に、編集したいスケジュールのタイトルを入力してください。")]
                )
            )
        except ValueError:
            line_bot_api_messaging.reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[TextMessage(text="日付の形式が正しくありません。YYYY/MM/DD形式で入力してください。\n例: 2025/06/15")]
                )
            )
    elif current_state == SessionState.ASKING_SCHEDULE_EDIT_TITLE:
        session_data['タイトル'] = message_text
        set_user_session_data(user_id, Config.SESSION_DATA_KEY, session_data)

        # 該当するスケジュールが存在するか確認
        all_schedules = get_all_records(Config.GOOGLE_SHEETS_SCHEDULE_WORKSHEET_NAME)

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

        matching_schedule = all_schedules[
            (pd.notna(all_schedules['日付']) & (all_schedules['日付'].dt.normalize() == search_date)) &
            (all_schedules['タイトル'] == session_data['タイトル'])
        ]

        if not matching_schedule.empty:
            session_data['row_index'] = matching_schedule.index[0] + 2 # スプレッドシートの行番号（1始まり、ヘッダー含む）
            set_user_session_data(user_id, Config.SESSION_DATA_KEY, session_data)

            SessionState.set_state(user_id, SessionState.ASKING_SCHEDULE_EDIT_FIELD)
            line_bot_api_messaging.reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[TextMessage(text="編集したい項目を入力してください。（例: 場所、備考、内容など）")]
                )
            )
        else:
            SessionState.set_state(user_id, SessionState.NONE)
            delete_user_session_data(user_id, Config.SESSION_DATA_KEY)
            line_bot_api_messaging.reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[TextMessage(text="指定されたスケジュールは見つかりませんでした。最初からやり直してください。")]
                )
            )
    elif current_state == SessionState.ASKING_SCHEDULE_EDIT_FIELD:
        session_data['編集項目'] = message_text
        set_user_session_data(user_id, Config.SESSION_DATA_KEY, session_data)
        SessionState.set_state(user_id, SessionState.ASKING_SCHEDULE_EDIT_VALUE)
        line_bot_api_messaging.reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[TextMessage(text=f"{session_data['編集項目']}の新しい値を入力してください。")]
            )
        )
    elif current_state == SessionState.ASKING_SCHEDULE_EDIT_VALUE:
        field_to_edit = session_data['編集項目']
        new_value = message_text
        row_index = session_data['row_index']

        update_data = {field_to_edit: new_value}
        if edit_schedule(row_index, update_data):
            reply_message = "スケジュールを更新しました。\n他に編集したい予定はありますか？（はい/いいえ）"
            SessionState.set_state(user_id, SessionState.ASKING_FOR_ANOTHER_SCHEDULE_EDIT)
        else:
            reply_message = "スケジュールの更新に失敗しました。最初からやり直してください。"
            SessionState.set_state(user_id, SessionState.NONE)
        delete_user_session_data(user_id, Config.SESSION_DATA_KEY)
        line_bot_api_messaging.reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[TextMessage(text=reply_message)]
            )
        )
    elif current_state == SessionState.ASKING_FOR_ANOTHER_SCHEDULE_EDIT:
        if message_text.lower() == 'はい':
            start_schedule_edit(user_id, reply_token, line_bot_api_messaging)
        else:
            SessionState.set_state(user_id, SessionState.NONE)
            delete_user_session_data(user_id, Config.SESSION_DATA_KEY)
            line_bot_api_messaging.reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[TextMessage(text="スケジュール編集を終了します。")]
                )
            )

# スケジュール削除開始 (この関数は変更なし)
def start_schedule_deletion(user_id, reply_token, line_bot_api_messaging: MessagingApi):
    SessionState.set_state(user_id, SessionState.ASKING_SCHEDULE_DELETE_DATE)
    set_user_session_data(user_id, Config.SESSION_DATA_KEY, {})
    line_bot_api_messaging.reply_message(
        ReplyMessageRequest(
            reply_token=reply_token,
            messages=[TextMessage(text="削除したいスケジュールの日付をYYYY/MM/DD形式で入力してください。\n例: 2025/06/15")]
        )
    )

# スケジュール削除の次のステップ (この関数は変更なし)
def process_schedule_deletion_step(user_id, message_text, reply_token, line_bot_api_messaging: MessagingApi):
    current_state = SessionState.get_state(user_id)
    session_data = get_user_session_data(user_id, Config.SESSION_DATA_KEY) or {}

    if current_state == SessionState.ASKING_SCHEDULE_DELETE_DATE:
        try:
            pd.to_datetime(message_text, errors='raise')
            session_data['日付'] = message_text
            set_user_session_data(user_id, Config.SESSION_DATA_KEY, session_data)
            SessionState.set_state(user_id, SessionState.ASKING_SCHEDULE_DELETE_TITLE)
            line_bot_api_messaging.reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[TextMessage(text="次に、削除したいスケジュールのタイトルを入力してください。")]
                )
            )
        except ValueError:
            line_bot_api_messaging.reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[TextMessage(text="日付の形式が正しくありません。YYYY/MM/DD形式で入力してください。\n例: 2025/06/15")]
                )
            )
    elif current_state == SessionState.ASKING_SCHEDULE_DELETE_TITLE:
        session_data['タイトル'] = message_text
        set_user_session_data(user_id, Config.SESSION_DATA_KEY, session_data)

        # 該当するスケジュールが存在するか確認
        all_schedules = get_all_records(Config.GOOGLE_SHEETS_SCHEDULE_WORKSHEET_NAME)

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

        matching_schedule = all_schedules[
            (pd.notna(all_schedules['日付']) & (all_schedules['日付'].dt.normalize() == search_date)) &
            (all_schedules['タイトル'] == session_data['タイトル'])
        ]

        if not matching_schedule.empty:
            session_data['row_index'] = matching_schedule.index[0] + 2 # スプレッドシートの行番号（1始まり、ヘッダー含む）
            set_user_session_data(user_id, Config.SESSION_DATA_KEY, session_data)
            SessionState.set_state(user_id, SessionState.ASKING_CONFIRM_SCHEDULE_DELETE)

            confirm_message = "以下のスケジュールを削除します。よろしいですか？\n"
            for key, value in session_data.items():
                if key != 'row_index': # row_indexは表示しない
                    confirm_message += f"{key}: {value}\n"
            confirm_message += "はい / いいえ"

            line_bot_api_messaging.reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[TextMessage(text=confirm_message)]
                )
            )
        else:
            SessionState.set_state(user_id, SessionState.NONE)
            delete_user_session_data(user_id, Config.SESSION_DATA_KEY)
            line_bot_api_messaging.reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[TextMessage(text="指定されたスケジュールは見つかりませんでした。最初からやり直してください。")]
                )
            )
    elif current_state == SessionState.ASKING_CONFIRM_SCHEDULE_DELETE:
        if message_text.lower() == 'はい':
            row_index_to_delete = session_data['row_index']
            if delete_schedule(row_index_to_delete):
                reply_message = "スケジュールを削除しました。\n続けて別のスケジュールを削除しますか？（はい/いいえ）"
                SessionState.set_state(user_id, SessionState.ASKING_FOR_NEXT_SCHEDULE_DELETION)
            else:
                reply_message = "スケジュールの削除に失敗しました。最初からやり直してください。"
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
                    messages=[TextMessage(text="スケジュール削除をキャンセルしました。")]
                )
            )
    elif current_state == SessionState.ASKING_FOR_NEXT_SCHEDULE_DELETION:
        if message_text.lower() == 'はい':
            start_schedule_deletion(user_id, reply_token, line_bot_api_messaging)
        else:
            SessionState.set_state(user_id, SessionState.NONE)
            delete_user_session_data(user_id, Config.SESSION_DATA_KEY)
            line_bot_api_messaging.reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[TextMessage(text="スケジュール削除を終了します。")]
                )
            )
