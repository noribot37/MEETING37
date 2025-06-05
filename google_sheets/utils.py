import gspread
from datetime import datetime

# --- 初期化 ---
# ここでは認証情報は直接記述せず、環境変数またはサービスアカウントキーファイルからの読み込みを想定
# 実際のアプリケーションでは、この部分は main.py や初期化処理で一度だけ行われるべきです。
# gspreadの認証はファイルパスまたはJSON内容で設定します。
# 例: gc = gspread.service_account(filename='path/to/your/service_account.json')
# または、環境変数からJSON文字列を読み込む場合
# import os
# import json
# service_account_info = json.loads(os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON"))
# gc = gspread.service_account_from_dict(service_account_info)

# 注意: このutilsファイルでは直接認証情報を読み込まず、
# 認証済みのクライアントを関数に渡すか、グローバルに利用可能な形で初期化されている前提とします。
# 便宜上、ここではダミーのクライアントを想定しますが、実際には main.py などで適切に初期化してください。
# 例: gc = gspread.service_account() # または .from_dict() など

# --- ヘルパー関数 ---
def get_worksheet(gc, spreadsheet_name, worksheet_name):
    """指定されたスプレッドシートとワークシートを取得するヘルパー関数"""
    try:
        spreadsheet = gc.open(spreadsheet_name)
        # 修正: worksheet_index ではなく worksheet_name でシートを取得
        worksheet = spreadsheet.worksheet(worksheet_name)
        return worksheet
    except gspread.exceptions.SpreadsheetNotFound:
        print(f"Error: Spreadsheet '{spreadsheet_name}' not found.")
        return None
    except gspread.exceptions.WorksheetNotFound:
        print(f"Error: Worksheet '{worksheet_name}' not found in '{spreadsheet_name}'.")
        return None
    except Exception as e:
        print(f"An error occurred while getting worksheet: {e}")
        return None

def add_record(gc, spreadsheet_name, record_data, worksheet_name):
    """
    指定されたワークシートに新しいレコードを追加する。
    record_dataは辞書形式。
    """
    worksheet = get_worksheet(gc, spreadsheet_name, worksheet_name)
    if worksheet is None:
        return False

    try:
        # ヘッダー行を取得
        headers = worksheet.row_values(1)

        # record_data のキーとヘッダーを比較し、適切な順序で値のリストを作成
        values_to_add = [record_data.get(header, '') for header in headers]

        worksheet.append_row(values_to_add)
        print(f"Record added successfully to '{worksheet_name}'.")
        return True
    except Exception as e:
        print(f"Error adding record to '{worksheet_name}': {e}")
        return False

def get_all_records(gc, spreadsheet_name, worksheet_name):
    """
    指定されたワークシートの全てのレコードを辞書のリストとして取得する。
    """
    worksheet = get_worksheet(gc, spreadsheet_name, worksheet_name)
    if worksheet is None:
        return []

    try:
        records = worksheet.get_all_records()
        print(f"Retrieved {len(records)} records from '{worksheet_name}'.")
        return records
    except Exception as e:
        print(f"Error retrieving records from '{worksheet_name}': {e}")
        return []

def delete_record(gc, spreadsheet_name, date_to_delete, title_to_delete, worksheet_name):
    """
    指定されたワークシートから日付とタイトルが一致するレコードを削除する。
    """
    worksheet = get_worksheet(gc, spreadsheet_name, worksheet_name)
    if worksheet is None:
        return False, "ワークシートが見つかりません。"

    try:
        # 全レコードを取得
        records = worksheet.get_all_records()

        # ヘッダー行を取得 (インデックス削除後に新しいヘッダーを書き込むため)
        headers = worksheet.row_values(1)

        # 削除対象の行を特定
        rows_to_keep = []
        deleted_count = 0

        # gspreadのget_all_records()はヘッダー行をスキップするため、
        # 行番号で操作する場合は1を足す必要がある。
        # また、削除すると行番号がずれるため、一度全て取得してから書き直すのが安全。
        all_values = worksheet.get_all_values()

        # 最初の行 (ヘッダー) は常に保持
        rows_to_keep.append(all_values[0])

        for i, row in enumerate(all_values[1:], start=1): # ヘッダーの次の行から開始
            # 辞書形式に変換して比較 (ヘッダーをキーとして使用)
            record_dict = dict(zip(headers, row))

            # 日付とタイトルを正規化して比較
            record_date = record_dict.get('日付', '').strip()
            record_title = record_dict.get('タイトル', '').strip()

            if record_date == date_to_delete.strip() and record_title == title_to_delete.strip():
                deleted_count += 1
                print(f"DEBUG: Deleting row {i+1} for Date: '{record_date}', Title: '{record_title}'")
            else:
                rows_to_keep.append(row)

        if deleted_count > 0:
            # ワークシートをクリアして、残す行を書き込む
            worksheet.clear()
            worksheet.append_rows(rows_to_keep)
            print(f"Deleted {deleted_count} record(s) from '{worksheet_name}'.")
            return True, f"{deleted_count}件のスケジュールを削除しました。"
        else:
            print(f"No matching record found for Date: '{date_to_delete}', Title: '{title_to_delete}' in '{worksheet_name}'.")
            return False, "指定された日付とタイトルのスケジュールは見つかりませんでした。"

    except Exception as e:
        print(f"Error deleting record from '{worksheet_name}': {e}")
        return False, f"スケジュールの削除中にエラーが発生しました: {e}"

def update_record(gc, spreadsheet_name, search_criteria, update_data, worksheet_name):
    """
    指定されたワークシートで検索条件に一致するレコードを更新する。
    search_criteria: 例 {'日付': '2023-04-01', 'タイトル': '会議'}
    update_data: 例 {'場所': 'オンライン', '備考': '議題：新製品開発'}
    """
    worksheet = get_worksheet(gc, spreadsheet_name, worksheet_name)
    if worksheet is None:
        return False, "ワークシートが見つかりません。"

    try:
        # 全レコードと値を取得
        all_values = worksheet.get_all_values()
        if not all_values:
            return False, "ワークシートにデータがありません。"

        headers = all_values[0] # ヘッダー行
        data_rows = all_values[1:] # データ行

        updated_count = 0
        new_all_values = [headers] # 更新後の値を格納するリスト。まずヘッダーを追加

        for i, row_values in enumerate(data_rows):
            record_dict = dict(zip(headers, row_values))

            # 検索条件にすべて一致するか確認
            match = True
            for key, value in search_criteria.items():
                if record_dict.get(key) != value:
                    match = False
                    break

            if match:
                # 更新データを既存のレコードにマージ
                for update_key, update_value in update_data.items():
                    if update_key in headers:
                        col_index = headers.index(update_key)
                        row_values[col_index] = update_value
                updated_count += 1
                print(f"DEBUG: Updated row {i+2} (original index {i+1}) with {update_data}") # +2はヘッダーと0-indexedのため
            new_all_values.append(row_values)

        if updated_count > 0:
            # ワークシートをクリアし、更新されたデータで書き直す
            worksheet.clear()
            worksheet.append_rows(new_all_values)
            print(f"Updated {updated_count} record(s) in '{worksheet_name}'.")
            return True, f"{updated_count}件のスケジュールを更新しました。"
        else:
            print(f"No matching record found for search criteria {search_criteria} in '{worksheet_name}'.")
            return False, "指定された条件に一致するスケジュールは見つかりませんでした。"

    except Exception as e:
        print(f"Error updating record in '{worksheet_name}': {e}")
        return False, f"スケジュールの更新中にエラーが発生しました: {e}"

def sort_sheet_by_date(gc, spreadsheet_name, worksheet_name, date_column_name='日付', sort_order='ASCENDING'):
    """
    指定されたワークシートを日付カラムでソートする。
    date_column_name: 日付が格納されているカラムの名前（例: '日付'）
    sort_order: 'ASCENDING' (昇順) または 'DESCENDING' (降順)
    """
    worksheet = get_worksheet(gc, spreadsheet_name, worksheet_name)
    if worksheet is None:
        return False, "ワークシートが見つかりません。"

    try:
        # ヘッダー行を取得して日付カラムのインデックスを見つける
        headers = worksheet.row_values(1)
        if date_column_name not in headers:
            return False, f"指定された日付カラム名 '{date_column_name}' が見つかりません。"

        date_col_index = headers.index(date_column_name) + 1 # gspreadのsortは1-based index

        # gspreadのsortメソッドを使用
        worksheet.sort((date_col_index, sort_order))
        print(f"Worksheet '{worksheet_name}' sorted by '{date_column_name}' in {sort_order} order.")
        return True, "シートを日付で並べ替えました。"

    except Exception as e:
        print(f"Error sorting worksheet '{worksheet_name}': {e}")
        return False, f"シートの並べ替え中にエラーが発生しました: {e}"


# --- 新規追加・修正が必要な関数 ---

def update_or_add_attendee(gc, spreadsheet_name, user_id, event_date, event_title, attendance_status, note, worksheet_name):
    """
    参加者情報を更新または追加する。
    user_id, event_date, event_title をキーとして、既存のレコードを検索。
    存在すれば更新、なければ新規追加。
    """
    worksheet = get_worksheet(gc, spreadsheet_name, worksheet_name)
    if worksheet is None:
        return False, "ワークシートが見つかりません。"

    try:
        all_values = worksheet.get_all_values()
        if not all_values:
            # ヘッダーがない場合は追加（要検討: 通常は先にヘッダーがあるはず）
            headers = ['ユーザーID', '日付', 'タイトル', '出欠', '備考']
            worksheet.append_row(headers)
            all_values = worksheet.get_all_values() # ヘッダー追加後の状態を再取得

        headers = all_values[0]
        data_rows = all_values[1:]

        user_id_col_index = headers.index('ユーザーID')
        date_col_index = headers.index('日付')
        title_col_index = headers.index('タイトル')
        attendance_col_index = headers.index('出欠')
        note_col_index = headers.index('備考')

        found_row_index = -1
        for i, row_values in enumerate(data_rows):
            if (row_values[user_id_col_index] == user_id and
                row_values[date_col_index] == event_date and
                row_values[title_col_index] == event_title):
                found_row_index = i + 2 # +2はヘッダー行と0-indexedのため
                break

        if found_row_index != -1:
            # 既存レコードを更新
            worksheet.update_cell(found_row_index, attendance_col_index + 1, attendance_status) # +1はgspreadの1-indexedのため
            worksheet.update_cell(found_row_index, note_col_index + 1, note)
            print(f"Attendee record updated for user {user_id} on {event_date} - {event_title}.")
            return True, "参加予定を更新しました。"
        else:
            # 新規レコードを追加
            new_row = [user_id, event_date, event_title, attendance_status, note]
            worksheet.append_row(new_row)
            print(f"New attendee record added for user {user_id} on {event_date} - {event_title}.")
            return True, "参加予定を登録しました。"

    except gspread.exceptions.APIError as e:
        print(f"Google Sheets API Error in update_or_add_attendee: {e}")
        return False, f"Google Sheets APIエラー: {e.args[0]['message']}"
    except ValueError as e:
        print(f"ValueError in update_or_add_attendee (e.g., column not found): {e}")
        return False, f"データ処理エラー: {e}"
    except Exception as e:
        print(f"An unexpected error occurred in update_or_add_attendee: {e}")
        return False, f"予期せぬエラー: {e}"

def delete_row_by_criteria(gc, spreadsheet_name, criteria_dict, worksheet_name):
    """
    指定されたワークシートから、複数の条件に一致する行を削除する。
    criteria_dict: 辞書形式で、{'カラム名': '値'} の形で削除条件を指定。
                   例: {'ユーザーID': 'U1234567890', '日付': '2023-01-01', 'タイトル': '会議'}
    """
    worksheet = get_worksheet(gc, spreadsheet_name, worksheet_name)
    if worksheet is None:
        return False, "ワークシートが見つかりません。"

    try:
        all_values = worksheet.get_all_values()
        if not all_values:
            return False, "ワークシートにデータがありません。"

        headers = all_values[0]
        data_rows = all_values[1:]

        rows_to_keep = [headers] # ヘッダーは常に保持

        deleted_count = 0

        for i, row_values in enumerate(data_rows):
            row_dict = dict(zip(headers, row_values))

            # 全ての条件に一致するかを確認
            match = True
            for key, value in criteria_dict.items():
                if key not in row_dict or row_dict[key] != value:
                    match = False
                    break

            if match:
                deleted_count += 1
                print(f"DEBUG: Deleting row matching criteria: {criteria_dict}")
            else:
                rows_to_keep.append(row_values)

        if deleted_count > 0:
            worksheet.clear()
            worksheet.append_rows(rows_to_keep)
            print(f"Deleted {deleted_count} row(s) matching criteria from '{worksheet_name}'.")
            return True, f"{deleted_count}件のレコードを削除しました。"
        else:
            print(f"No record found matching criteria: {criteria_dict} in '{worksheet_name}'.")
            return False, "指定された条件に一致するレコードは見つかりませんでした。"

    except gspread.exceptions.APIError as e:
        print(f"Google Sheets API Error in delete_row_by_criteria: {e}")
        return False, f"Google Sheets APIエラー: {e.args[0]['message']}"
    except ValueError as e:
        print(f"ValueError in delete_row_by_criteria (e.g., column not found): {e}")
        return False, f"データ処理エラー: {e}"
    except Exception as e:
        print(f"An unexpected error occurred in delete_row_by_criteria: {e}")
        return False, f"予期せぬエラー: {e}"

# 注意:
# このファイルは汎用的なGoogle Sheets操作を提供することを目的としています。
# 認証クライアント (gc) はこのファイルの外部で初期化され、各関数に引数として渡されるか、
# グローバルなコンテキストで利用可能になっている必要があります。
# 例: main.py で gc = gspread.service_account() を行い、それを他の関数に渡す。
