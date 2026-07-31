import pytest

from app.services.agent_service import PlayerNotFoundError, get_player_stats


def test_get_player_stats_returns_matching_player():
    player = get_player_stats("Darnell Voss")

    assert player["player_id"] == "P001"
    assert player["position"] == "QB"


def test_get_player_stats_is_case_insensitive():
    player = get_player_stats("darnell voss")

    assert player["player_id"] == "P001"


def test_get_player_stats_filters_by_season():
    with pytest.raises(PlayerNotFoundError):
        get_player_stats("Darnell Voss", season=1999)


def test_get_player_stats_unknown_player_raises():
    with pytest.raises(PlayerNotFoundError):
        get_player_stats("Nobody Fakename")
