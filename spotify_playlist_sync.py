import argparse
import spotipy
from spotipy.oauth2 import SpotifyOAuth, CacheFileHandler
import logging
from pprint import pformat
import yaml
from mergedeep import merge, Strategy
import schedule
import time


logging.basicConfig(format='%(asctime)s %(message)s', level=logging.WARNING)
log = logging.getLogger()

auth_cache = {}

def get_all(sp, function, limit=50, *args):
    log.debug("Call get_all with function: %s" % function)
    func = getattr(sp, function)
    result = func(*args, limit=limit)
    while result.get("next"):
        log.debug("Next page for call %s" % function)
        res = sp.next(result)
        merge(result, res, strategy=Strategy.ADDITIVE)
    return result


def auth(account, config):
    """Handles the authentication for the various accounts
    """
    global auth_cache
    if account["Username"] in auth_cache:
        return auth_cache[account["Username"]]

    handler = CacheFileHandler(username=account["Username"])
    sp = spotipy.Spotify(
        auth_manager=SpotifyOAuth(
            client_id=account.get("ClientId"),
            client_secret=account["Secret"],
            redirect_uri=account.get("RedirectUrl"),
            cache_handler=handler,
            open_browser=config.get("OpenBrowser"),
            scope="playlist-read-collaborative " +
                  "playlist-read-private " +
                  "user-library-read " +
                  "user-library-modify " +
                  "playlist-modify-private " +
                  "playlist-modify-public"),
        retries=10,
        status_retries=10,
        backoff_factor=1.0)
    log.info("Authenicated with user %s" % account["Username"])
    auth_cache[account["Username"]] = sp
    return sp


def indentify_transfer_playlist(sp, config):
    playlists = get_all(sp, "current_user_playlists")

    for playlist in playlists['items']:
        if config["SpotifyTransferPlaylist"] == playlist.get("name"):
            return playlist

    log.critical("No transfer playlist found (%s)" %
                 config["SpotifyTransferPlaylist"])
    exit(1)


def main(args):
    with open(args.config_file) as f:
        config = yaml.full_load(f)
    log.setLevel(config.get("LogLevel"))

    transfer_playlist = None
    tracks_on_transfer = None

    for account in config.get("accounts"):
        sp = auth(account, config)

        if transfer_playlist is None:
            transfer_playlist = indentify_transfer_playlist(sp, config)
            tracks_on_transfer = get_all(sp, "playlist_tracks", 100,
                                         transfer_playlist.get("id"))

        tracks_id_trans = {}
        for track in tracks_on_transfer["items"]:
            tracks_id_trans[track["item"]["id"]] = track["item"].get("name")

        tracks = get_all(sp, "current_user_saved_tracks")
        for track in tracks["items"]:
            if track.get("track").get("id") in tracks_id_trans:
                del tracks_id_trans[track.get("track").get("id")]
        if args.add and tracks_id_trans:
            log.info("Missing tracks :" + pformat(tracks_id_trans))
            ids = list(tracks_id_trans.keys())
            for i in range(0, len(ids), 50):
                sp.current_user_saved_tracks_add(ids[i:i+50])

    if args.empty_transfer:
        if transfer_playlist is None:
            sp = auth(config["accounts"][0], config)
            transfer_playlist = indentify_transfer_playlist(sp, config)
            tracks_on_transfer = get_all(sp, "playlist_tracks", 100,
                                         transfer_playlist.get("id"))
        else:
            sp = auth(config["accounts"][0], config)

        tracks_id_trans = [track.get("item").get("id")
                           for track in tracks_on_transfer["items"]]
        if tracks_id_trans:
            log.info("Removing tracks (%s) from %s" %
                    (tracks_id_trans, transfer_playlist["name"]))
            for i in range(0, len(tracks_id_trans), 100):
                sp.playlist_remove_all_occurrences_of_items(
                    playlist_id=transfer_playlist["id"],
                    items=tracks_id_trans[i:i+100])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Spotify playlist sync')
    parser.add_argument('--config-file', "-c",
                        help='Config file (default config.yaml)',
                        default="config.yaml")
    parser.add_argument('--add', action="store_true", default=False,
                        help='Add missing tracks to saved tracks')
    parser.add_argument('--empty-transfer', "-e", action="store_true",
                        default=False,
                        help='Remove all songs from transfer playlist')
    parser.add_argument('--daemon', "-d", action="store_true",
                        default=False,
                        help='Keep running and syncing')
    parser.add_argument('--frequency',
                        default=5,
                        help='Sync frequency in minutes')
    args = parser.parse_args()

    main(args)
    if args.daemon:
        schedule.every(args.frequency).minutes.do(main, args=args)
        log.info("Run every %s minutes from now" % args.frequency)
        while True:
            schedule.run_pending()
            time.sleep(10)
