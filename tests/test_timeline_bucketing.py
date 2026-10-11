"""The bucket lookup must find exactly the same bucket a linear scan would.

`_bucket_index` finds which half-open bucket a moment belongs to. It was a linear
scan, which made a daily timeline over a year cost 45 ms against 7 ms for the same
rows bucketed by month — a day timeline has hundreds of edges and the scan ran once
per row. It is now a binary search over the same sorted edges.

That is only safe if it returns identical answers, so this module checks the fast
implementation against the obvious linear one across every edge, every boundary,
and a window spanning a daylight-saving transition, where a local day is not
twenty-four hours long and a fixed offset would quietly misbucket.
"""

from datetime import datetime, timedelta, timezone

import pytest

from aggregation.timeline import _bucket_edges, _bucket_index

UTC = timezone.utc


def linear_bucket_index(moment: datetime, edges: list[datetime]) -> int | None:
    """The original implementation, kept here as the reference to check against."""
    for index in range(len(edges) - 1):
        if edges[index] <= moment < edges[index + 1]:
            return index
    if moment == edges[-1] and len(edges) > 1:
        return len(edges) - 2
    return None


def edges_for_days(start: datetime, count: int) -> list[datetime]:
    """Half-open bucket edges `count` days after `start`, in UTC."""
    return [start + timedelta(days=index) for index in range(count + 1)]


def test_every_moment_maps_to_the_same_bucket_as_a_linear_scan() -> None:
    edges = edges_for_days(datetime(2026, 3, 1, tzinfo=UTC), 40)

    for offset in range(-2, 41 * 24 * 4, 7):  # hourly, well past both ends
        moment = edges[0] + timedelta(hours=offset)
        assert _bucket_index(moment, edges) == linear_bucket_index(moment, edges), moment


def test_the_exact_edges_are_handled_the_same_way() -> None:
    edges = edges_for_days(datetime(2026, 3, 1, tzinfo=UTC), 10)

    for edge in edges:
        assert _bucket_index(edge, edges) == linear_bucket_index(edge, edges)


def test_a_moment_past_the_last_edge_belongs_to_no_bucket() -> None:
    edges = edges_for_days(datetime(2026, 3, 1, tzinfo=UTC), 5)
    beyond = edges[-1] + timedelta(seconds=1)

    assert _bucket_index(beyond, edges) is None
    assert linear_bucket_index(beyond, edges) is None


def test_a_moment_before_the_first_edge_belongs_to_no_bucket() -> None:
    edges = edges_for_days(datetime(2026, 3, 1, tzinfo=UTC), 5)

    assert _bucket_index(edges[0] - timedelta(seconds=1), edges) is None


def test_the_closing_edge_lands_in_the_final_bucket() -> None:
    edges = edges_for_days(datetime(2026, 3, 1, tzinfo=UTC), 5)

    assert _bucket_index(edges[-1], edges) == len(edges) - 2
    assert _bucket_index(edges[-1], edges) == linear_bucket_index(edges[-1], edges)


@pytest.mark.parametrize(
    "zone",
    ["UTC", "Asia/Kathmandu", "America/New_York", "Australia/Lord_Howe"],
)
def test_daylight_saving_transitions_do_not_shift_a_row_between_buckets(zone: str) -> None:
    # A local day is 23, 24, or 25 hours long depending on the transition, so the
    # edges are not evenly spaced in UTC. The lookup must not assume they are.
    edges = _bucket_edges(
        datetime(2026, 3, 6, tzinfo=UTC),
        datetime(2026, 3, 12, tzinfo=UTC),
        "day",
        zone,
    )

    for offset in range(0, 6 * 24 * 4, 3):
        moment = edges[0] + timedelta(hours=offset)
        assert _bucket_index(moment, edges) == linear_bucket_index(moment, edges), (zone, moment)

    # And every moment inside a bucket really is bracketed by that bucket's edges.
    for index in range(len(edges) - 1):
        middle = edges[index] + (edges[index + 1] - edges[index]) / 2
        assert _bucket_index(middle, edges) == index


def test_a_day_timeline_with_many_edges_still_agrees() -> None:
    # The shape that motivated the change: hundreds of edges, one lookup per row.
    edges = _bucket_edges(
        datetime(2026, 1, 1, tzinfo=UTC),
        datetime(2026, 12, 31, tzinfo=UTC),
        "day",
        "UTC",
    )

    assert len(edges) > 300
    for index in range(0, len(edges) - 1, 17):
        moment = edges[index] + timedelta(hours=13)
        assert _bucket_index(moment, edges) == linear_bucket_index(moment, edges)