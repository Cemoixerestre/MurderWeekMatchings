from __future__ import annotations

from datetime import datetime
from typing import List, Dict
import re

SLOT_TIMES = {
    'matin': ('08:00', '13:00'),
    'après-midi': ('13:00', '18:00'),
    'soir': ('18:00', '23:59')
}
NIGHT_SLOT_TIMES = ('00:00', '04:00')

# TODO: keep?
WEEK_DAYS = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche']

YEAR = "2024"
MONTH = "08" # TODO: delete

def set_year(year):
    global YEAR
    YEAR = year

class TimeSlot:
    def __init__(self, day_name: Option[str], start: datetime, end: datetime,
                 is_game=True):
        """Create a timeslot.

        For a game timeslot, we add an extra-check: we verify that the game
        starts before midnight and ends before 4:00.
        """
        self.start = start
        self.end = end
        assert self.start < self.end, \
            "Error: time slot should starts before it ends. " \
            f"day. Erroneous dates: start = {start} and end = {end}."
        assert self.end.day - self.start.day <= 1, \
            "Error: a game cannot be more than one day long. " \
            f"day. Erroneous dates: start = {start} and end = {end}."
        # Should only be tested for games, not for timeslots
        assert not (is_game and self.start.hour < 8), \
            f"Error: a game starts between 8:00 and 23:59. " \
            f"Erroneous date: start = {start}"
        assert not (is_game and 4 <= self.end.hour < 8), \
            f"Error: a game starts between 8:00 and 4:00. " \
            f"Erroneous date: start = {start}"

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

    def __eq__(self, other):
        return (self.start, self.end) == (other.start, other.end)

    def disp_day(self) -> str:
        return f"{self.day_name} {self.start.day}"

    def disp_hour(self) -> str:
        return f"{self.start.hour:02}:{self.start.minute:02}-" \
               f"{self.end.hour:02}:{self.end.minute:02}"

def generate_timeslots_from_column_names(column_names: List[str]) -> Dict[str, TimeSlot]:
    """
    Take the list of all columns. To each of them that correspond to slot name in
    natural language, map them to a TimeSlot object.

    Examples:
    - "Dimanche 25/08 après-midi" is mapped to the slot
      (YYYY-08-25 13:00, YYYY-08-25 18:00)
    - "Nuit de dimanche 25/08 à lundi 26/08" is mapped to the slot
      (YYYY-08-26 00:00, YYYY-08-26 04:00)
    """
    res = dict()
    day_pattern = "\S* (?P<day>.{2})/(?P<month>.{2}) (?P<slot>\S*)"
    night_pattern = "Nuit de \S* .{2}/.{2} à \S* (?P<day>.{2})/(?P<month>.{2})"
    for col in column_names:
        day_match = re.fullmatch(day_pattern, col)
        night_match = re.fullmatch(night_pattern, col)
        if day_match is not None:
            month = day_match.group("month")
            day_nb = day_match.group("day")
            slot_name = day_match.group("slot")
            start, end = SLOT_TIMES[slot_name]
        elif night_match is not None:
            month = night_match.group("month")
            day_nb = night_match.group("day")
            start, end = NIGHT_SLOT_TIMES
        else:
            continue
        # TODO: use the day name in the column name as a sanity check?
        day_name = None
            
        start_date = datetime.fromisoformat(f"{YEAR}-{month}-{day_nb} {start}")
        end_date = datetime.fromisoformat(f"{YEAR}-{month}-{day_nb} {end}")

        slot = TimeSlot(day_name, start_date, end_date, is_game=False)
        res[col] = slot

    return res

# TODO: move
def test_generate_timeslots_from_column_names():
    set_year(2024)
    column_names = [
        "Dimanche 25/08 après-midi",
        "Nuit de lundi 26/08 à mardi 27/08",
        "Vœu n°3"
    ]
    expected = {
        "Dimanche 25/08 après-midi": TimeSlot(
            None,
            datetime.fromisoformat("2024-08-25 13:00"),
            datetime.fromisoformat("2024-08-25 18:00"),
            is_game=False
        ),
        "Nuit de lundi 26/08 à mardi 27/08": TimeSlot(
            None,
            datetime.fromisoformat("2024-08-27 00:00"),
            datetime.fromisoformat("2024-08-27 04:00"),
            is_game=False
        )
    }
    time_slots = generate_timeslots_from_column_names(column_names)
    assert time_slots == expected
