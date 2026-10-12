"""The dashboard is served from the backend and stays wired to the API.

Approach A retired the React app: `web/index.html` + `web/app.js` are now served
by FastAPI at the site root. These tests prove the page is served, branded
Tokenly (not the mockup's "TokenScope"), and — critically — that mounting static
files at "/" did not shadow the `/api` routes.
"""

import pytest


def test_the_dashboard_is_served_at_the_root(client) -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert "Tokenly" in response.text
    assert "/app.js" in response.text
    # The mockup's placeholder brand must be gone.
    assert "TokenScope" not in response.text


def test_the_api_wiring_script_is_served(client) -> None:
    response = client.get("/app.js")

    assert response.status_code == 200
    assert "/api/usage/summary" in response.text
    assert "/api/collector/status" in response.text


def test_the_api_routes_still_answer_under_the_static_mount(client) -> None:
    # The catch-all static mount must not shadow the API.
    health = client.get("/api/health")
    summary = client.get("/api/usage/summary")

    assert health.status_code == 200
    assert summary.status_code == 200


@pytest.mark.parametrize(
    "asset",
    [
        "app.js",
        "usage-filters.js",
        "usage-chart.js",
        "platform-cards.js",
        "usage-breakdown.js",
        "usage-cards.js",
        "dropdowns.js",
        "model-ranking.js",
    ],
)
def test_dashboard_modules_are_served_without_stale_caching(client, asset) -> None:
    response = client.get(f"/{asset}")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert "javascript" in response.headers["content-type"]


def test_unknown_api_routes_are_not_hidden_by_dashboard_assets(client) -> None:
    assert client.get("/api/unknown").status_code == 404

def test_platform_cards_start_with_loading_states_instead_of_demo_graphs(client) -> None:
    response = client.get("/")

    cards = response.text.split('id="platform-cards-container"', 1)[1].split(
        'id="velocity-analytics-card"', 1
    )[0]

    assert "Loading daily usage" in cards
    assert "sparkline-anim" not in cards
    assert "Session #4821" not in cards


def test_the_breakdown_section_ships_a_card_grid_not_platform_bars(client) -> None:
    """The section is one card per platform with its own model dropdown.

    The card grid replaced a set of platform-wide usage bars. Its markup is keyed on
    `#usage-card-grid`, so a stale bar container left behind would render an empty
    section while every API call still succeeded.
    """
    response = client.get("/")

    assert 'id="usage-card-grid"' in response.text
    assert 'id="usage-platform-filter"' in response.text
    assert 'id="usage-breakdown-bars"' not in response.text


def test_the_card_and_bar_rendering_lives_in_tested_modules(client) -> None:
    """Both renderers are separate modules with their own unit tests, not inline in app.js.

    The card arithmetic and the per-day tooltip content are the two places a silent
    regression would show wrong numbers rather than a broken layout.
    """
    page = client.get("/")
    script = client.get("/app.js")

    assert "/usage-cards.js" in page.text
    assert "/usage-breakdown.js" in page.text
    assert "TokenlyUsageCards.createRenderer" in script.text
    assert "TokenlyUsageBreakdown.createDayBarRenderer" in script.text
    assert "TokenlyUsageBreakdown.aggregateByPlatform" in script.text


def test_each_card_drills_into_its_own_model_without_disturbing_the_others(client) -> None:
    """Model selection is tracked per platform, not globally.

    A single shared selection would collapse the section to one card the moment a model
    was chosen, which is the opposite of comparing platforms side by side.
    """
    script = client.get("/app.js")

    assert "modelByPlatform" in script.text
    assert "loadPlatformDaySeries(platformId" in script.text


def test_the_section_platform_filter_defers_to_the_page_wide_one_only_when_unset(client) -> None:
    """The header filter and the section filter must not contradict each other.

    The header's "Cline" filter has to narrow the cards too, or OpenCode cards sit
    directly below a view labelled Cline and read as a broken filter. Choosing inside
    the section is the more specific act, so it wins there.
    """
    script = client.get("/app.js").text

    assert "state.sectionPlatform || state.platform || ''" in script
