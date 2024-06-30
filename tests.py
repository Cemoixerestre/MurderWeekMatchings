from typing import List
from pathlib import Path
from datetime import datetime

from activityMatch import Matcher
from loader import load_activities_and_players
from timeslots import set_year, TimeSlot

def test_load():
    """Just to try the standard format files."""
    set_year("2024")
    activities, players = load_activities_and_players(
            Path('data/format_standard_activites.csv'),
            Path('data/format_standard_inscriptions.csv'))

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

def test_blacklist():
    set_year("2024")
    activities, players = load_activities_and_players(
            Path('test-input/blacklist-activities.csv'),
            Path('test-input/blacklist-inscriptions.csv'))

    matcher = Matcher(players, activities, 0.6)

    res = matcher.solve(verbose=True)
    res.print_players_status()
    res.print_activities_status()

    pearl = matcher.find_player_by_name("Pearl")
    greg = matcher.find_player_by_name("Greg Universe")
    amethyst = matcher.find_player_by_name("Amethyst")
    garnet = matcher.find_player_by_name("Garnet")
    peridot = matcher.find_player_by_name("Peridot")

    # Pearl plays Braquage because it's her first choice.
    # Greg cannot play because it's his second choice and Pearl blacklisted him.
    # Amethyst can play because she only refused to be organized by Pearl.
    braquage = matcher.find_activity_by_name("Braquage")[0]
    assert set(res.players[braquage]) == {pearl, amethyst}

    # Amethyst doesn't want to play "In Antarctica" because Pearl is organizing
    in_antarctica = matcher.find_activity_by_name("In Antarctica")[0]
    assert amethyst not in res.players[in_antarctica]

    # Garnet doesn't want to organize for Peridot
    arcane = matcher.find_activity_by_name("Arcane")[0]
    assert peridot not in res.players[arcane]
