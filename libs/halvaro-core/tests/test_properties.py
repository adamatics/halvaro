"""Property style tests of the modules calendar, facts and keys of halvaro-core (standard 3.2.3, lane P2, issue #469).

Each test states a rule that must hold for many inputs and draws them from a seeded generator (no extra package): a round trip, an idempotence, an ordering, a relation between two functions. The
rule is written from the documented behaviour of the function, not from its body.
"""
import datetime as dt
import random

import pytest

import halvaro.core as core
from halvaro.core import snapshot

REGIONS = ("DK", "DE-HH", "DE-NI")
STARTS = [dt.date(2026, 1, 1) + dt.timedelta(days=d) for d in range(0, 700, 7)]


def rng(seed: int) -> random.Random:
    return random.Random(20261119 + seed)


# ---------------------------------------------------------------- calendar
@pytest.mark.parametrize("region", REGIONS)
def test_counting_working_days_is_the_round_trip_of_adding_them(region):
    """add_working_days(start, n) is the n-th working day from start, so counting the working days from start to it gives n back, and it is itself a working day."""
    r = rng(1)
    for _ in range(150):
        start, n = r.choice(STARTS) + dt.timedelta(days=r.randint(0, 6)), r.randint(1, 40)
        end = core.add_working_days(start, n, region)
        assert end >= start and core.is_working_day(end, region)
        assert core.working_days(start, end, region) == n


@pytest.mark.parametrize("region", REGIONS)
def test_working_days_are_the_sum_of_the_working_days_of_adjacent_ranges(region):
    """Both ends are included, so [a, c] is [a, b] followed by [b + 1 day, c]."""
    r = rng(2)
    for _ in range(150):
        a = r.choice(STARTS) + dt.timedelta(days=r.randint(0, 6))
        b, c = a + dt.timedelta(days=r.randint(0, 60)), a + dt.timedelta(days=r.randint(61, 200))
        assert core.working_days(a, c, region) == core.working_days(a, b, region) + core.working_days(b + dt.timedelta(days=1), c, region)


@pytest.mark.parametrize("region", REGIONS)
def test_a_weekend_day_and_a_public_holiday_are_never_working_days(region):
    for year in (2026, 2027):
        holidays = core.public_holidays(year, region)
        assert holidays == core.public_holidays(year, region)                      # idempotent: the same call gives the same set
        assert holidays and all(d.year == year for d in holidays)
        assert not any(core.is_working_day(d, region) for d in holidays)
    r = rng(3)
    for _ in range(200):
        d = dt.date(2026, 1, 1) + dt.timedelta(days=r.randint(0, 729))
        if d.weekday() >= 5:
            assert not core.is_working_day(d, region)


# ---------------------------------------------------------------- keys
def test_a_key_text_of_every_prefix_round_trips_through_parse_key():
    """Writing prefix, a dash and the number with the width of the prefix gives a valid key that parse_key reads back to the same prefix, number and width."""
    spine = snapshot.load()["keys"]
    r = rng(4)
    for prefix, info in sorted(spine.items()):
        width = info["width"]
        for number in {1, 10 ** width - 1, *(r.randint(1, 10 ** width - 1) for _ in range(20))}:
            text = f"{prefix}-{number:0{width}d}"
            parts = core.parse_key(text)
            assert (parts.prefix, parts.number, parts.width) == (prefix, number, width)
            assert core.is_valid_key(text) and core.is_valid_key(text, prefix)
            assert f"{parts.prefix}-{parts.number:0{parts.width}d}" == text


def test_a_key_with_the_wrong_width_or_another_prefix_is_not_valid():
    spine = snapshot.load()["keys"]
    for prefix, info in sorted(spine.items()):
        width = info["width"]
        assert not core.is_valid_key(f"{prefix}-{1:0{width + 1}d}")                  # one digit too many
        if width > 1:
            assert not core.is_valid_key(f"{prefix}-{1:0{width - 1}d}")              # one digit too few
        other = next(p for p in sorted(spine) if p != prefix)
        assert not core.is_valid_key(f"{prefix}-{1:0{width}d}", other)


def test_every_prefix_of_the_spine_with_a_master_names_itself():
    snap = snapshot.load()
    for prefix in sorted(set(snap["keys"]) & set(snap["masters"])):
        assert core.master_of(prefix).prefix == prefix


# ---------------------------------------------------------------- facts
def test_every_fact_is_found_by_its_id_and_the_lookup_is_idempotent():
    for fact_id in sorted(snapshot.load()["facts"]):
        first = core.fact(fact_id)
        assert first.id == fact_id and first == core.fact(fact_id)


def test_the_value_of_a_fact_read_by_file_and_path_equals_the_value_read_by_id():
    """cfg(file, path) and fact(prefix.path) are two ways to the same fact: the round trip file to prefix and back."""
    snap = snapshot.load()
    by_file = {prefix: rel for prefix, rel in snap["fact_files"].items()}
    checked = 0
    for fact_id in sorted(snap["facts"]):
        for prefix, rel in sorted(by_file.items(), key=lambda kv: -len(kv[0])):
            if fact_id.startswith(prefix + "."):
                assert core.cfg(rel, fact_id[len(prefix) + 1:]) == core.fact(fact_id)
                checked += 1
                break
    assert checked > 100


def test_the_status_of_a_set_of_facts_does_not_depend_on_their_order():
    statuses = sorted({f["status"] for f in snapshot.load()["facts"].values()})
    r = rng(5)
    for _ in range(200):
        picked = [r.choice(statuses) for _ in range(r.randint(1, 8))]
        shuffled = picked[:]
        r.shuffle(shuffled)
        assert core.combine_status(picked) == core.combine_status(shuffled) and core.combine_status(picked + picked) == core.combine_status(picked)
