import pandas as pd
from datetime import datetime
from linebot.v3.messaging import MessagingApi, ReplyMessageRequest, TextMessage, QuickReply, QuickReplyItem
from linebot.v3.messaging.models.postback_action import PostbackAction

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
    print(f"DEBUG: list_user_attendees called for user_id: {user_id}")
    all_attendees_df = get_all_records(Config.GOOGLE_SHEETS_ATTENDEES_WORKSHEET_NAME)

    if all_attendees_df.empty:
        reply_message = "登録されている参加予定はありません。"
        print("DEBUG: Attendees worksheet is empty. No user attendees to display.")
    else:
        # ユーザーIDでフィルタリング
        # カラム名が「参加者ID」であることを確認
        if '参加者ID' not in all_attendees_df.columns:
            print(f"ERROR: '参加者ID' column not found in attendees sheet. Columns: {all_attendees_df.columns.tolist()}")
            reply_message = "参加者シートのデータ形式に問題があります。（参加者ID列が見つかりません）"
        else:
            # ここを「参加者ID」に修正
            user_attendees_df = all_attendees_df[all_attendees_df['参加者ID'] == user_id]

            if user_attendees_df.empty:
                reply_message = "あなたの参加予定は登録されていません。"
                print(f"DEBUG: No attendee records found for user_id: {user_id}.")
            else:
                reply_message = "【あなたの参加予定一覧】\n"
                # 日付でソート（日付がdatetime型であると仮定）
                # '日付'カラムが存在し、かつ空でないことを確認してからpd.to_datetimeを適用
                if '日付' in user_attendees_df.columns and not user_attendees_df['日付'].empty:
                    user_attendees_df['日付'] = pd.to_datetime(user_attendees_df['日付'], errors='coerce')
                    user_attendees_df = user_attendees_df.sort_values(by='日付', ascending=True)
                else:
                    print("WARNING: '日付' column not found or is empty in user attendees DataFrame. Skipping date sort.")
                    # 日付がない場合の代替処理（例: ソートしない）

                for index, row in user_attendees_df.iterrows():
                    date_str = row['日付'].strftime('%Y/%m/%d') if pd.notna(row['日付']) else '日付未定'
                    reply_message += f"日付: {date_str}, タイトル: {row['タイトル']}\n"
                    reply_message += f"  出欠: {row.get('出欠', '未回答')}, 備考: {row.get('備考', 'なし')}\n\n"
                print(f"DEBUG: Successfully prepared {len(user_attendees_df)} attendee records for user {user_id}.")

    line_bot_api_messaging.reply_message(
        ReplyMessageRequest(
            reply_token=reply_token,
            messages=[TextMessage(text=reply_message)]
        )
    )

# 参加者一覧表示（イベントごとの参加者）
def list_attendees(user_id, reply_token, line_bot_api_messaging: MessagingApi):
    print(f"DEBUG: list_attendees called for user_id: {user_id}")
    all_attendees_df = get_all_records(Config.GOOGLE_SHEETS_ATTENDEES_WORKSHEET_NAME)

    if all_attendees_df.empty:
        reply_message = "登録されている参加者情報はありません。"
        print("DEBUG: Attendees worksheet is empty. No attendees to display.")
    else:
        reply_message = "【参加者一覧】\n"

        # '日付'と'タイトル'カラムが存在することを確認
        if '日付' not in all_attendees_df.columns or 'タイトル' not in all_attendees_df.columns:
            print(f"ERROR: Missing '日付' or 'タイトル' column in attendees sheet. Columns: {all_attendees_df.columns.tolist()}")
            reply_message = "参加者シートのデータ形式に問題があります。（日付またはタイトル列が見つかりません）"
        else:
            # 日付をdatetime型に変換し、NaNを除外してからグループ化
            all_attendees_df['日付_dt'] = pd.to_datetime(all_attendees_df['日付'], errors='coerce')

            # 日付が無効な行を除外
            valid_attendees_df = all_attendees_df[pd.notna(all_attendees_df['日付_dt'])]

            if valid_attendees_df.empty:
                 reply_message = "登録されている参加者情報はありません。" # 日付が無効なデータしかない場合
                 print("DEBUG: No valid date entries in attendees worksheet.")
            else:
                # 日付でソートしてからグループ化することで、出力順を保証
                valid_attendees_df = valid_attendees_df.sort_values(by='日付_dt', ascending=True)
                grouped_attendees = valid_attendees_df.groupby(['日付_dt', 'タイトル'])

                for (date, title), group in grouped_attendees:
                    date_str = date.strftime('%Y/%m/%d')
                    attendee_count = len(group)

                    # '参加者名' カラムを使用（もし存在すれば）
                    if '参加者名' in group.columns:
                        attendee_names = ", ".join(group['参加者名'].tolist())
                    elif '参加者ID' in group.columns: # fallback to '参加者ID' if '参加者名' is missing
                        attendee_names = ", ".join(group['参加者ID'].tolist()) # ここを「参加者ID」に修正
                    else:
                        attendee_names = "不明"
                        print("WARNING: '参加者名' and '参加者ID' columns not found in attendees group. Cannot list names.")

                    reply_message += f"日付: {date_str}, タイトル: {title}\n"
                    reply_message += f"  参加者人数: {attendee_count}\n"
                    reply_message += f"  参加者名: {attendee_names}\n\n"
                print(f"DEBUG: Successfully prepared grouped attendee records.")

    line_bot_api_messaging.reply_message(
        ReplyMessageRequest(
            reply_token=reply_token,
            messages=[TextMessage(text=reply_message)]
        )
    )


# 参加予定編集開始
def start_attendee_edit(user_id, reply_token, line_bot_api_messaging: MessagingApi):
    print(f"DEBUG: start_attendee_edit called for user_id: {user_id}")
    SessionState.set_state(user_id, SessionState.ASKING_ATTENDEE_DATE)
    # SessionState がデータを管理するため、Config.SESSION_DATA_KEY は不要
    # 修正: Config.SESSION_DATA_KEY を削除
    set_user_session_data(user_id, {'参加者ID': user_id}) # ここを「参加者ID」に修正
    line_bot_api_messaging.reply_message(
        ReplyMessageRequest(
            reply_token=reply_token,
            messages=[TextMessage(text="編集したい参加予定の日付をYYYY/MM/DD形式で入力してください。\n例: 2025/06/15")]
        )
    )

# 参加予定編集の次のステップ
def process_attendee_edit_step(user_id, message_text, reply_token, line_bot_api_messaging: MessagingApi):
    print(f"DEBUG: process_attendee_edit_step called for user_id: {user_id}, message: {message_text}")
    current_state = SessionState.get_state(user_id)
    # SessionState がデータを管理するため、Config.SESSION_DATA_KEY は不要
    # 修正: Config.SESSION_DATA_KEY を削除
    session_data = get_user_session_data(user_id) or {}

    if current_state == SessionState.ASKING_ATTENDEE_DATE:
        try:
            pd.to_datetime(message_text, errors='raise')
            session_data['日付'] = message_text
            # 修正: Config.SESSION_DATA_KEY を削除
            set_user_session_data(user_id, session_data)
            SessionState.set_state(user_id, SessionState.ASKING_ATTENDEE_TITLE)
            print(f"DEBUG: User {user_id} entered date: {message_text}. Next state: ASKING_ATTENDEE_TITLE.")
            line_bot_api_messaging.reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[TextMessage(text="次に、編集したい参加予定のタイトルを入力してください。")]
                )
            )
        except ValueError:
            print(f"DEBUG: Invalid date format entered by {user_id}: {message_text}")
            line_bot_api_messaging.reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[TextMessage(text="日付の形式が正しくありません。YYYY/MM/DD形式で入力してください。\n例: 2025/06/15")]
                )
            )
    elif current_state == SessionState.ASKING_ATTENDEE_TITLE:
        session_data['タイトル'] = message_text
        # 修正: Config.SESSION_DATA_KEY を削除
        set_user_session_data(user_id, session_data)
        print(f"DEBUG: User {user_id} entered title: {message_text}. Next, check matching attendees.")

        # 該当する参加予定が存在するか確認
        all_attendees = get_all_records(Config.GOOGLE_SHEETS_ATTENDEES_WORKSHEET_NAME)

        # 日付を正規化して比較
        try:
            search_date_str = session_data.get('日付')
            if not search_date_str:
                raise ValueError("Session data missing '日付'.")
            search_date = pd.to_datetime(search_date_str).normalize()
            print(f"DEBUG: Searching for attendees with date: {search_date} and title: {session_data['タイトル']}")
        except ValueError as e:
            print(f"ERROR: Date format error in session data for {user_id}: {e}")
            line_bot_api_messaging.reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[TextMessage(text="日付の形式が正しくありません。最初からやり直してください。")]
                )
            )
            SessionState.set_state(user_id, SessionState.NONE)
            # 修正: Config.SESSION_DATA_KEY を削除
            delete_user_session_data(user_id)
            return

        # '日付'カラムの型がdatetimeであることを確認
        if '日付' in all_attendees.columns and pd.api.types.is_datetime64_any_dtype(all_attendees['日付']):
            matching_attendees = all_attendees[
                (all_attendees['参加者ID'] == user_id) & # ここを「参加者ID」に修正
                (pd.notna(all_attendees['日付']) & (all_attendees['日付'].dt.normalize() == search_date)) &
                (all_attendees['タイトル'] == session_data['タイトル'])
            ]
        else:
            print("WARNING: '日付' column is not datetime type or missing in all_attendees_df. Attempting string comparison.")
            # 日付カラムがdatetime型でない場合のフォールバック（文字列比較）
            matching_attendees = all_attendees[
                (all_attendees['参加者ID'] == user_id) & # ここを「参加者ID」に修正
                (all_attendees['日付'] == search_date_str) & # 文字列として比較
                (all_attendees['タイトル'] == session_data['タイトル'])
            ]

        if not matching_attendees.empty:
            SessionState.set_state(user_id, SessionState.ASKING_ATTENDEE_CONFIRM_CANCEL)
            print(f"DEBUG: Matching attendee found for {user_id}. Asking for cancel confirmation.")
            # クイックリプライを追加
            quick_reply_items = [
                QuickReplyItem(action=PostbackAction(label="はい", data="はい", display_text="はい")),
                QuickReplyItem(action=PostbackAction(label="いいえ", data="いいえ", display_text="いいえ"))
            ]
            line_bot_api_messaging.reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[TextMessage(text="この参加予定をキャンセルしますか？（はい/いいえ）\n「いいえ」の場合、備考を編集します。",
                                          quick_reply=QuickReply(items=quick_reply_items))]
                )
            )
        else:
            print(f"DEBUG: No matching attendee found for {user_id} with date {search_date_str} and title {session_data['タイトル']}.")
            SessionState.set_state(user_id, SessionState.NONE)
            # 修正: Config.SESSION_DATA_KEY を削除
            delete_user_session_data(user_id)
            line_bot_api_messaging.reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[TextMessage(text="指定された参加予定は見つかりませんでした。最初からやり直してください。")]
                )
            )
    elif current_state == SessionState.ASKING_ATTENDEE_CONFIRM_CANCEL:
        print(f"DEBUG: User {user_id} chose to cancel or edit notes: {message_text}")
        if message_text.lower() == 'はい':
            # 参加予定を削除
            criteria = {
                '参加者ID': user_id, # ここを「参加者ID」に修正
                '日付': session_data['日付'], # 文字列形式の日付を使用
                'タイトル': session_data['タイトル']
            }
            if delete_row_by_criteria(Config.GOOGLE_SHEETS_ATTENDEES_WORKSHEET_NAME, criteria):
                reply_message = "参加予定をキャンセルしました。\n他に編集したい予定はありますか？（はい/いいえ）"
                SessionState.set_state(user_id, SessionState.ASKING_FOR_ANOTHER_ATTENDEE_EDIT)
                print(f"DEBUG: Attendee record for {user_id} cancelled.")
            else:
                reply_message = "参加予定のキャンセルに失敗しました。最初からやり直してください。"
                SessionState.set_state(user_id, SessionState.NONE)
                print(f"ERROR: Failed to cancel attendee record for {user_id}.")
            # 修正: Config.SESSION_DATA_KEY を削除
            delete_user_session_data(user_id)
            line_bot_api_messaging.reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[TextMessage(text=reply_message,
                                          quick_reply=QuickReply(items=[
                                              QuickReplyItem(action=PostbackAction(label="はい", data="はい", display_text="はい")),
                                              QuickReplyItem(action=PostbackAction(label="いいえ", data="いいえ", display_text="いいえ"))
                                          ]))]
                )
            )
        else: # 'いいえ' の場合、備考編集へ
            SessionState.set_state(user_id, SessionState.ASKING_ATTENDEE_EDIT_NOTES)
            print(f"DEBUG: User {user_id} chose not to cancel. Next state: ASKING_ATTENDEE_EDIT_NOTES.")
            line_bot_api_messaging.reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[TextMessage(text="新しい備考を入力してください。（ない場合は「なし」）")]
                )
            )
    elif current_state == SessionState.ASKING_ATTENDEE_EDIT_NOTES:
        new_notes = message_text
        session_data['備考'] = new_notes

        # update_or_add_attendee は、既存があれば更新、なければ追加。
        # 既存のレコードを特定し、備考のみを更新する
        # この関数は引数として個々のデータを受け取るため、session_dataから展開
        # username がセッションデータにない場合は、一旦 user_id を使用
        username = session_data.get('参加者名', user_id) # 暫定的にuser_idをusernameとして使用。ここを「参加者名」に修正

        success, msg = update_or_add_attendee(
            date=session_data.get('日付'),
            title=session_data.get('タイトル'),
            user_id=session_data.get('参加者ID'), # ここを「参加者ID」に修正
            username=username,
            attendance_status=session_data.get('出欠', '未回答'), # 出欠は更新時に必要
            notes=new_notes
        )

        if success:
            reply_message = "備考を更新しました。\n他に編集したい予定はありますか？（はい/いいえ）"
            SessionState.set_state(user_id, SessionState.ASKING_FOR_ANOTHER_ATTENDEE_EDIT)
            print(f"DEBUG: Notes for {user_id} updated successfully.")
        else:
            reply_message = f"備考の更新に失敗しました。{msg} 最初からやり直してください。"
            SessionState.set_state(user_id, SessionState.NONE)
            print(f"ERROR: Failed to update notes for {user_id}: {msg}")

        # 修正: Config.SESSION_DATA_KEY を削除
        delete_user_session_data(user_id)
        line_bot_api_messaging.reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[TextMessage(text=reply_message,
                                      quick_reply=QuickReply(items=[
                                          QuickReplyItem(action=PostbackAction(label="はい", data="はい", display_text="はい")),
                                          QuickReplyItem(action=PostbackAction(label="いいえ", data="いいえ", display_text="いいえ"))
                                      ]))]
            )
        )
    elif current_state == SessionState.ASKING_FOR_ANOTHER_ATTENDEE_EDIT:
        print(f"DEBUG: User {user_id} chose to continue/end attendee edit: {message_text}")
        if message_text.lower() == 'はい':
            start_attendee_edit(user_id, reply_token, line_bot_api_messaging)
        else:
            SessionState.set_state(user_id, SessionState.NONE)
            # 修正: Config.SESSION_DATA_KEY を削除
            delete_user_session_data(user_id)
            line_bot_api_messaging.reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[TextMessage(text="参加予定編集を終了します。")]
                )
            )

# 参加予定登録開始
def start_attendee_registration(user_id, reply_token, line_bot_api_messaging: MessagingApi):
    print(f"DEBUG: start_attendee_registration called for user_id: {user_id}")
    SessionState.set_state(user_id, SessionState.ASKING_ATTENDEE_REGISTRATION_DATE)
    # SessionState がデータを管理するため、Config.SESSION_DATA_KEY は不要
    # 修正: Config.SESSION_DATA_KEY を削除
    set_user_session_data(user_id, {'参加者ID': user_id}) # ここを「参加者ID」に修正
    line_bot_api_messaging.reply_message(
        ReplyMessageRequest(
            reply_token=reply_token,
            messages=[TextMessage(text="参加したいスケジュールの日付をYYYY/MM/DD形式で入力してください。\n例: 2025/06/15")]
        )
    )

# 参加予定登録の次のステップ
def process_attendee_registration_step(user_id, message_text, reply_token, line_bot_api_messaging: MessagingApi):
    print(f"DEBUG: process_attendee_registration_step called for user_id: {user_id}, message: {message_text}")
    current_state = SessionState.get_state(user_id)
    # SessionState がデータを管理するため、Config.SESSION_DATA_KEY は不要
    # 修正: Config.SESSION_DATA_KEY を削除
    session_data = get_user_session_data(user_id) or {}

    if current_state == SessionState.ASKING_ATTENDEE_REGISTRATION_DATE:
        try:
            pd.to_datetime(message_text, errors='raise')
            session_data['日付'] = message_text
            # 修正: Config.SESSION_DATA_KEY を削除
            set_user_session_data(user_id, session_data)
            SessionState.set_state(user_id, SessionState.ASKING_ATTENDEE_REGISTRATION_TITLE)
            print(f"DEBUG: User {user_id} entered date: {message_text}. Next state: ASKING_ATTENDEE_REGISTRATION_TITLE.")
            line_bot_api_messaging.reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[TextMessage(text="次に、参加したいスケジュールのタイトルを入力してください。")]
                )
            )
        except ValueError:
            print(f"DEBUG: Invalid date format entered by {user_id}: {message_text}")
            line_bot_api_messaging.reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[TextMessage(text="日付の形式が正しくありません。YYYY/MM/DD形式で入力してください。\n例: 2025/06/15")]
                )
            )
    elif current_state == SessionState.ASKING_ATTENDEE_REGISTRATION_TITLE:
        session_data['タイトル'] = message_text
        # 修正: Config.SESSION_DATA_KEY を削除
        set_user_session_data(user_id, session_data)
        SessionState.set_state(user_id, SessionState.ASKING_ATTENDEE_STATUS)
        print(f"DEBUG: User {user_id} entered title: {message_text}. Next state: ASKING_ATTENDEE_STATUS.")
        line_bot_api_messaging.reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[TextMessage(text="出欠を入力してください。（例: 〇、✕、△）",
                                      quick_reply=QuickReply(items=[
                                          QuickReplyItem(action=PostbackAction(label="〇", data="〇", display_text="〇")),
                                          QuickReplyItem(action=PostbackAction(label="✕", data="✕", display_text="✕")),
                                          QuickReplyItem(action=PostbackAction(label="△", data="△", display_text="△"))
                                      ]))]
            )
        )
    elif current_state == SessionState.ASKING_ATTENDEE_STATUS:
        attendee_status = message_text
        if attendee_status in ['〇', '○', 'x', 'X', '✕', '△', '▲']: # 許容される出欠の文字
            session_data['出欠'] = attendee_status
            # 修正: Config.SESSION_DATA_KEY を削除
            set_user_session_data(user_id, session_data)
            SessionState.set_state(user_id, SessionState.ASKING_ATTENDEE_NOTES)
            print(f"DEBUG: User {user_id} entered status: {message_text}. Next state: ASKING_ATTENDEE_NOTES.")
            line_bot_api_messaging.reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[TextMessage(text="備考を入力してください。（ない場合は「なし」）")]
                )
            )
        else:
            print(f"DEBUG: Invalid status entered by {user_id}: {message_text}")
            line_bot_api_messaging.reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[TextMessage(text="出欠は「〇」「✕」「△」のいずれかで入力してください。",
                                          quick_reply=QuickReply(items=[
                                              QuickReplyItem(action=PostbackAction(label="〇", data="〇", display_text="〇")),
                                              QuickReplyItem(action=PostbackAction(label="✕", data="✕", display_text="✕")),
                                              QuickReplyItem(action=PostbackAction(label="△", data="△", display_text="△"))
                                          ]))]
            )
        )
    elif current_state == SessionState.ASKING_ATTENDEE_NOTES:
        session_data['備考'] = message_text
        # 修正: Config.SESSION_DATA_KEY を削除
        set_user_session_data(user_id, session_data)
        SessionState.set_state(user_id, SessionState.ASKING_CONFIRM_ATTENDEE_REGISTRATION)
        print(f"DEBUG: User {user_id} entered notes: {message_text}. Next state: ASKING_CONFIRM_ATTENDEE_REGISTRATION.")

        confirm_message = "以下の内容で参加予定を登録します。よろしいですか？\n"
        for key, value in session_data.items():
            confirm_message += f"{key}: {value}\n"
        confirm_message += "はい / いいえ"

        line_bot_api_messaging.reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[TextMessage(text=confirm_message,
                                      quick_reply=QuickReply(items=[
                                          QuickReplyItem(action=PostbackAction(label="はい", data="はい", display_text="はい")),
                                          QuickReplyItem(action=PostbackAction(label="いいえ", data="いいえ", display_text="いいえ"))
                                      ]))]
            )
        )
    elif current_state == SessionState.ASKING_CONFIRM_ATTENDEE_REGISTRATION:
        print(f"DEBUG: User {user_id} confirmed registration: {message_text}")
        if message_text.lower() == 'はい':
            # 参加者名を取得（暫定的にユーザーIDを使用するか、別の方法で取得）
            # LINEのプロフィールから取得するロジックが main.py などにあるはず
            # ここでは便宜上、ユーザーIDをそのまま渡すか、セッションデータに username があればそれを使う
            username = session_data.get('参加者名', user_id) # ユーザー名がセッションデータにあればそれを使う。ここを「参加者名」に修正

            success, msg = update_or_add_attendee(
                date=session_data.get('日付'),
                title=session_data.get('タイトル'),
                user_id=session_data.get('参加者ID'), # ここを「参加者ID」に修正
                username=username,
                attendance_status=session_data.get('出欠'),
                notes=session_data.get('備考')
            )

            if success:
                reply_message = "参加予定を登録しました。\n他に登録したい参加予定はありますか？（はい/いいえ）"
                SessionState.set_state(user_id, SessionState.ASKING_FOR_ANOTHER_ATTENDEE_REGISTRATION)
                print(f"DEBUG: Attendee registration for {user_id} successful.")
            else:
                reply_message = f"参加予定の登録に失敗しました。{msg} 最初からやり直してください。"
                SessionState.set_state(user_id, SessionState.NONE)
                print(f"ERROR: Attendee registration for {user_id} failed: {msg}")

            # 修正: Config.SESSION_DATA_KEY を削除
            delete_user_session_data(user_id)
            line_bot_api_messaging.reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[TextMessage(text=reply_message,
                                          quick_reply=QuickReply(items=[
                                              QuickReplyItem(action=PostbackAction(label="はい", data="はい", display_text="はい")),
                                              QuickReplyItem(action=PostbackAction(label="いいえ", data="いいえ", display_text="いいえ"))
                                          ]))]
                )
            )
        else:
            SessionState.set_state(user_id, SessionState.NONE)
            # 修正: Config.SESSION_DATA_KEY を削除
            delete_user_session_data(user_id)
            print(f"DEBUG: User {user_id} cancelled registration.")
            line_bot_api_messaging.reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[TextMessage(text="参加予定登録をキャンセルしました。")]
                )
            )
    elif current_state == SessionState.ASKING_FOR_ANOTHER_ATTENDEE_REGISTRATION:
        print(f"DEBUG: User {user_id} chose to continue/end registration: {message_text}")
        if message_text.lower() == 'はい':
            start_attendee_registration(user_id, reply_token, line_bot_api_messaging)
        else:
            SessionState.set_state(user_id, SessionState.NONE)
            # 修正: Config.SESSION_DATA_KEY を削除
            delete_user_session_data(user_id)
            line_bot_api_messaging.reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[TextMessage(text="参加予定登録を終了します。")]
                )
            )

