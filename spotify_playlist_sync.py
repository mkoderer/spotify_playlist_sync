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
saved_tracks_cache = {}  # username -> set of saved track IDs

def get_all(sp, function, limit=50, *args):
    log.debug("Call get_all with function: %s" % function)
    func = getattr(sp, function)
    try:
        result = func(*args, limit=limit)
    except spotipy.SpotifyException as e:
        log.error(e)
        raise e
    while result.get("next"):
        log.debug("Next page for call %s" % function)
        res = sp.next(result)
        time.sleep(0.1)
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
        retries=5,
        status_retries=5,
        backoff_factor=1.0)
    log.info("Authenicated with user %s" % account["Username"])
    auth_cache[account["Username"]] = sp
    return sp


def get_saved_tracks(sp, username):
    """Fetch saved tracks incrementally, stopping early if all transfer IDs are already known.
    Returns a set of saved track IDs. Results are cached across daemon runs."""
    global saved_tracks_cache
    if username not in saved_tracks_cache:
        saved_tracks_cache[username] = set()

    cache = saved_tracks_cache[username]
    result = sp.current_user_saved_tracks(limit=50)
    while result:
        for item in result["items"]:
            track_id = item["track"]["id"]
            if track_id in cache:
                # Reached a track we already know — rest of the list is known too
                log.debug("Early exit: reached cached track %s" % track_id)
                return cache
            cache.add(track_id)
        result = sp.next(result) if result.get("next") else None
        if result:
            time.sleep(0.1)
    return cache


def indentify_transfer_playlist(sp, config):
    result = sp.current_user_playlists(limit=50)
    while result:
        for playlist in result['items']:
            if config["SpotifyTransferPlaylist"] == playlist.get("name"):
                return playlist
        result = sp.next(result) if result.get("next") else None
        if result:
            time.sleep(0.1)

    log.critical("No transfer playlist found (%s)" %
                 config["SpotifyTransferPlaylist"])
    exit(1)

transfer_playlist = None

def main(args):
    with open(args.config_file) as f:
        config = yaml.full_load(f)
    log.setLevel(config.get("LogLevel"))

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

        # Check transfer tracks against cached saved tracks, fetching incrementally if needed
        if tracks_id_trans:
            saved = get_saved_tracks(sp, account["Username"])
            for track_id in list(tracks_id_trans.keys()):
                if track_id in saved:
                    del tracks_id_trans[track_id]

            if args.add and tracks_id_trans:
                log.info("Missing tracks :" + pformat(tracks_id_trans))
                ids = list(tracks_id_trans.keys())
                for i in range(0, len(ids), 50):
                    sp.current_user_saved_tracks_add(ids[i:i+50])
                saved_tracks_cache.get(account["Username"], set()).update(ids)

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
