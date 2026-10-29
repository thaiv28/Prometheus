"""Render Other games pages from local feeds, without a database or network."""

import datetime
import time

from prometheus.site import games


def main():
    started = time.perf_counter()
    feeds = games.load_feeds()
    games.install_nav(feeds)
    pages = games.render_game_pages(feeds, datetime.datetime.now(datetime.UTC))
    summary = (
        f"Games: {', '.join(f['game'] for f in feeds) or 'none'}; "
        f"{pages} pages written; {time.perf_counter() - started:.3f} seconds"
    )
    print(summary)
    return summary


if __name__ == "__main__":
    main()
