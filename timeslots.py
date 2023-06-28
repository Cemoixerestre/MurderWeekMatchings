from __future__ import annotations

from datetime import datetime
from typing import List, Dict

SLOT_TIMES = {
    'matin': ('08:00', '13:00'),
    'après-midi': ('13:00', '18:00'),
    'soir': ('18:00', '23:59')
}

WEEK_DAYS = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche']

EVENT_DAY_START = 19
YEAR = "2023"
MONTH = "08"

class TimeSlot:
    def __init__(self, day_name: Option[str], start: datetime, end: datetime):
        self.start = start
        self.end = end
        assert self.start.day == self.end.day, \
            "Error: the start and the end of a time slot must be on the same " \
            f"day. Erroneous dates: start = {start} and end = {end}."
        assert self.start < self.end, \
            "Error: time slot should starts before it ends. " \
            f"day. Erroneous dates: start = {start} and end = {end}."

        self.day_name: str = WEEK_DAYS[start.weekday()]
        if day_name is not None:
            assert self.day_name == day_name

    def overlaps(self, other: TimeSlot) -> bool:
        if (self.start <= other.start) and (other.start < self.end):
            return True
        elif (other.start <= self.start) and (self.start < other.end):
            return True
        else:
            return False

    def __repr__(self):
        start_hour = f"{self.start.hour:02}:{self.start.minute:02}"
        end_hour = f"{self.end.hour:02}:{self.end.minute:02}"
        return f"{self.start.day:02}/{MONTH} {start_hour}-{end_hour}"

    def disp_day(self) -> str:
        return f"{self.day_name} {self.start.day}"

    def disp_hour(self) -> str:
        return f"{self.start.hour:02}:{self.start.minute:02}-" \
               f"{self.end.hour:02}:{self.end.minute:02}"

def generate_timeslots_from_column_names(column_names: List[str]) -> Dict[str, TimeSlot]:
    res = dict()
    for col in column_names:
        fields = col.split(' ')
        day_name = fields[0]
        day_nb = int(fields[1])
        slot_name = fields[2]
        start, end = SLOT_TIMES[slot_name]
        start_date = datetime.fromisoformat(f"{YEAR}-{MONTH}-{day_nb} {start}")
        end_date = datetime.fromisoformat(f"{YEAR}-{MONTH}-{day_nb} {end}")

        slot = TimeSlot(day_name, start_date, end_date)
        res[col] = slot

    return res
