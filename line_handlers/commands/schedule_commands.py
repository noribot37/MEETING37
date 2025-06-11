import pandas as pd
from datetime import datetime
from linebot.v3.messaging import MessagingApi, ReplyMessageRequest, TextMessage, QuickReply, QuickReplyItem, MessageAction 

from config import Config, SessionState
from google_sheets.utils import (
    get_all_records,
    add_schedule,
    delete_schedule,
    edit_schedule
)
from utils.session_manager import get_user_session_data, set_user_session_data, delete_user_session_data


# スケジュール一覧表示 (ここに修正を追加)
def list_schedules(user_id, reply_token, line_bot_api_messaging: MessagingApi):
    all_schedules_df = get_all_records(Config.GOOGLE_SHEETS_SCHEDULE_WORKSHEET_NAME)

    messages_to_send = []

    if all_schedules_df.empty:
        reply_message_text = "登録されているスケジュールはありません。"
        messages_to_send.append(TextMessage(text=reply_message_text))
        SessionState.set_state(user_id, SessionState.NONE)
        delete_user_session_data(user_id, Config.SESSION_DATA_KEY)
    else:
        reply_message_text = "【スケジュール一覧】\n"
        all_schedules_df['日付'] = pd.to_datetime(all_schedules_df['日付'], errors='coerce')
        all_schedules_df = all_schedules_df.sort_values(by='日付', ascending=True)

        unregistered_events_for_session = []
        for index, meeting_series in all_schedules_df.iterrows():
            meeting = meeting_series.to_dict()
            date = meeting.get('日付')
            title = meeting.get('タイトル')
            if pd.notna(date) and title:
                unregistered_events_for_session.append({'date': date.strftime('%Y/%m/%d'), 'title': title})

        session_data = get_user_session_data(user_id, Config.SESSION_DATA_KEY) or {}
        session_data['unregistered_events'] = unregistered_events_for_session
        session_data['logic_path'] = 'list_schedules_flow'
        set_user_session_data(user_id, Config.SESSION_DATA_KEY, session_data)

        for index, row in all_schedules_df.iterrows():
            date_str = row['日付'].strftime('%Y/%m/%d') if pd.notna(row['日付']) else '日付未定'
            time_str = row.get('時間', '未定')
            location = row.get('場所', '未定')
            title = row.get('タイトル', '未定')
            detail = row.get('詳細', 'なし')
            deadline_str = row.get('申込締切日', 'なし')
            scale = row.get('尺', 'なし')

            reply_message_text += f"日付: {date_str}, タイトル: {title}\n"
            reply_message_text += f"  時間: {time_str}\n"
            reply_message_text += f"  場所: {location}\n"
            reply_message_text += f"  詳細: {detail}\n"
            reply_message_text += f"  申込締切日: {deadline_str}\n"
            reply_message_text += f"  尺: {scale}\n\n"

        messages_to_send.append(TextMessage(text=reply_message_text))

        quick_reply_message = TextMessage(
            text="続けて参加希望の登録をしますか？",
            quick_reply=QuickReply(
                items=[
                    QuickReplyItem(action=MessageAction(label="はい", text="はい")),
                    QuickReplyItem(action=MessageAction(label="いいえ", text="いいえ"))
                ]
            )
        )
        messages_to_send.append(quick_reply_message)

        # ★★★★ この一行を追加してください ★★★★
        SessionState.set_state(user_id, SessionState.ASKING_ATTENDEE_REGISTRATION_CONFIRMATION)


    line_bot_api_messaging.reply_message(
        ReplyMessageRequest(
            reply_token=reply_token,
            messages=messages_to_send
        )
    )


# スケジュール登録開始 (変更なし)
def start_schedule_registration(user_id, reply_token, line_bot_api_messaging: MessagingApi):
    SessionState.set_state(user_id, SessionState.ASKING_SCHEDULE_DATE)
    set_user_session_data(user_id, Config.SESSION_DATA_KEY, {})
    line_bot_api_messaging.reply_message(
        ReplyMessageRequest(
            reply_token=reply_token,
            messages=[TextMessage(text="スケジュールを登録します。日付をYYYY/MM/DD形式で入力してください。\n例: 2025/06/15")]
        )
    )

# スケジュール登録の次のステップ (変更なし)
def process_schedule_registration_step(user_id, message_text, reply_token, line_bot_api_messaging: MessagingApi):
    current_state = SessionState.get_state(user_id)
    session_data = get_user_session_data(user_id, Config.SESSION_DATA_KEY) or {}

    if current_state == SessionState.ASKING_SCHEDULE_DATE:
        try:
            pd.to_datetime(message_text, errors='raise') # 日付形式の検証
            session_data['日付'] = message_text
            set_user_session_data(user_id, Config.SESSION_DATA_KEY, session_data)
            SessionState.set_state(user_id, SessionState.ASKING_SCHEDULE_START_TIME) # 次は時間入力
            line_bot_api_messaging.reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[TextMessage(text="次に、開始時間を入力してください。（例: 10:00）")] # メッセージ変更
                )
            )
        except ValueError:
            line_bot_api_messaging.reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[TextMessage(text="日付の形式が正しくありません。YYYY/MM/DD形式で入力してください。\n例: 2025/06/15")]
                )
            )
    elif current_state == SessionState.ASKING_SCHEDULE_START_TIME: # 時間入力時の処理を追加
        session_data['時間'] = message_text
        set_user_session_data(user_id, Config.SESSION_DATA_KEY, session_data)

        # ここで重複チェックを実施
        all_schedules_df = get_all_records(Config.GOOGLE_SHEETS_SCHEDULE_WORKSHEET_NAME)

        # 日付と時間をdatetimeオブジェクトに変換して比較
        try:
            input_date = pd.to_datetime(session_data['日付']).normalize()
            # 時間は文字列のままで比較するため、そのまま利用
            input_time = session_data['時間']
        except ValueError:
            line_bot_api_messaging.reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[TextMessage(text="日付または時間の形式が正しくありません。最初からやり直してください。")]
                )
            )
            SessionState.set_state(user_id, SessionState.NONE)
            delete_user_session_data(user_id, Config.SESSION_DATA_KEY)
            return

        # スプレッドシートの日付もnormalizeして比較
        # '時間'列は文字列として扱われるため、直接比較
        duplicate_schedules = all_schedules_df[
            (pd.notna(all_schedules_df['日付']) & (all_schedules_df['日付'].dt.normalize() == input_date)) &
            (all_schedules_df['時間'] == input_time)
        ]

        if not duplicate_schedules.empty:
            # 重複が見つかった場合
            SessionState.set_state(user_id, SessionState.ASKING_CONTINUE_ON_DUPLICATE_SCHEDULE)

            # 既存のスケジュール情報を表示
            duplicate_info = "同日同時刻に以下の予定が既に登録されています:\n"
            for index, row in duplicate_schedules.iterrows():
                duplicate_info += f"- 日付: {row['日付'].strftime('%Y/%m/%d')}, 時間: {row['時間']}, タイトル: {row['タイトル']}\n"
            duplicate_info += "\n入力を続けますか？"

            line_bot_api_messaging.reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[TextMessage(
                        text=duplicate_info,
                        quick_reply=QuickReply(
                            items=[
                                QuickReplyItem(action=MessageAction(label="はい", text="はい")),
                                QuickReplyItem(action=MessageAction(label="いいえ", text="いいえ"))
                            ]
                        )
                    )]
                )
            )
        else:
            # 重複がない場合はそのままタイトル入力へ
            SessionState.set_state(user_id, SessionState.ASKING_SCHEDULE_TITLE)
            line_bot_api_messaging.reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[TextMessage(text="次に、スケジュールのタイトルを入力してください。")]
                )
            )

    elif current_state == SessionState.ASKING_CONTINUE_ON_DUPLICATE_SCHEDULE:
        if message_text.lower() == 'はい':
            # 「はい」の場合、次のタイトル入力へ進む
            SessionState.set_state(user_id, SessionState.ASKING_SCHEDULE_TITLE)
            line_bot_api_messaging.reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[TextMessage(text="続けてスケジュールのタイトルを入力してください。")]
                )
            )
        else:
            # 「いいえ」の場合、登録をキャンセルしてセッションを終了
            SessionState.set_state(user_id, SessionState.NONE)
            delete_user_session_data(user_id, Config.SESSION_DATA_KEY)
            line_bot_api_messaging.reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[TextMessage(text="スケジュール登録をキャンセルしました。")]
                )
            )

    elif current_state == SessionState.ASKING_SCHEDULE_TITLE: # タイトル入力時の処理を移動
        session_data['タイトル'] = message_text
        set_user_session_data(user_id, Config.SESSION_DATA_KEY, session_data)
        SessionState.set_state(user_id, SessionState.ASKING_SCHEDULE_LOCATION) # 次は場所入力
        line_bot_api_messaging.reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[TextMessage(text="場所を入力してください。（例: 会議室A）")]
            )
        )
    elif current_state == SessionState.ASKING_SCHEDULE_LOCATION:
        session_data['場所'] = message_text
        set_user_session_data(user_id, Config.SESSION_DATA_KEY, session_data)
        SessionState.set_state(user_id, SessionState.ASKING_SCHEDULE_DETAIL)
        line_bot_api_messaging.reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[TextMessage(text="詳細を入力してください。（ない場合は「なし」）")]
            )
        )
    elif current_state == SessionState.ASKING_SCHEDULE_DETAIL:
        session_data['詳細'] = message_text
        set_user_session_data(user_id, Config.SESSION_DATA_KEY, session_data)
        SessionState.set_state(user_id, SessionState.ASKING_SCHEDULE_DEADLINE)
        line_bot_api_messaging.reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[TextMessage(text="申込締切日をYYYY/MM/DD形式で入力してください。（ない場合は「なし」）")]
            )
        )
    elif current_state == SessionState.ASKING_SCHEDULE_DEADLINE:
        if message_text.lower() != 'なし':
            try:
                pd.to_datetime(message_text, errors='raise')
            except ValueError:
                line_bot_api_messaging.reply_message(
                    ReplyMessageRequest(
                        reply_token=reply_token,
                        messages=[TextMessage(text="日付の形式が正しくありません。「なし」またはYYYY/MM/DD形式で入力してください。\n例: 2025/06/15")]
                    )
                )
                return
        session_data['申込締切日'] = message_text
        set_user_session_data(user_id, Config.SESSION_DATA_KEY, session_data)
        SessionState.set_state(user_id, SessionState.ASKING_SCHEDULE_SCALE)
        line_bot_api_messaging.reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[TextMessage(text="尺を入力してください。（例: 1時間、ない場合は「なし」）")]
            )
        )
    elif current_state == SessionState.ASKING_SCHEDULE_SCALE:
        session_data['尺'] = message_text
        set_user_session_data(user_id, Config.SESSION_DATA_KEY, session_data)

        data_to_add = {
            '日付': session_data.get('日付'),
            'タイトル': session_data.get('タイトル'),
            '時間': session_data.get('時間'),
            '場所': session_data.get('場所'),
            '詳細': session_data.get('詳細'),
            '申込締切日': session_data.get('申込締切日', ''),
            '尺': session_data.get('尺', ''),
        }

        messages_to_send = []
        if add_schedule(data_to_add):
            registration_details = "以下の内容で登録しました！\n"
            display_keys = ['日付', 'タイトル', '時間', '場所', '詳細', '申込締切日', '尺']
            for key in display_keys:
                if key in data_to_add:
                    registration_details += f"{key}: {data_to_add[key]}\n"

            messages_to_send.append(TextMessage(text=registration_details))
            messages_to_send.append(
                TextMessage(
                    text="続けて他のスケジュールも登録しますか？",
                    quick_reply=QuickReply(
                        items=[
                            QuickReplyItem(action=MessageAction(label="はい", text="はい")),
                            QuickReplyItem(action=MessageAction(label="いいえ", text="いいえ"))
                        ]
                    )
                )
            )
            SessionState.set_state(user_id, SessionState.ASKING_FOR_ANOTHER_SCHEDULE_REGISTRATION)
        else:
            messages_to_send.append(TextMessage(text="スケジュールの登録に失敗しました。最初からやり直してください。"))
            SessionState.set_state(user_id, SessionState.NONE)

        delete_user_session_data(user_id, Config.SESSION_DATA_KEY)

        line_bot_api_messaging.reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=messages_to_send
            )
        )

# スケジュール編集開始 (変更なし)
def start_schedule_edit(user_id, reply_token, line_bot_api_messaging: MessagingApi):
    SessionState.set_state(user_id, SessionState.ASKING_SCHEDULE_EDIT_DATE)
    set_user_session_data(user_id, Config.SESSION_DATA_KEY, {})
    line_bot_api_messaging.reply_message(
        ReplyMessageRequest(
            reply_token=reply_token,
            messages=[TextMessage(text="編集したいスケジュールの日付をYYYY/MM/DD形式で入力してください。\n例: 2025/06/15")]
        )
    )

# スケジュール編集の次のステップ (変更なし)
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
            session_data['row_index'] = matching_schedule.index[0] + 2
            set_user_session_data(user_id, Config.SESSION_DATA_KEY, session_data)

            SessionState.set_state(user_id, SessionState.ASKING_SCHEDULE_EDIT_FIELD)
            line_bot_api_messaging.reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[TextMessage(text="編集したい項目を入力してください。（例: 場所、備考、詳細など）")]
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

# スケジュール削除開始 (変更なし)
def start_schedule_deletion(user_id, reply_token, line_bot_api_messaging: MessagingApi):
    SessionState.set_state(user_id, SessionState.ASKING_SCHEDULE_DELETE_DATE)
    set_user_session_data(user_id, Config.SESSION_DATA_KEY, {})
    line_bot_api_messaging.reply_message(
        ReplyMessageRequest(
            reply_token=reply_token,
            messages=[TextMessage(text="削除したいスケジュールの日付をYYYY/MM/DD形式で入力してください。\n例: 2025/06/15")]
        )
    )

# スケジュール削除の次のステップ (変更なし)
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
            session_data['row_index'] = matching_schedule.index[0] + 2
            set_user_session_data(user_id, Config.SESSION_DATA_KEY, session_data)
            SessionState.set_state(user_id, SessionState.ASKING_CONFIRM_SCHEDULE_DELETE)

            confirm_message = "以下のスケジュールを削除します。よろしいですか？\n"
            for key, value in session_data.items():
                if key != 'row_index':
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
