"""Non-League game identities shared by feeds and the isolated executor."""

from dataclasses import dataclass


@dataclass(frozen=True)
class OtherGame:
    slug: str
    series_ticker: str
    rules_word: str
    groups: frozenset[str]
    trade_groups: frozenset[str]
    repo: str
    label: str
    emoji: str
    color: str
    kalshi_slug: str


GAMES = {
    "cs2": OtherGame(
        "cs2",
        "KXCS2GAME",
        "CS2",
        frozenset({"cs2-series"}),
        frozenset({"cs2-series"}),
        "cs2-model",
        "CS2",
        "🟥",
        "#dc2626",
        "counter-strike-2-game",
    ),
    "valorant": OtherGame(
        "valorant",
        "KXVALORANTGAME",
        "Valorant",
        frozenset({"valorant-domestic", "valorant-international"}),
        frozenset({"valorant-domestic"}),
        "valorant-model",
        "Valorant",
        "🟩",
        "#16a34a",
        "valorant-game-winner",
    ),
    "dota2": OtherGame(
        "dota2",
        "KXDOTA2GAME",
        "Dota 2",
        frozenset({"dota2-series"}),
        frozenset({"dota2-series"}),
        "dota2-model",
        "Dota 2",
        "🟧",
        "#ea580c",
        "dota-2-game",
    ),
}


def account_key(slug: str) -> str:
    return f"ACCOUNT#{slug}"


ACCOUNT_KEYS = ("ACCOUNT", *(account_key(slug) for slug in GAMES))
