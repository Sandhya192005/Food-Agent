"""store weekly menu day_of_week as an enum name

Revision ID: eec4124e60ff
Revises: d5c35e1e1d33
Create Date: 2026-09-08 12:36:41.164432

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'eec4124e60ff'
down_revision: Union[str, None] = 'd5c35e1e1d33'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Column previously stored 0=Monday..6=Sunday (Python's datetime.weekday()
# convention); the new enum stores the day name directly, matching how
# meal_type is already stored (as the Python Enum member NAME, e.g. 'MONDAY').
_INT_TO_ENUM_LABEL = {
    0: "MONDAY",
    1: "TUESDAY",
    2: "WEDNESDAY",
    3: "THURSDAY",
    4: "FRIDAY",
    5: "SATURDAY",
    6: "SUNDAY",
}


def upgrade() -> None:
    day_of_week_enum = sa.Enum(
        "MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY",
        name="dayofweek",
    )
    day_of_week_enum.create(op.get_bind())

    case_sql = " ".join(
        f"WHEN {i} THEN '{label}'" for i, label in _INT_TO_ENUM_LABEL.items()
    )
    op.execute(
        f"""
        ALTER TABLE weekly_menus
        ALTER COLUMN day_of_week TYPE dayofweek
        USING (CASE day_of_week {case_sql} END)::dayofweek
        """
    )


def downgrade() -> None:
    case_sql = " ".join(
        f"WHEN '{label}' THEN {i}" for i, label in _INT_TO_ENUM_LABEL.items()
    )
    op.execute(
        f"""
        ALTER TABLE weekly_menus
        ALTER COLUMN day_of_week TYPE INTEGER
        USING (CASE day_of_week {case_sql} END)
        """
    )
    sa.Enum(name="dayofweek").drop(op.get_bind())
