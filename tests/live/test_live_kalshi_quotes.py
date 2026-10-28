import unittest

from prometheus.live.kalshi import contract, quote, scheduled_day

RULE = (
    "If {side} wins game {map} in the Worlds 2026: Karmine Corp vs. Cloud9 League "
    "of Legends match originally scheduled for {day} at 2:00 PM EDT, then the "
    "market resolves to Yes."
)
TEAMS = [
    {"name": "Karmine Corp", "riot_name": "Karmine Corp", "code": "KC"},
    {"name": "Cloud9", "riot_name": "Cloud9 Kia", "code": "C9"},
]


def market(side, number=4, day="Oct 15, 2026", event="E4"):
    return {
        "ticker": f"{event}-{side}",
        "event_ticker": event,
        "rules_primary": RULE.format(side=side, map=number, day=day),
    }


class ContractTest(unittest.TestCase):
    start = "2026-10-15T18:00:00Z"
    markets = (
        market("Karmine Corp"),
        market("Cloud9"),
        market("Cloud9", 3, event="E3"),
    )

    def test_picks_yes_on_first_team_for_the_map(self):
        self.assertEqual(
            contract(self.markets, {"teams": TEAMS}, 4, self.start), "E4-Karmine Corp"
        )
        self.assertEqual(
            contract(self.markets, {"teams": TEAMS[::-1]}, 4, self.start), "E4-Cloud9"
        )

    def test_wrong_map_or_day_gives_none(self):
        self.assertIsNone(contract(self.markets, {"teams": TEAMS}, 5, self.start))
        self.assertIsNone(
            contract(self.markets, {"teams": TEAMS}, 4, "2026-10-17T18:00:00Z")
        )

    def test_a_lone_event_a_day_off_matches_but_the_exact_day_wins(self):
        # Kalshi listed T1 vs MKOI (Oct 28, 4 PM EDT) as Oct 29.
        self.assertEqual(
            contract(self.markets, {"teams": TEAMS}, 4, "2026-10-16T18:00:00Z"),
            "E4-Karmine Corp",
        )
        exact = [market("Karmine Corp", day="Oct 16, 2026", event="E4x")]
        self.assertEqual(
            contract(
                [*self.markets, *exact], {"teams": TEAMS}, 4, "2026-10-16T18:00:00Z"
            ),
            "E4x-Karmine Corp",
        )

    def test_two_events_for_one_map_are_ambiguous(self):
        markets = [*self.markets, market("Karmine Corp", event="E4b")]
        self.assertIsNone(contract(markets, {"teams": TEAMS}, 4, self.start))

    def test_kalshi_names_go_through_market_aliases(self):
        # Kalshi calls FURIA "FURIA Esports"; Riot, Prometheus and the code say FURIA.
        rule = (
            "If {side} wins game 4 in the Worlds 2026: Cloud9 vs. FURIA Esports "
            "League of Legends match originally scheduled for Oct 16, 2026 at "
            "4:50 PM EDT, then the market resolves to Yes."
        )
        markets = [
            {
                "ticker": f"E-{s}",
                "event_ticker": "E",
                "rules_primary": rule.format(side=s),
            }
            for s in ("FURIA Esports", "Cloud9")
        ]
        teams = [
            {"name": "FURIA", "riot_name": "FURIA", "code": "FUR"},
            {"name": "Cloud9", "riot_name": "Cloud9 Kia", "code": "C9"},
        ]
        start = "2026-10-16T23:00:00Z"
        self.assertEqual(
            contract(markets, {"teams": teams}, 4, start), "E-FURIA Esports"
        )
        self.assertEqual(
            contract(markets, {"teams": teams[::-1]}, 4, start), "E-Cloud9"
        )

    def test_eastern_date(self):
        self.assertEqual(scheduled_day("2026-10-16T02:00:00Z"), "Oct 15, 2026")


class QuoteTest(unittest.TestCase):
    def test_top_of_book_for_yes(self):
        book = {
            "orderbook_fp": {
                "yes_dollars": [["0.50", "10"], ["0.54", "3"]],
                "no_dollars": [["0.44", "5"]],
            }
        }
        self.assertEqual(quote(book, "t"), {"at": "t", "bid": 0.54, "ask": 0.56})

    def test_one_sided_book_gives_none(self):
        self.assertIsNone(
            quote(
                {"orderbook_fp": {"yes_dollars": [["0.5", "1"]], "no_dollars": []}}, "t"
            )
        )


if __name__ == "__main__":
    unittest.main()
