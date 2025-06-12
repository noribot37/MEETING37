import pandas as pd
from datetime import datetime
from linebot.v3.messaging import MessagingApi, ReplyMessageRequest, TextMessage, QuickReply, QuickReplyItem
from linebot.v3.messaging.models import MessageAction, PostbackAction

from config import Config, SessionState
from google_sheets.utils import get_all_records, add_schedule, update_schedule, delete_schedule_by_date_title
from utils.session_manager import get_user_session_data, set_user_session_data, delete_user_session_data


def start_schedule_registration(user_id, reply_token, line_bot_api_messaging: MessagingApi):
    print(f"DEBUG: start_schedule_registration called for user_id: {user_id}")
    SessionState.set_state(user_id, SessionState.ASKING_SCHEDULE_DATE)
    # 修正: Config.SESSION_DATA_KEY を削除
    set_user_session_data(user_id, {})  # セッションデータを初期化
    line_bot_api_messaging.reply_message(
        ReplyMessageRequest(
            reply_token=reply_token,
            messages=[TextMessage(text="スケジュール登録を開始します。\n日付をYYYY/MM/DD形式で入力してください。\n例: 2025/06/15")]
        )
    )

def process_schedule_registration_step(user_id, message_text, reply_token, line_bot_api_messaging: MessagingApi):
    print(f"DEBUG: process_schedule_registration_step called for user_id: {user_id}, message: {message_text}")
    current_state = SessionState.get_state(user_id)
    # 修正: Config.SESSION_DATA_KEY を削除
    session_data = get_user_session_data(user_id) or {}
    messages = []

    if current_state == SessionState.ASKING_SCHEDULE_DATE:
        try:
            # 日付の正規表現チェックと変換
            if not pd.isna(message_text):
                date_obj = pd.to_datetime(message_text)
                session_data['日付'] = date_obj.strftime('%Y/%m/%d')
                SessionState.set_state(user_id, SessionState.ASKING_SCHEDULE_START_TIME)
                messages.append(TextMessage(text="開始時刻をHH:MM形式で入力してください。（例: 10:00, 22:30）\nない場合は「なし」と入力してください。"))
            else:
                raise ValueError("Date cannot be empty.")
        except ValueError:
            messages.append(TextMessage(text="日付の形式が正しくありません。YYYY/MM/DD形式で入力してください。\n例: 2025/06/15"))
    elif current_state == SessionState.ASKING_SCHEDULE_START_TIME:
        if message_text.lower() == 'なし' or pd.isna(message_text):
            session_data['開始時刻'] = 'なし'
            SessionState.set_state(user_id, SessionState.ASKING_SCHEDULE_TITLE)
            messages.append(TextMessage(text="次に、スケジュールのタイトルを入力してください。"))
        else:
            # 時刻の正規表現チェック
            if re.fullmatch(r'([01]?[0-9]|2[0-3]):[0-5][0-9]', message_text):
                session_data['開始時刻'] = message_text
                SessionState.set_state(user_id, SessionState.ASKING_SCHEDULE_TITLE)
                messages.append(TextMessage(text="次に、スケジュールのタイトルを入力してください。"))
            else:
                messages.append(TextMessage(text="時刻の形式が正しくありません。HH:MM形式で入力してください。（例: 10:00, 22:30）\nない場合は「なし」と入力してください。"))
    elif current_state == SessionState.ASKING_SCHEDULE_TITLE:
        if pd.isna(message_text) or not message_text.strip():
            messages.append(TextMessage(text="タイトルは必須です。スケジュールタイトルを入力してください。"))
        else:
            session_data['タイトル'] = message_text.strip()

            # 重複チェックの前にデータを保存
            # 修正: Config.SESSION_DATA_KEY を削除
            set_user_session_data(user_id, session_data)

            # 重複チェック
            all_schedules_df = get_all_records(Config.GOOGLE_SHEETS_SCHEDULE_WORKSHEET_NAME)
            if not all_schedules_df.empty:
                # 日付とタイトルが一致する行を検索
                # スプレッドシートの日付もpd.to_datetimeで変換して比較
                all_schedules_df['日付_dt'] = pd.to_datetime(all_schedules_df['日付'], errors='coerce')

                # session_data['日付'] も datetime オブジェクトに変換して比較
                try:
                    session_date_dt = pd.to_datetime(session_data['日付'])
                    duplicate_entry = all_schedules_df[
                        (all_schedules_df['日付_dt'].dt.normalize() == session_date_dt.normalize()) &
                        (all_schedules_df['タイトル'] == session_data['タイトル'])
                    ]
                except ValueError: # session_data['日付']が不正な場合は無視
                    duplicate_entry = pd.DataFrame() # 重複なしとする

                if not duplicate_entry.empty:
                    SessionState.set_state(user_id, SessionState.ASKING_CONTINUE_ON_DUPLICATE_SCHEDULE)
                    messages.append(TextMessage(
                        text=f"「{session_data['日付']}」の「{session_data['タイトル']}」は既に登録されています。\n"
                             f"この内容で上書きしますか？（はい/いいえ）",
                        quick_reply=QuickReply(items=[
                            QuickReplyItem(action=MessageAction(label="はい", text="はい")),
                            QuickReplyItem(action=MessageAction(label="いいえ", text="いいえ"))
                        ])
                    ))
                    # 重複確認を待つためここで処理を中断
                    line_bot_api_messaging.reply_message(
                        ReplyMessageRequest(
                            reply_token=reply_token,
                            messages=messages
                        )
                    )
                    return # ここでreturnして重複確認の返答を待つ

            # 重複がなければ次の状態へ
            SessionState.set_state(user_id, SessionState.ASKING_SCHEDULE_LOCATION)
            messages.append(TextMessage(text="次に、開催場所を入力してください。（ない場合は「なし」）"))

    elif current_state == SessionState.ASKING_CONTINUE_ON_DUPLICATE_SCHEDULE:
        if message_text.lower() == 'はい':
            # ユーザーが上書きを承諾
            SessionState.set_state(user_id, SessionState.ASKING_SCHEDULE_LOCATION)
            messages.append(TextMessage(text="開催場所を入力してください。（ない場合は「なし」）"))
        else: # いいえ、またはその他の入力
            # 登録を中止しセッションをリセット
            SessionState.set_state(user_id, SessionState.NONE)
            # 修正: Config.SESSION_DATA_KEY を削除
            delete_user_session_data(user_id)
            messages.append(TextMessage(text="スケジュール登録を中止しました。"))
            line_bot_api_messaging.reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=messages
                )
            )
            return # 処理を終了

    elif current_state == SessionState.ASKING_SCHEDULE_LOCATION:
        session_data['開催場所'] = message_text.strip() if not pd.isna(message_text) else 'なし'
        SessionState.set_state(user_id, SessionState.ASKING_SCHEDULE_DETAIL)
        messages.append(TextMessage(text="次に、詳細情報を入力してください。（ない場合は「なし」）"))
    elif current_state == SessionState.ASKING_SCHEDULE_DETAIL:
        session_data['詳細'] = message_text.strip() if not pd.isna(message_text) else 'なし'
        SessionState.set_state(user_id, SessionState.ASKING_SCHEDULE_DEADLINE)
        messages.append(TextMessage(text="次に、申込締切日をYYYY/MM/DD形式で入力してください。（ない場合は「なし」）\n例: 2025/06/01"))
    elif current_state == SessionState.ASKING_SCHEDULE_DEADLINE:
        if message_text.lower() == 'なし' or pd.isna(message_text):
            session_data['申込締切日'] = 'なし'
            SessionState.set_state(user_id, SessionState.ASKING_SCHEDULE_SCALE)
            messages.append(TextMessage(text="次に、規模を入力してください。（例: 100名、50人以下など。ない場合は「なし」）"))
        else:
            try:
                # 締切日の正規表現チェックと変換
                if not pd.isna(message_text):
                    deadline_obj = pd.to_datetime(message_text)
                    session_data['申込締切日'] = deadline_obj.strftime('%Y/%m/%d')
                    SessionState.set_state(user_id, SessionState.ASKING_SCHEDULE_SCALE)
                    messages.append(TextMessage(text="次に、規模を入力してください。（例: 100名、50人以下など。ない場合は「なし」）"))
                else:
                    raise ValueError("Deadline cannot be empty.")
            except ValueError:
                messages.append(TextMessage(text="申込締切日の形式が正しくありません。YYYY/MM/DD形式で入力してください。（ない場合は「なし」）\n例: 2025/06/01"))
    elif current_state == SessionState.ASKING_SCHEDULE_SCALE:
        session_data['規模'] = message_text.strip() if not pd.isna(message_text) else 'なし'

        # 全ての情報を収集後、スプレッドシートに書き込み
        print(f"DEBUG: All schedule data collected for user {user_id}. Data: {session_data}")
        success, msg = add_schedule(session_data)

        if success:
            messages.append(TextMessage(text="スケジュールを登録しました！\n続けてスケジュールを登録しますか？（はい/いいえ）",
                                        quick_reply=QuickReply(items=[
                                            QuickReplyItem(action=MessageAction(label="はい", text="はい")),
                                            QuickReplyItem(action=MessageAction(label="いいえ", text="いいえ"))
                                        ])))
            SessionState.set_state(user_id, SessionState.ASKING_FOR_ANOTHER_SCHEDULE_REGISTRATION)
        else:
            messages.append(TextMessage(text=f"スケジュールの登録に失敗しました: {msg}\n最初からやり直してください。"))
            SessionState.set_state(user_id, SessionState.NONE)
            # 修正: Config.SESSION_DATA_KEY を削除
            delete_user_session_data(user_id)

    # 状態がASKING_FOR_ANOTHER_SCHEDULE_REGISTRATIONの時に'はい'/'いいえ'を処理するロジック
    elif current_state == SessionState.ASKING_FOR_ANOTHER_SCHEDULE_REGISTRATION:
        if message_text.lower() == 'はい':
            start_schedule_registration(user_id, reply_token, line_bot_api_messaging) # 再帰的に開始
            return # ここで処理を終了
        else:
            messages.append(TextMessage(text="スケジュール登録を終了します。"))
            SessionState.set_state(user_id, SessionState.NONE)
            # 修正: Config.SESSION_DATA_KEY を削除
            delete_user_session_data(user_id)

    # 修正: Config.SESSION_DATA_KEY を削除
    set_user_session_data(user_id, session_data) # 現在のセッションデータを保存

    if messages:
        line_bot_api_messaging.reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=messages
            )
        )


def list_schedules(user_id, reply_token, line_bot_api_messaging: MessagingApi):
    print(f"DEBUG: list_schedules called for user_id: {user_id}")
    schedules_df = get_all_records(Config.GOOGLE_SHEETS_SCHEDULE_WORKSHEET_NAME)

    if schedules_df.empty:
        reply_message = "現在、登録されているスケジュールはありません。"
        print("DEBUG: Schedule worksheet is empty.")
    else:
        # '日付'カラムを datetime オブジェクトに変換し、変換できないものはNaT (Not a Time) とする
        schedules_df['日付'] = pd.to_datetime(schedules_df['日付'], errors='coerce')
        # 日付でソートし、日付がNaTのものを最後に持ってくる
        schedules_df = schedules_df.sort_values(by='日付', ascending=True, na_position='last')

        reply_message = "【今後のスケジュール一覧】\n\n"
        for index, row in schedules_df.iterrows():
            date_str = row['日付'].strftime('%Y/%m/%d') if pd.notna(row['日付']) else '日付未定'
            start_time = row.get('開始時刻', 'なし')
            title = row.get('タイトル', 'タイトルなし')
            location = row.get('開催場所', 'なし')
            detail = row.get('詳細', 'なし')
            deadline = row.get('申込締切日', 'なし')
            scale = row.get('規模', 'なし')

            reply_message += f"日付: {date_str}\n"
            reply_message += f"開始時刻: {start_time}\n"
            reply_message += f"タイトル: {title}\n"
            reply_message += f"開催場所: {location}\n"
            reply_message += f"詳細: {detail}\n"
            reply_message += f"申込締切日: {deadline}\n"
            reply_message += f"規模: {scale}\n"
            reply_message += "--------------------\n"
        print(f"DEBUG: Successfully prepared {len(schedules_df)} schedules.")

    line_bot_api_messaging.reply_message(
        ReplyMessageRequest(
            reply_token=reply_token,
            messages=[TextMessage(text=reply_message)]
        )
    )

def start_schedule_edit(user_id, reply_token, line_bot_api_messaging: MessagingApi):
    print(f"DEBUG: start_schedule_edit called for user_id: {user_id}")
    SessionState.set_state(user_id, SessionState.ASKING_SCHEDULE_EDIT_DATE)
    # 修正: Config.SESSION_DATA_KEY を削除
    set_user_session_data(user_id, {})  # セッションデータを初期化
    line_bot_api_messaging.reply_message(
        ReplyMessageRequest(
            reply_token=reply_token,
            messages=[TextMessage(text="編集したいスケジュールの**日付**をYYYY/MM/DD形式で入力してください。\n例: 2025/06/15")]
        )
    )

def process_schedule_edit_step(user_id, message_text, reply_token, line_bot_api_messaging: MessagingApi):
    print(f"DEBUG: process_schedule_edit_step called for user_id: {user_id}, message: {message_text}")
    current_state = SessionState.get_state(user_id)
    # 修正: Config.SESSION_DATA_KEY を削除
    session_data = get_user_session_data(user_id) or {}
    messages = []

    if current_state == SessionState.ASKING_SCHEDULE_EDIT_DATE:
        try:
            pd.to_datetime(message_text, errors='raise') # 日付として有効かチェック
            session_data['編集対象日付'] = message_text
            SessionState.set_state(user_id, SessionState.ASKING_SCHEDULE_EDIT_TITLE)
            messages.append(TextMessage(text="次に、編集したいスケジュールの**タイトル**を入力してください。"))
        except ValueError:
            messages.append(TextMessage(text="日付の形式が正しくありません。YYYY/MM/DD形式で入力してください。\n例: 2025/06/15"))

    elif current_state == SessionState.ASKING_SCHEDULE_EDIT_TITLE:
        session_data['編集対象タイトル'] = message_text.strip()
        # 編集対象のスケジュールが存在するか確認
        schedules_df = get_all_records(Config.GOOGLE_SHEETS_SCHEDULE_WORKSHEET_NAME)

        target_date_str = session_data.get('編集対象日付')
        target_title = session_data.get('編集対象タイトル')

        # 日付をdatetimeオブジェクトに変換して比較
        try:
            target_date_dt = pd.to_datetime(target_date_str).normalize()
            matching_schedules = schedules_df[
                (schedules_df['日付'].apply(lambda x: pd.to_datetime(x, errors='coerce').normalize() if pd.notna(x) else None) == target_date_dt) &
                (schedules_df['タイトル'] == target_title)
            ]
        except ValueError:
            matching_schedules = pd.DataFrame() # 無効な日付の場合は一致なしとする

        if not matching_schedules.empty:
            # 該当するスケジュールが見つかった場合、どの項目を編集するか尋ねる
            session_data['既存データ'] = matching_schedules.iloc[0].to_dict() # 既存データをセッションに保存
            SessionState.set_state(user_id, SessionState.ASKING_SCHEDULE_EDIT_FIELD)
            quick_reply_items = [
                QuickReplyItem(action=MessageAction(label="日付", text="日付")),
                QuickReplyItem(action=MessageAction(label="開始時刻", text="開始時刻")),
                QuickReplyItem(action=MessageAction(label="タイトル", text="タイトル")),
                QuickReplyItem(action=MessageAction(label="開催場所", text="開催場所")),
                QuickReplyItem(action=MessageAction(label="詳細", text="詳細")),
                QuickReplyItem(action=MessageAction(label="申込締切日", text="申込締切日")),
                QuickReplyItem(action=MessageAction(label="規模", text="規模")),
                QuickReplyItem(action=MessageAction(label="終了", text="終了")) # 編集終了オプションを追加
            ]
            messages.append(TextMessage(text="どの項目を編集しますか？", quick_reply=QuickReply(items=quick_reply_items)))
        else:
            SessionState.set_state(user_id, SessionState.NONE)
            # 修正: Config.SESSION_DATA_KEY を削除
            delete_user_session_data(user_id)
            messages.append(TextMessage(text="指定されたスケジュールは見つかりませんでした。\n最初からやり直してください。"))

    elif current_state == SessionState.ASKING_SCHEDULE_EDIT_FIELD:
        editable_fields = ["日付", "開始時刻", "タイトル", "開催場所", "詳細", "申込締切日", "規模"]
        if message_text == "終了":
            SessionState.set_state(user_id, SessionState.NONE)
            # 修正: Config.SESSION_DATA_KEY を削除
            delete_user_session_data(user_id)
            messages.append(TextMessage(text="スケジュール編集を終了します。"))
        elif message_text in editable_fields:
            session_data['編集フィールド'] = message_text
            SessionState.set_state(user_id, SessionState.ASKING_SCHEDULE_EDIT_NEW_VALUE)
            messages.append(TextMessage(text=f"「{message_text}」の新しい値を入力してください。"))
        else:
            messages.append(TextMessage(text="無効な項目です。リストから選択するか、「終了」と入力してください。"))

    elif current_state == SessionState.ASKING_SCHEDULE_EDIT_NEW_VALUE:
        field_to_edit = session_data.get('編集フィールド')
        new_value = message_text.strip() if not pd.isna(message_text) else 'なし'

        # 形式チェック (日付と時刻のみ)
        if field_to_edit in ["日付", "申込締切日"]:
            try:
                if new_value.lower() != 'なし':
                    pd.to_datetime(new_value, errors='raise')
                # OKならそのまま進む
            except ValueError:
                messages.append(TextMessage(text=f"「{field_to_edit}」の形式が正しくありません。YYYY/MM/DD形式で入力してください。\n変更をキャンセルし、再度項目選択からやり直します。",
                                            quick_reply=QuickReply(items=[
                                                QuickReplyItem(action=MessageAction(label="日付", text="日付")),
                                                QuickReplyItem(action=MessageAction(label="開始時刻", text="開始時刻")),
                                                QuickReplyItem(action=MessageAction(label="タイトル", text="タイトル")),
                                                QuickReplyItem(action=MessageAction(label="開催場所", text="開催場所")),
                                                QuickReplyItem(action=MessageAction(label="詳細", text="詳細")),
                                                QuickReplyItem(action=MessageAction(label="申込締切日", text="申込締切日")),
                                                QuickReplyItem(action=MessageAction(label="規模", text="規模")),
                                                QuickReplyItem(action=MessageAction(label="終了", text="終了"))
                                            ])))
                SessionState.set_state(user_id, SessionState.ASKING_SCHEDULE_EDIT_FIELD) # 項目選択に戻す
                # 修正: Config.SESSION_DATA_KEY を削除
                set_user_session_data(user_id, session_data) # セッションはクリアしない
                line_bot_api_messaging.reply_message(
                    ReplyMessageRequest(
                        reply_token=reply_token,
                        messages=messages
                    )
                )
                return
        elif field_to_edit == "開始時刻":
            if new_value.lower() != 'なし' and not re.fullmatch(r'([01]?[0-9]|2[0-3]):[0-5][0-9]', new_value):
                messages.append(TextMessage(text=f"「{field_to_edit}」の形式が正しくありません。HH:MM形式で入力してください。\n変更をキャンセルし、再度項目選択からやり直します。",
                                            quick_reply=QuickReply(items=[
                                                QuickReplyItem(action=MessageAction(label="日付", text="日付")),
                                                QuickReplyItem(action=MessageAction(label="開始時刻", text="開始時刻")),
                                                QuickReplyItem(action=MessageAction(label="タイトル", text="タイトル")),
                                ReplyMessageItem(action=MessageAction(label="開催場所", text="開催場所")),
                                                QuickReplyItem(action=MessageAction(label="詳細", text="詳細")),
                                                QuickReplyItem(action=MessageAction(label="申込締切日", text="申込締切日")),
                                                QuickReplyItem(action=MessageAction(label="規模", text="規模")),
                                                QuickReplyItem(action=MessageAction(label="終了", text="終了"))
                                            ])))
                SessionState.set_state(user_id, SessionState.ASKING_SCHEDULE_EDIT_FIELD) # 項目選択に戻す
                # 修正: Config.SESSION_DATA_KEY を削除
                set_user_session_data(user_id, session_data) # セッションはクリアしない
                line_bot_api_messaging.reply_message(
                    ReplyMessageRequest(
                        reply_token=reply_token,
                        messages=messages
                    )
                )
                return

        # スプレッドシートを更新
        original_date = session_data['編集対象日付']
        original_title = session_data['編集対象タイトル']

        # 更新する辞書を作成
        update_data = {field_to_edit: new_value}

        success, msg = update_schedule(original_date, original_title, update_data)

        if success:
            messages.append(TextMessage(text=f"「{field_to_edit}」を「{new_value}」に更新しました。\n他に編集したい項目はありますか？（はい/いいえ）",
                                        quick_reply=QuickReply(items=[
                                            QuickReplyItem(action=MessageAction(label="はい", text="はい")),
                                            QuickReplyItem(action=MessageAction(label="いいえ", text="いいえ"))
                                        ])))
            SessionState.set_state(user_id, SessionState.ASKING_FOR_ANOTHER_SCHEDULE_EDIT)
            # 編集が成功した場合、セッションの編集対象日付とタイトルを更新しておく
            if field_to_edit == "日付":
                session_data['編集対象日付'] = new_value
            elif field_to_edit == "タイトル":
                session_data['編集対象タイトル'] = new_value
        else:
            messages.append(TextMessage(text=f"更新に失敗しました: {msg}\n最初からやり直してください。"))
            SessionState.set_state(user_id, SessionState.NONE)
            # 修正: Config.SESSION_DATA_KEY を削除
            delete_user_session_data(user_id)

    elif current_state == SessionState.ASKING_FOR_ANOTHER_SCHEDULE_EDIT:
        if message_text.lower() == 'はい':
            # 別の項目を編集する場合、再度項目選択に戻る
            SessionState.set_state(user_id, SessionState.ASKING_SCHEDULE_EDIT_FIELD)
            quick_reply_items = [
                QuickReplyItem(action=MessageAction(label="日付", text="日付")),
                QuickReplyItem(action=MessageAction(label="開始時刻", text="開始時刻")),
                QuickReplyItem(action=MessageAction(label="タイトル", text="タイトル")),
                QuickReplyItem(action=MessageAction(label="開催場所", text="開催場所")),
                QuickReplyItem(action=MessageAction(label="詳細", text="詳細")),
                QuickReplyItem(action=MessageAction(label="申込締切日", text="申込締切日")),
                QuickReplyItem(action=MessageAction(label="規模", text="規模")),
                QuickReplyItem(action=MessageAction(label="終了", text="終了"))
            ]
            messages.append(TextMessage(text="他に編集したい項目はありますか？", quick_reply=QuickReply(items=quick_reply_items)))
        else:
            SessionState.set_state(user_id, SessionState.NONE)
            # 修正: Config.SESSION_DATA_KEY を削除
            delete_user_session_data(user_id)
            messages.append(TextMessage(text="スケジュール編集を終了します。"))

    # 修正: Config.SESSION_DATA_KEY を削除
    set_user_session_data(user_id, session_data) # 現在のセッションデータを保存

    if messages:
        line_bot_api_messaging.reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=messages
            )
        )

def start_schedule_deletion(user_id, reply_token, line_bot_api_messaging: MessagingApi):
    print(f"DEBUG: start_schedule_deletion called for user_id: {user_id}")
    SessionState.set_state(user_id, SessionState.ASKING_SCHEDULE_DELETE_DATE)
    # 修正: Config.SESSION_DATA_KEY を削除
    set_user_session_data(user_id, {})
    line_bot_api_messaging.reply_message(
        ReplyMessageRequest(
            reply_token=reply_token,
            messages=[TextMessage(text="削除したいスケジュールの**日付**をYYYY/MM/DD形式で入力してください。\n例: 2025/06/15")]
        )
    )

def process_schedule_deletion_step(user_id, message_text, reply_token, line_bot_api_messaging: MessagingApi):
    print(f"DEBUG: process_schedule_deletion_step called for user_id: {user_id}, message: {message_text}")
    current_state = SessionState.get_state(user_id)
    # 修正: Config.SESSION_DATA_KEY を削除
    session_data = get_user_session_data(user_id) or {}
    messages = []

    if current_state == SessionState.ASKING_SCHEDULE_DELETE_DATE:
        try:
            pd.to_datetime(message_text, errors='raise')
            session_data['削除対象日付'] = message_text
            SessionState.set_state(user_id, SessionState.ASKING_SCHEDULE_DELETE_TITLE)
            messages.append(TextMessage(text="次に、削除したいスケジュールの**タイトル**を入力してください。"))
        except ValueError:
            messages.append(TextMessage(text="日付の形式が正しくありません。YYYY/MM/DD形式で入力してください。\n例: 2025/06/15"))

    elif current_state == SessionState.ASKING_SCHEDULE_DELETE_TITLE:
        session_data['削除対象タイトル'] = message_text.strip()

        # 該当スケジュールが存在するか確認
        schedules_df = get_all_records(Config.GOOGLE_SHEETS_SCHEDULE_WORKSHEET_NAME)

        target_date_str = session_data.get('削除対象日付')
        target_title = session_data.get('削除対象タイトル')

        try:
            target_date_dt = pd.to_datetime(target_date_str).normalize()
            matching_schedules = schedules_df[
                (schedules_df['日付'].apply(lambda x: pd.to_datetime(x, errors='coerce').normalize() if pd.notna(x) else None) == target_date_dt) &
                (schedules_df['タイトル'] == target_title)
            ]
        except ValueError:
            matching_schedules = pd.DataFrame() # 無効な日付の場合は一致なしとする

        if not matching_schedules.empty:
            SessionState.set_state(user_id, SessionState.ASKING_CONFIRM_SCHEDULE_DELETE)
            messages.append(TextMessage(
                text=f"「{session_data['削除対象日付']}」の「{session_data['削除対象タイトル']}」を削除します。よろしいですか？（はい/いいえ）",
                quick_reply=QuickReply(items=[
                    QuickReplyItem(action=MessageAction(label="はい", text="はい")),
                    QuickReplyItem(action=MessageAction(label="いいえ", text="いいえ"))
                ])
            ))
        else:
            SessionState.set_state(user_id, SessionState.NONE)
            # 修正: Config.SESSION_DATA_KEY を削除
            delete_user_session_data(user_id)
            messages.append(TextMessage(text="指定されたスケジュールは見つかりませんでした。\n最初からやり直してください。"))

    elif current_state == SessionState.ASKING_CONFIRM_SCHEDULE_DELETE:
        if message_text.lower() == 'はい':
            # 削除を実行
            date_to_delete = session_data['削除対象日付']
            title_to_delete = session_data['削除対象タイトル']

            success, msg = delete_schedule_by_date_title(date_to_delete, title_to_delete)

            if success:
                messages.append(TextMessage(text="スケジュールを削除しました。\n他に削除したい予定はありますか？（はい/いいえ）",
                                            quick_reply=QuickReply(items=[
                                                QuickReplyItem(action=MessageAction(label="はい", text="はい")),
                                                QuickReplyItem(action=MessageAction(label="いいえ", text="いいえ"))
                                            ])))
                SessionState.set_state(user_id, SessionState.ASKING_FOR_NEXT_SCHEDULE_DELETION)
            else:
                messages.append(TextMessage(text=f"スケジュールの削除に失敗しました: {msg}\n最初からやり直してください。"))
                SessionState.set_state(user_id, SessionState.NONE)
                # 修正: Config.SESSION_DATA_KEY を削除
                delete_user_session_data(user_id)
        else: # いいえ、またはその他の入力
            messages.append(TextMessage(text="スケジュール削除を中止しました。\n他に削除したい予定はありますか？（はい/いいえ）",
                                        quick_reply=QuickReply(items=[
                                            QuickReplyItem(action=MessageAction(label="はい", text="はい")),
                                            QuickReplyItem(action=MessageAction(label="いいえ", text="いいえ"))
                                        ])))
            SessionState.set_state(user_id, SessionState.ASKING_FOR_NEXT_SCHEDULE_DELETION)
            # 修正: Config.SESSION_DATA_KEY を削除
            delete_user_session_data(user_id) # セッションデータは一度クリア

    elif current_state == SessionState.ASKING_FOR_NEXT_SCHEDULE_DELETION:
        if message_text.lower() == 'はい':
            start_schedule_deletion(user_id, reply_token, line_bot_api_messaging)
            return
        else:
            messages.append(TextMessage(text="スケジュール削除を終了します。"))
            SessionState.set_state(user_id, SessionState.NONE)
            # 修正: Config.SESSION_DATA_KEY を削除
            delete_user_session_data(user_id)

    # 修正: Config.SESSION_DATA_KEY を削除
    set_user_session_data(user_id, session_data) # 現在のセッションデータを保存

    if messages:
        line_bot_api_messaging.reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=messages
            )
        )
