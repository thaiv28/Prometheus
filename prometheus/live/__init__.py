"""Live maps: the Riot feed, Kalshi quotes and FORGE, published for the live pages.

`service.py` runs always on: it discovers games in progress, collects each one's
feed, and writes `live/index.json` and one file per match for the site.
"""
