from typing import List
from pathlib import Path
from datetime import datetime

from activityMatch import Matcher
from loader import load_activities_and_players
from timeslots import set_year, TimeSlot

def test_night_then_morning():
    set_year("2024")
    activities, players = load_activities_and_players(
            Path('test-input/night-then-morning-activities.csv'),
            Path('test-input/night-then-morning-inscriptions.csv'))

    matcher = Matcher(players, activities, 0.6)

    res = matcher.solve(verbose=True)
    res.print_players_status()
    res.print_activities_status()

    # Frodon can play a night and the next morning. Therefore, he can play both
    # Arcane and Braquage.
    frodon = matcher.find_player_by_name("Frodon")
    assert len(res.activities[frodon]) == 2
    # Unlike Frodon, Sam can only play one of these two activities.
    sam = matcher.find_player_by_name("Sam")
    assert len(res.activities[sam]) == 1
    # Pipin cannot play a night and the next morning, but because there is a
    # gap of more than 12h between Arcane and Hôtel AZ, he can play both.
    pipin = matcher.find_player_by_name("Pipin")
    assert len(res.activities[pipin]) == 2


def test_get_availability():
    set_year("2024")
    activities, players = load_activities_and_players(
            Path('test-input/empty-activities.csv'),
            Path('test-input/get-availability-inscriptions.csv'))

    matcher = Matcher(players, activities, 0.6)
    slot = TimeSlot(
        None,
        datetime.fromisoformat("2024-08-24 19:00"),
        datetime.fromisoformat("2024-08-25 02:00")
    )

    mion = matcher.find_player_by_name("Mion Sonozaki")
    keiichi = matcher.find_player_by_name("Keiichi Maebara")
    rena = matcher.find_player_by_name("Rena Ryuugu")

    # Keiichi is not available on the night, he cannot play on this slot.
    assert set(matcher.get_available_players(slot, None)) == {mion, rena}
    # Rena is available on this slot but she doesn't want to play Braquage.
    assert matcher.get_available_players(slot, "Braquage") == [mion]
