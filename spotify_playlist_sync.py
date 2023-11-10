import spotipy
from spotipy.oauth2 import SpotifyOAuth, CacheFileHandler
import logging
from pprint import pprint
import yaml

logging.basicConfig(level=logging.WARNING)
with open("config.yaml") as f:
    config = yaml.full_load(f)

for account in config.get("accounts"):
    handler = CacheFileHandler(username=account["Username"])
    sp = spotipy.Spotify(
        auth_manager=SpotifyOAuth(
            client_id=account.get("ClientId"),
            client_secret=account["Secret"],
            redirect_uri=account.get("RedirectUrl"),
            cache_handler=handler,
            scope="playlist-read-collaborative playlist-read-private user-library-read"))

    user = sp.current_user()
    playlists = sp.current_user_playlists()
    transfer_playlist = None

    for playlist in playlists['items']:
        if config["SpotifyTransferPlaylist"] == playlist.get("name"):
            transfer_playlist = sp.playlist(playlist_id=playlist["id"])
            break

    if transfer_playlist == None:
        logging.critical("No transfer playlist found (%s)" % config["SPOTIFY_TRANSFER_PLAYLIST"])

    tracks = sp.current_user_saved_tracks()

    pprint(tracks)