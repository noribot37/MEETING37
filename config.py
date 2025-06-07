# config.py

import os

class Config:
    # LINE Bot API設定
    CHANNEL_ACCESS_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
    CHANNEL_SECRET = os.getenv('LINE_CHANNEL_SECRET')

    # Google Sheets API設定 (お客様の指示に従い変数名を修正)
    GOOGLE_SHEETS_CREDENTIALS = os.getenv('GOOGLE_SHEETS_CREDENTIALS') # サービスアカウントキーJSONの内容
    GOOGLE_SHEETS_SPREADSHEET_NAME = "Bot自動化" # お客様のスプレッドシート名に合わせてください
    GOOGLE_SHEETS_SCHEDULE_WORKSHEET_NAME = "シート1" # スケジュールシート名 (お客様の指示に従い"シート1"に)
    GOOGLE_SHEETS_ATTENDEES_WORKSHEET_NAME = "参加者" # 参加者シート名
    GOOGLE_SHEETS_KEY = os.getenv('GOOGLE_SHEETS_KEY') # 未使用の場合、削除またはコメントアウト可能

    # セッション管理用キー
    SESSION_DATA_KEY = 'current_session_data'

    # デフォルト応答メッセージ
    DEFAULT_REPLY_MESSAGE = "「スケジュール登録」「スケジュール一覧」「スケジュール編集」「スケジュール削除」「参加予定登録」「参加予定一覧」「参加予定編集」「参加者一覧」のいずれかのコマンドを入力してください。"

class SessionState:
    _states = {}

    # 初期状態
    NONE = 'none'

    # スケジュール登録の状態
    ASKING_SCHEDULE_DATE = 'asking_schedule_date'
    ASKING_SCHEDULE_TITLE = 'asking_schedule_title'
    ASKING_SCHEDULE_START_TIME = 'asking_schedule_start_time'
    ASKING_SCHEDULE_END_TIME = 'asking_schedule_end_time'
    ASKING_SCHEDULE_LOCATION = 'asking_schedule_location'
    ASKING_SCHEDULE_PERSON_IN_CHARGE = 'asking_schedule_person_in_charge'
    ASKING_SCHEDULE_CONTENT = 'asking_schedule_content'
    ASKING_SCHEDULE_URL = 'asking_schedule_url'
    ASKING_SCHEDULE_NOTES = 'asking_schedule_notes'
    ASKING_CONFIRM_SCHEDULE_REGISTRATION = 'asking_confirm_schedule_registration'
    ASKING_FOR_ANOTHER_SCHEDULE_REGISTRATION = 'asking_for_another_schedule_registration'

    # スケジュール編集の状態
    ASKING_SCHEDULE_EDIT_DATE = 'asking_schedule_edit_date'
    ASKING_SCHEDULE_EDIT_TITLE = 'asking_schedule_edit_title'
    ASKING_SCHEDULE_EDIT_FIELD = 'asking_schedule_edit_field'
    ASKING_SCHEDULE_EDIT_VALUE = 'asking_schedule_edit_value'
    ASKING_FOR_ANOTHER_SCHEDULE_EDIT = 'asking_for_another_schedule_edit'

    # スケジュール削除の状態
    ASKING_SCHEDULE_DELETE_DATE = 'asking_schedule_delete_date'
    ASKING_SCHEDULE_DELETE_TITLE = 'asking_schedule_delete_title'
    ASKING_CONFIRM_SCHEDULE_DELETE = 'asking_confirm_schedule_delete'
    ASKING_FOR_NEXT_SCHEDULE_DELETION = 'asking_for_next_schedule_deletion'

    # 参加予定登録の状態
    ASKING_ATTENDEE_REGISTRATION_DATE = 'asking_attendee_registration_date'
    ASKING_ATTENDEE_REGISTRATION_TITLE = 'asking_attendee_registration_title'
    ASKING_ATTENDEE_STATUS = 'asking_attendee_status'
    ASKING_ATTENDEE_NOTES = 'asking_attendee_notes'
    ASKING_CONFIRM_ATTENDEE_REGISTRATION = 'asking_confirm_attendee_registration'
    ASKING_FOR_ANOTHER_ATTENDEE_REGISTRATION = 'asking_for_another_attendee_registration'

    # 参加予定編集の状態
    ASKING_ATTENDEE_DATE = 'asking_attendee_date'
    ASKING_ATTENDEE_TITLE = 'asking_attendee_title'
    ASKING_ATTENDEE_CONFIRM_CANCEL = 'asking_attendee_confirm_cancel'
    ASKING_ATTENDEE_EDIT_NOTES = 'asking_attendee_edit_notes'
    ASKING_FOR_ANOTHER_ATTENDEE_EDIT = 'asking_for_another_attendee_edit'

    # QA登録の状態
    ASKING_QA_DATE = 'asking_qa_date'
    ASKING_QA_TITLE = 'asking_qa_title'
    ASKING_QA_ATTENDANCE = 'asking_qa_attendance'
    ASKING_QA_NOTES = 'asking_qa_notes'
    ASKING_CONFIRM_QA = 'asking_confirm_qa'

    @classmethod
    def get_state(cls, user_id):
        return cls._states.get(user_id, {}).get('state', cls.NONE)

    @classmethod
    def set_state(cls, user_id, state):
        if user_id not in cls._states:
            cls._states[user_id] = {}
        cls._states[user_id]['state'] = state

    @classmethod
    def delete_state(cls, user_id):
        if user_id in cls._states:
            del cls._states[user_id]['state']

