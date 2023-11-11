# spotify_playlist_sync
Syncs multiple Spotify (family) accounts and their saved tracks

The script is using a transfer playlist. This ensures that every account can control their liked songs individually.
But if someone wants to share a songs with the group it will be automatically liked from the others.

## Setup

1. Create a transfer playlist in spotify and share it across the accounts
2. Create [developer accounts](https://developer.spotify.com/) for all the accounts where the marked songs should be synced
3. Copy ``config.yaml.sample`` to ``config.yaml``
4. Adapt username, access key and secret (first account shoule be the user of the tranfer playlist)
5. Create venv `python3 -mvenv .venv && source .venv/bin/activate`
6. `pip install -r requirements.txt`
7. Run `python3 spotify_playlist_sync.py`


## Cache files
The refresh tokens are stored locally for each username. Please ensure that the usernames are unique.
