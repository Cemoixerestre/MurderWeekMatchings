from typing import List
from pathlib import Path
from datetime import datetime

from activityMatch import Matcher, get_available_players, print_dispos
from loader import load_activities_and_players
from timeslots import set_year, TimeSlot, generate_timeslot_from_column_name

def test_load():
    """Just to try the standard format files."""
    set_year("2024")
    activities, players = load_activities_and_players(
            Path('format_standard_activites.csv'),
            Path('format_standard_inscriptions.csv'))

    print(activities)

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
    _, players = load_activities_and_players(
            Path('test-input/empty-activities.csv'),
            Path('test-input/get-availability-inscriptions.csv'))

    slot = generate_timeslot_from_column_name(
        "Nuit de samedi 24/08 à dimanche 25/08"
    )

    mion = [p for p in players if p.name == "Mion Sonozaki"][0]
    keiichi = [p for p in players if p.name == "Keiichi Maebara"][0]
    rena = [p for p in players if p.name == "Rena Ryuugu"][0]

    # Keiichi is not available on the night, he cannot play on this slot.
    assert set(get_available_players(players, slot, None)) == {mion, rena}
    # Rena is available on this slot but she doesn't want to play Braquage.
    assert get_available_players(players, slot, "Braquage") == [mion]

    # Just check that `print_dispos` runs without errors. We don't check
    # what's printed.
    print_dispos(players, "Arcane", True)

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

def test_orga_player_consecutive_days():
    set_year("2024")
    activities, players = load_activities_and_players(
            Path('test-input/play-orga-consecutive-days-activities.csv'),
            Path('test-input/play-orga-consecutive-days-inscriptions.csv'))

    matcher = Matcher(players, activities, 0.6)

    res = matcher.solve(verbose=True)
    res.print_players_status()
    res.print_activities_status()

    luz = matcher.find_player_by_name("Luz Noceda")
    assert len(res.activities[luz]) == 3

    # Amity cannot play on 24-08 and 26-08 because of her organization
    amity = matcher.find_player_by_name("Amity Blight")
    assert len(res.activities[amity]) == 1

def test_orga_player_same_day():
    set_year("2024")
    activities, players = load_activities_and_players(
            Path('test-input/play-orga-same-day-activities.csv'),
            Path('test-input/play-orga-same-day-inscriptions.csv'))

    matcher = Matcher(players, activities, 0.6)

    res = matcher.solve(verbose=True)
    res.print_players_status()
    res.print_activities_status()

    sayaka = matcher.find_player_by_name("Sayaka Miki")
    assert len(res.activities[sayaka]) == 1

    # Kyoko does not play and organize the same day. Therefore, she cannot play
    # "A magical party".
    kyoko = matcher.find_player_by_name("Kyoko Sakura")
    assert len(res.activities[kyoko]) == 0
