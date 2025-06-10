import os

class Config:
    # Google Sheets API 関連
    # 環境変数から取得するように変更し、デフォルト値もReplitシークレットの設定に合わせて修正
    GOOGLE_SHEETS_CREDENTIALS = os.environ.get('GOOGLE_SHEETS_CREDENTIALS', 'path/to/your/credentials.json') # デフォルト値はGitHubのプレースホルダー
    GOOGLE_SHEETS_SPREADSHEET_NAME = os.environ.get('GOOGLE_SHEETS_SPREADSHEET_NAME', 'meeting_schedule_data') # Replitシークレットの値（meeting_schedule_data）をデフォルトに
    GOOGLE_SHEETS_SCHEDULE_WORKSHEET_NAME = os.environ.get('GOOGLE_SHEETS_SCHEDULE_WORKSHEET_NAME', 'シート1') # Replitシークレットの値（シート1）をデフォルトに
    GOOGLE_SHEETS_ATTENDEES_WORKSHEET_NAME = os.environ.get('GOOGLE_SHEETS_ATTENDEES_WORKSHEET_NAME', '参加者一覧') # 既存の値をデフォルトに
    GOOGLE_SHEETS_KEY = os.environ.get('GOOGLE_SHEETS_KEY', 'your-google-sheets-api-key') # デフォルト値はGitHubのプレースホルダー

    # LINE Bot API 関連
    # 環境変数から取得するように変更
    CHANNEL_ACCESS_TOKEN = os.environ.get('CHANNEL_ACCESS_TOKEN', 'your-channel-access-token') # デフォルト値はGitHubのプレースホルダー
    CHANNEL_SECRET = os.environ.get('CHANNEL_SECRET', 'your-channel-secret') # デフォルト値はGitHubのプレースホルダー

    # デフォルト応答メッセージ
    DEFAULT_REPLY_MESSAGE = "このコマンドは認識できません。利用可能なコマンドは以下の通りです。\n" \
                            "・スケジュール登録\n" \
                            "・スケジュール一覧\n" \
                            "・スケジュール編集\n" \
                            "・スケジュール削除\n" \
                            "・参加予定登録\n" \
                            "・参加予定一覧\n" \
                            "・参加予定編集\n" \
                            "・参加者一覧\n" \
                            "・終了"

    # セッションデータキー
    SESSION_DATA_KEY = 'user_session_data'


class SessionState:
    NONE = "none" # 初期状態またはセッション終了状態

    # スケジュール登録
    ASKING_SCHEDULE_DATE = "asking_schedule_date"
    ASKING_SCHEDULE_TITLE = "asking_schedule_title"
    ASKING_SCHEDULE_START_TIME = "asking_schedule_start_time"
    # ASKING_SCHEDULE_END_TIME を削除済
    ASKING_SCHEDULE_LOCATION = "asking_schedule_location"
    # ASKING_SCHEDULE_PERSON_IN_CHARGE を削除済
    ASKING_SCHEDULE_DETAIL = "asking_schedule_detail" # 変更済
    # ASKING_SCHEDULE_URL を削除済
    # ASKING_SCHEDULE_NOTES を削除済
    ASKING_SCHEDULE_DEADLINE = "asking_schedule_deadline" # 追加済
    ASKING_SCHEDULE_SCALE = "asking_schedule_scale"     # 追加済

    # ASKING_CONFIRM_SCHEDULE_REGISTRATION を削除
    ASKING_FOR_ANOTHER_SCHEDULE_REGISTRATION = "asking_for_another_schedule_registration" # 続けて登録するかの状態

    # スケジュール編集 (変更なし)
    ASKING_SCHEDULE_EDIT_DATE = "asking_schedule_edit_date"
    ASKING_SCHEDULE_EDIT_TITLE = "asking_schedule_edit_title"
    ASKING_SCHEDULE_EDIT_FIELD = "asking_schedule_edit_field"
    ASKING_SCHEDULE_EDIT_VALUE = "asking_schedule_edit_value"
    ASKING_FOR_ANOTHER_SCHEDULE_EDIT = "asking_for_another_schedule_edit"

    # スケジュール削除 (変更なし)
    ASKING_SCHEDULE_DELETE_DATE = "asking_schedule_delete_date"
    ASKING_SCHEDULE_DELETE_TITLE = "asking_schedule_delete_title"
    ASKING_CONFIRM_SCHEDULE_DELETE = "asking_confirm_schedule_delete"
    ASKING_FOR_NEXT_SCHEDULE_DELETION = "asking_for_next_schedule_deletion"

    # 参加予定登録 (attendance_commands) (変更なし)
    ASKING_ATTENDEE_REGISTRATION_DATE = "asking_attendee_registration_date"
    ASKING_ATTENDEE_REGISTRATION_TITLE = "asking_attendee_registration_title"
    ASKING_ATTENDEE_REGISTRATION_STATUS = "asking_attendee_registration_status" # 〇✕△
    ASKING_ATTENDEE_REGISTRATION_NOTES = "asking_attendee_registration_notes"
    ASKING_CONFIRM_ATTENDEE_REGISTRATION = "asking_confirm_attendee_registration"
    ASKING_FOR_ANOTHER_ATTENDEE_REGISTRATION = "asking_for_another_attendee_registration"

    # 参加予定編集 (attendance_commands) (変更なし)
    ASKING_ATTENDEE_EDIT_DATE = "asking_attendee_edit_date"
    ASKING_ATTENDEE_EDIT_TITLE = "asking_attendee_edit_title"
    ASKING_ATTENDEE_CONFIRM_CANCEL = "asking_attendee_confirm_cancel"
    ASKING_ATTENDEE_EDIT_NOTES = "asking_attendee_edit_notes"
    ASKING_FOR_ANOTHER_ATTENDEE_EDIT = "asking_for_another_attendee_edit"

    # スケジュール一覧からの参加希望確認 (list_schedulesから遷移) (変更なし)
    ASKING_ATTENDEE_REGISTRATION_CONFIRMATION = "asking_attendee_registration_confirmation" 

    # attendance_qna.py で使用される状態 (変更なし)
    ASKING_ATTENDANCE_STATUS = "asking_attendance_status" # 〇△×の回答待ち
    ASKING_FOR_REMARKS_CONFIRMATION = "asking_for_remarks_confirmation" # 備考の有無の確認（はい/いいえ）
    ASKING_ATTENDANCE_REMARKS = "asking_attendance_remarks" # 備考の回答待ち
    ASKING_NEXT_ATTENDANCE_REGISTRATION = "asking_next_attendance_registration" # 次の予定があるかどうかの確認

    _user_states = {} # ユーザーごとの状態を保持する辞書

    @classmethod
    def get_state(cls, user_id):
        return cls._user_states.get(user_id, cls.NONE)

    @classmethod
    def set_state(cls, user_id, state):
        cls._user_states[user_id] = state

    @classmethod
    def delete_state(cls, user_id):
        if user_id in cls._user_states:
            del cls._user_states[user_id]
