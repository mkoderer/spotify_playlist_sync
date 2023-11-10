import spotipy
from spotipy.oauth2 import SpotifyOAuth, CacheFileHandler
import logging
from pprint import pprint
import yaml
from mergedeep import merge, Strategy

def get_all(sp, function, *arg):
    log.info("Call %s" % function)
    func = getattr(sp, function)
    result = func(*arg)
    while result.get("next"):
        log.debug("Next page for call %s" % function)
        res = sp.next(result)
        merge(result, res, strategy=Strategy.ADDITIVE)
    return result


logging.basicConfig(level=logging.WARNING)
log = logging.getLogger()

def main():
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
                open_browser=config.get("OpenBrowser"),
                scope="playlist-read-collaborative playlist-read-private user-library-read user-library-modify"))

        playlists = sp.current_user_playlists()
        transfer_playlist = None
        
        for playlist in playlists['items']:
            if config["SpotifyTransferPlaylist"] == playlist.get("name"):
                transfer_playlist = sp.playlist(playlist_id=playlist["id"])
                break

        if transfer_playlist == None:
            log.critical("No transfer playlist found (%s)" % config["SPOTIFY_TRANSFER_PLAYLIST"])

        tracks_on_transfer = get_all(sp, "playlist_tracks", transfer_playlist.get("id"))
        tracks_id_trans = {}
        for track in tracks_on_transfer["items"]:
            tracks_id_trans[track.get("track").get("id")] =  track.get("track").get("name")

        tracks = get_all(sp, "current_user_saved_tracks")
        for track in tracks["items"]:
            if track.get("track").get("id") in tracks_id_trans:
                del tracks_id_trans[track.get("track").get("id")]
        print ("## Missing tracks:")
        pprint (tracks_id_trans)

if __name__ == "__main__":
    main()