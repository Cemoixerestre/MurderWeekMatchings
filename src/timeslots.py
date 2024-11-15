from __future__ import annotations

from datetime import datetime, timedelta
from typing import List, Dict
import re

SLOT_TIMES = {
    'matin': ('08:00', '13:00'),
    'après-midi': ('13:00', '18:00'),
    'soir': ('18:00', '23:59')
}
NIGHT_SLOT_TIMES = ('00:00', '03:59')

# TODO: keep?
WEEK_DAYS = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche']

YEAR = "2024"
MONTH = "08" # TODO: delete

def set_year(year):
    global YEAR
    YEAR = year

class TimeSlot:
    def __init__(self, start: datetime, end: datetime, name: Option[str]=None):
        """Create a timeslot.

        Arguments:
        - start: a datetime. The hour must be between 4AM and 8AM.
        - end: a datetime. The hour must be between 4AM and 8AM. It must be
          greater than start. It can be the same day as start, or the day after
          start.
        - Optional: a representation "name". It is used for columns extracted
          from the inscription file. The goal is to display
          "Lundi 24/08 matin" instead of "24/08 08:00-13:00". 
        """
        self.start = start
        self.end = end
        self.name: Option[str] = name
        assert self.start < self.end, \
            "Error: time slot should starts before it ends. " \
            f"day. Erroneous dates: start = {start} and end = {end}."
        assert self.end.day - self.start.day <= 1, \
            "Error: a game cannot be more than one day long. " \
            f"day. Erroneous dates: start = {start} and end = {end}."
        assert not (4 <= self.start.hour < 8), \
            f"Error: a game starts between 8:00 AM and 4:00 AM. " \
            f"Erroneous date: start = {start}"
        assert not (4 <= self.end.hour < 8), \
            f"Error: a game ends between 8:00 AM and 4:00 AM. " \
            f"Erroneous date: start = {start}"

        self.day_name: str = WEEK_DAYS[start.weekday()]

    def overlaps(self, other: TimeSlot) -> bool:
        if (self.start <= other.start) and (other.start < self.end):
            return True
        elif (other.start <= self.start) and (self.start < other.end):
            return True
        else:
            return False

    def __repr__(self):
        if self.name is not None:
            return self.name
        start_hour = f"{self.start.hour:02}:{self.start.minute:02}"
        end_hour = f"{self.end.hour:02}:{self.end.minute:02}"
        return f"{self.start.day:02}/{MONTH} {start_hour}-{end_hour}"

    def __eq__(self, other):
        return (self.start, self.end) == (other.start, other.end)

    def __hash__(self):
        return hash((self.start, self.end))

    def disp_day(self) -> str:
        return f"{self.day_name} {self.start.day}"

    def disp_hour(self) -> str:
        return f"{self.start.hour:02}:{self.start.minute:02}-" \
               f"{self.end.hour:02}:{self.end.minute:02}"

def generate_timeslot_from_column_name(column_name: str) -> Option[TimeSlot]:
    """
    If column_name corresponds to a slot, returns the corresponding TimeSlot
    object. Otherwise, returns None.

    Examples:
    - "Dimanche 25/08 après-midi" is mapped to the slot
      (YYYY-08-25 13:00, YYYY-08-25 18:00)
    - "Nuit de dimanche 25/08 à lundi 26/08" is mapped to the slot
      (YYYY-08-26 00:00, YYYY-08-26 03:59)
    - "Vœu n°3" is not a time slot. Returns None.
    """
    day_pattern = "(?P<day_name>\\S*) (?P<day>.{2})/(?P<month>.{2}) " \
                  "(?P<slot>\\S*)"
    night_pattern = "Nuit de \\S* .{2}/.{2} à " \
                    "(?P<day_name>\\S*) (?P<day>.{2})/(?P<month>.{2})"
    day_match = re.fullmatch(day_pattern, column_name)
    night_match = re.fullmatch(night_pattern, column_name)
    if day_match is not None:
        day_name = day_match.group("day_name")
        month = day_match.group("month")
        day_nb = day_match.group("day")
        slot_name = day_match.group("slot")
        start, end = SLOT_TIMES[slot_name]
    elif night_match is not None:
        day_name = night_match.group("day_name")
        month = night_match.group("month")
        day_nb = night_match.group("day")
        start, end = NIGHT_SLOT_TIMES
    else:
        return None

    start_date = datetime.fromisoformat(f"{YEAR}-{month}-{day_nb} {start}")
    end_date = datetime.fromisoformat(f"{YEAR}-{month}-{day_nb} {end}")
    slot = TimeSlot(start_date, end_date, column_name)
    assert slot.day_name.lower() == day_name.lower()
    return slot

def generate_timeslots_from_column_names(column_names: List[str]) -> Dict[str, TimeSlot]:
    """
    Take the list of all columns. To each of them that correspond to slot name in
    natural language, map them to a TimeSlot object.

    Examples:
    - "Dimanche 25/08 après-midi" is mapped to the slot
      (YYYY-08-25 13:00, YYYY-08-25 18:00)
    - "Nuit de dimanche 25/08 à lundi 26/08" is mapped to the slot
      (YYYY-08-26 00:00, YYYY-08-26 03:59)
    - "Vœu n°3" is not a time slot. It's therefore not a key in the result.
    """
    res = dict()
    for col in column_names:
        slot = generate_timeslot_from_column_name(col)
        if slot is not None:
            res[col] = slot

    return res
