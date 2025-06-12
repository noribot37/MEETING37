import gspread
import pandas as pd
import json
import os
from datetime import datetime

from config import Config

def _get_sheets_client():
    """Google Sheets APIクライアントを認証して取得します。"""
    try:
        # 環境変数からJSON文字列として認証情報を取得
        credentials_json = Config.GOOGLE_SHEETS_CREDENTIALS
        if not credentials_json:
            raise ValueError("Google Sheets credentials (GOOGLE_SHEETS_CREDENTIALS) not set in environment variables.")

        # JSON文字列をPython辞書に変換
        credentials_info = json.loads(credentials_json)

        gc = gspread.service_account_from_dict(credentials_info)
        spreadsheet = gc.open(Config.GOOGLE_SHEETS_SPREADSHEET_NAME)
        print("DEBUG: Google Sheets service account authenticated successfully.")
        print(f"DEBUG: Spreadsheet '{Config.GOOGLE_SHEETS_SPREADSHEET_NAME}' opened successfully.")
        return gc, spreadsheet
    except Exception as e:
        print(f"ERROR: Failed to authenticate or open spreadsheet: {e}")
        raise

def get_all_records(worksheet_name: str) -> pd.DataFrame:
    """
    指定されたワークシートの全てのレコードをDataFrameとして取得します。
    :param worksheet_name: 取得するワークシートの名前
    :return: レコードを含むPandas DataFrame。エラー時は空のDataFrameを返します。
    """
    try:
        gc, spreadsheet = _get_sheets_client()
        worksheet = spreadsheet.worksheet(worksheet_name)
        records = worksheet.get_all_records()
        if not records:
            return pd.DataFrame() # レコードがない場合は空のDataFrameを返す
        df = pd.DataFrame(records)
        return df
    except gspread.exceptions.WorksheetNotFound:
        print(f"ERROR: Worksheet '{worksheet_name}' not found.")
        return pd.DataFrame()
    except Exception as e:
        print(f"ERROR: Failed to get records from '{worksheet_name}': {e}")
        return pd.DataFrame()

def add_schedule(schedule_data: dict) -> tuple[bool, str]:
    """
    新しいスケジュールをスプレッドシートに追加します。
    :param schedule_data: スケジュールデータを含む辞書。キーは列名と一致する必要があります。
    :return: 成功した場合は (True, "成功メッセージ")、失敗した場合は (False, "エラーメッセージ")
    """
    try:
        gc, spreadsheet = _get_sheets_client()
        worksheet = spreadsheet.worksheet(Config.GOOGLE_SHEETS_SCHEDULE_WORKSHEET_NAME)

        # スプレッドシートのヘッダーを取得
        headers = worksheet.row_values(1)

        # schedule_dataをヘッダーの順序に並べ替えてリストにする
        row_to_insert = [schedule_data.get(header, '') for header in headers]

        worksheet.append_row(row_to_insert)

        # 日付カラムでソート（日付がYYYY/MM/DD形式であると仮定）
        # まず全てのレコードを取得
        all_records_df = get_all_records(Config.GOOGLE_SHEETS_SCHEDULE_WORKSHEET_NAME)
        if not all_records_df.empty:
            # 日付をdatetime型に変換し、変換できないものはNaT (Not a Time) とする
            all_records_df['日付'] = pd.to_datetime(all_records_df['日付'], errors='coerce')
            # 日付でソートし、日付がNaTのものを最後に持ってくる
            sorted_df = all_records_df.sort_values(by='日付', ascending=True, na_position='last')

            # ソートされたDataFrameをスプレッドシートに書き戻す
            # ヘッダー行を再度含めて書き込む必要がある
            worksheet.clear()
            worksheet.update([sorted_df.columns.values.tolist()] + sorted_df.fillna('').values.tolist())


        return True, "スケジュールが正常に登録されました。"
    except Exception as e:
        print(f"ERROR: Failed to add schedule: {e}")
        return False, f"スケジュールの登録中にエラーが発生しました: {e}"


def update_schedule(original_date_str: str, original_title: str, update_data: dict) -> tuple[bool, str]:
    """
    指定された日付とタイトルのスケジュールを検索し、update_dataに基づいて更新します。
    日付とタイトルは既存レコードの特定に使用されます。
    :param original_date_str: 検索するスケジュールの元のYYYY/MM/DD形式の日付文字列
    :param original_title: 検索するスケジュールの元のタイトル
    :param update_data: 更新するカラムとその新しい値を含む辞書 (例: {'開催場所': '新しい場所'})
    :return: 成功した場合は (True, "更新成功メッセージ")、失敗した場合は (False, "エラーメッセージ")
    """
    try:
        gc, spreadsheet = _get_sheets_client()
        worksheet = spreadsheet.worksheet(Config.GOOGLE_SHEETS_SCHEDULE_WORKSHEET_NAME)
        records = worksheet.get_all_records()

        if not records:
            return False, "スケジュールデータが見つかりません。"

        df = pd.DataFrame(records)

        # 厳密に比較するために、元の文字列形式の日付とタイトルでフィルタリング
        # .copy() を使用して SettingWithCopyWarning を回避
        matching_rows = df[(df['日付'] == original_date_str) & (df['タイトル'] == original_title)].copy()

        if matching_rows.empty:
            return False, f"日付「{original_date_str}」タイトル「{original_title}」のスケジュールは見つかりませんでした。"

        # 最初のマッチした行を更新対象とする（通常は一意であることを期待）
        # gspreadは1-based index (ヘッダー行が1行目なのでデータは2行目から)
        row_index_to_update = matching_rows.index[0] + 2 # +2 はヘッダー行と0-based indexのため

        # update_data を元にセルを更新
        updated_cells = []
        for col_name, new_value in update_data.items():
            if col_name in df.columns:
                col_index = df.columns.get_loc(col_name) + 1 # gspreadは1-based index
                worksheet.update_cell(row_index_to_update, col_index, str(new_value))
                updated_cells.append(col_name)
            else:
                print(f"WARNING: Column '{col_name}' not found in schedule worksheet. Skipping update for this column.")

        if updated_cells:
            return True, f"スケジュールが更新されました: {', '.join(updated_cells)}"
        else:
            return False, "更新対象の項目が見つかりませんでした。"

    except Exception as e:
        print(f"ERROR: Error updating schedule: {e}")
        return False, f"スケジュールの更新中にエラーが発生しました: {e}"


def delete_schedule_by_date_title(date_str: str, title: str) -> tuple[bool, str]:
    """
    指定された日付とタイトルのスケジュールをスプレッドシートから削除します。
    :param date_str: 削除するスケジュールのYYYY/MM/DD形式の日付文字列
    :param title: 削除するスケジュールのタイトル
    :return: 成功した場合は (True, "成功メッセージ")、失敗した場合は (False, "エラーメッセージ")
    """
    try:
        gc, spreadsheet = _get_sheets_client()
        worksheet = spreadsheet.worksheet(Config.GOOGLE_SHEETS_SCHEDULE_WORKSHEET_NAME)
        records = worksheet.get_all_records()

        if not records:
            return False, "スケジュールデータが見つかりません。"

        df = pd.DataFrame(records)

        # 検索条件に合致する行を見つける
        # `errors='coerce'` を使用して無効な日付をNaTに変換し、それを除外して比較
        df['日付_dt'] = pd.to_datetime(df['日付'], errors='coerce')

        # 削除対象日付をdatetimeオブジェクトに変換して正規化
        target_date_dt = pd.to_datetime(date_str).normalize()

        matching_rows = df[
            (df['日付_dt'].dt.normalize() == target_date_dt) &
            (df['タイトル'] == title)
        ]

        if matching_rows.empty:
            return False, f"日付「{date_str}」タイトル「{title}」のスケジュールは見つかりませんでした。"

        # 最初のマッチした行を削除対象とする
        # gspreadは1-based index (ヘッダー行が1行目なのでデータは2行目から)
        row_index_to_delete = matching_rows.index[0] + 2 # +2 はヘッダー行と0-based indexのため

        worksheet.delete_rows(row_index_to_delete)

        return True, "スケジュールが正常に削除されました。"
    except Exception as e:
        print(f"ERROR: Error deleting schedule: {e}")
        return False, f"スケジュールの削除中にエラーが発生しました: {e}"


def update_or_add_attendee(date: str, title: str, user_id: str, username: str, attendance_status: str, notes: str) -> tuple[bool, str]:
    """
    参加者情報を更新または追加します。
    既存の参加予定があれば更新し、なければ新規追加します。
    :param date: スケジュールの日付 (YYYY/MM/DD)
    :param title: スケジュールのタイトル
    :param user_id: LINEユーザーID
    :param username: LINE表示名
    :param attendance_status: 出欠ステータス (〇, △, ×)
    :param notes: 備考
    :return: 成功した場合は (True, "成功メッセージ")、失敗した場合は (False, "エラーメッセージ")
    """
    try:
        gc, spreadsheet = _get_sheets_client()
        worksheet = spreadsheet.worksheet(Config.GOOGLE_SHEETS_ATTENDEES_WORKSHEET_NAME)

        # 既存のレコードを全て取得
        records = worksheet.get_all_records()
        df = pd.DataFrame(records)

        # 検索条件に合致する行を探す
        # 日付とタイトルと参加者IDが一致するものを探す
        matching_row = df[
            (df['日付'] == date) &
            (df['タイトル'] == title) &
            (df['参加者ID'] == user_id) # ここを「参加者ID」に修正
        ]

        if not matching_row.empty:
            # 既存のレコードを更新
            row_index_to_update = matching_row.index[0] + 2 # +2 はヘッダー行と0-based indexのため

            update_data = {
                '出欠': attendance_status,
                '備考': notes,
                '更新日時': datetime.now().strftime(Config.DATETIME_FORMAT)
            }

            # 各カラムを個別に更新
            headers = worksheet.row_values(1)
            for col_name, new_value in update_data.items():
                if col_name in headers:
                    col_index = headers.index(col_name) + 1 # gspreadは1-based index
                    worksheet.update_cell(row_index_to_update, col_index, str(new_value))

            return True, "参加予定を更新しました。"
        else:
            # 新規レコードとして追加
            new_attendee_data = {
                '日付': date,
                'タイトル': title,
                '参加者ID': user_id, # ここを「参加者ID」に修正
                '参加者名': username, # ここを「参加者名」に修正
                '出欠': attendance_status,
                '備考': notes,
                '登録日時': datetime.now().strftime(Config.DATETIME_FORMAT),
                '更新日時': datetime.now().strftime(Config.DATETIME_FORMAT)
            }

            # ヘッダーの順序に合わせてデータを整形
            headers = worksheet.row_values(1)
            row_to_insert = [new_attendee_data.get(header, '') for header in headers]

            worksheet.append_row(row_to_insert)

            return True, "参加予定を新規登録しました。"

    except Exception as e:
        print(f"ERROR: Failed to update or add attendee: {e}")
        return False, f"参加予定の登録/更新中にエラーが発生しました: {e}"

def get_attendees_for_user(user_id: str) -> list[list[str]]:
    """
    指定されたユーザーIDの参加予定をリスト形式で取得します。
    :param user_id: 検索するLINEユーザーID
    :return: ユーザーの参加予定リスト (例: [['タイトル', '日付', '出欠', '備考'], ...])
    """
    try:
        gc, spreadsheet = _get_sheets_client()
        worksheet = spreadsheet.worksheet(Config.GOOGLE_SHEETS_ATTENDEES_WORKSHEET_NAME)
        records = worksheet.get_all_records()

        user_attendees = []
        if records:
            df = pd.DataFrame(records)
            # '参加者ID' 列が存在することを確認
            if '参加者ID' in df.columns: # ここを「参加者ID」に修正
                filtered_df = df[df['参加者ID'] == user_id] # ここを「参加者ID」に修正
                # 必要なカラムを抽出してリストのリストとして返す
                # 例: 日付、タイトル、出欠、備考
                if not filtered_df.empty:
                    user_attendees = filtered_df[['タイトル', '日付', '出欠', '備考']].values.tolist()
            else:
                print("WARNING: '参加者ID' column not found in attendees sheet for filtering.") # ここを「参加者ID」に修正

        return user_attendees
    except Exception as e:
        print(f"ERROR: Failed to get attendees for user {user_id}: {e}")
        return []

def delete_row_by_criteria(worksheet_name: str, criteria: dict) -> bool:
    """
    指定されたワークシートから、複数の条件に合致する最初の行を削除します。
    :param worksheet_name: 操作対象のワークシート名
    :param criteria: 削除対象を特定するためのカラム名と値の辞書 (例: {'日付': '2025/06/15', 'タイトル': '会議'})
    :return: 削除に成功した場合はTrue、失敗した場合はFalse
    """
    try:
        gc, spreadsheet = _get_sheets_client()
        worksheet = spreadsheet.worksheet(worksheet_name)
        records = worksheet.get_all_records()

        if not records:
            print(f"DEBUG: No records found in worksheet '{worksheet_name}'.")
            return False

        df = pd.DataFrame(records)

        # 複数条件でのフィルタリング
        # 日付の比較は文字列で厳密に行う
        # 他の条件も全て文字列として比較

        # 各基準の条件をANDで結合
        conditions = pd.Series([True] * len(df)) # 全ての行がTrueで初期化
        for col, val in criteria.items():
            if col in df.columns:
                conditions = conditions & (df[col] == val)
            else:
                print(f"WARNING: Criteria column '{col}' not found in worksheet '{worksheet_name}'. Skipping this criterion.")
                return False # 存在しないカラムで削除条件を提示されたら失敗とする

        matching_rows = df[conditions]

        if matching_rows.empty:
            print(f"DEBUG: No matching row found for deletion in worksheet '{worksheet_name}' with criteria: {criteria}")
            return False

        # 最初のマッチした行を削除
        # gspreadは1-based index (ヘッダー行が1行目なのでデータは2行目から)
        row_index_to_delete = matching_rows.index[0] + 2 

        worksheet.delete_rows(row_index_to_delete)
        print(f"DEBUG: Successfully deleted row {row_index_to_delete} from worksheet '{worksheet_name}'.")
        return True

    except Exception as e:
        print(f"ERROR: Error deleting row from worksheet '{worksheet_name}': {e}")
        return False
