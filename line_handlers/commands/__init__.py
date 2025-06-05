# line_handlers/commands/__init__.py
# このファイルで各コマンドモジュールから必要な関数を直接インポートします

# schedule_commands.py から必要な関数を直接インポート
from .schedule_commands import start_schedule_registration
from .schedule_commands import handle_schedule_registration
from .schedule_commands import start_schedule_deletion
from .schedule_commands import handle_schedule_deletion
from .schedule_commands import start_schedule_editing
from .schedule_commands import handle_schedule_editing
from .schedule_commands import list_schedules

# attendance_commands.py から必要な関数を直接インポート
from .attendance_commands import list_participants # list_attendees を list_participants に修正
from .attendance_commands import list_my_planned_events # list_scheduled_attendees を list_my_planned_events に修正
from .attendance_commands import start_attendance_editing # TODOを解除
from .attendance_commands import handle_attendance_editing # TODOを解除

# general_commands.py から必要な関数を直接インポート (現在コメントアウト)
# TODO: from .general_commands import handle_help_command

# __all__ リストは削除します。
# これにより、message_processors.py からは各関数が直接インポートされるようになります。
