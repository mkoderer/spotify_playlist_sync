import argparse
import spotipy
from spotipy.oauth2 import SpotifyOAuth, CacheFileHandler
import logging
from pprint import pformat
import yaml
from mergedeep import merge, Strategy
import schedule
import time


logging.basicConfig(level=logging.WARNING)
log = logging.getLogger()


def get_all(sp, function, *arg):
    log.info("Call get_all with function: %s" % function)
    func = getattr(sp, function)
    result = func(*arg)
    while result.get("next"):
        log.debug("Next page for call %s" % function)
        res = sp.next(result)
        merge(result, res, strategy=Strategy.ADDITIVE)
    return result


def auth(account, config):
    """Handles the authentication for the various accounts
    """
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
                  "playlist-modify-public"))
    log.info("Authenicated with user %s" % account["Username"])
    return sp


def indentify_transfer_playlist(sp, config):
    playlists = get_all(sp, "current_user_playlists")
    transfer_playlist = None

    for playlist in playlists['items']:
        if config["SpotifyTransferPlaylist"] == playlist.get("name"):
            transfer_playlist = sp.playlist(playlist_id=playlist["id"])
            break

    if transfer_playlist is None:
        log.critical("No transfer playlist found (%s)" %
                     config["SPOTIFY_TRANSFER_PLAYLIST"])
        exit(1)
    return transfer_playlist


def main(args):
    with open(args.config_file) as f:
        config = yaml.full_load(f)
    log.setLevel(config.get("LogLevel"))
    for account in config.get("accounts"):
        sp = auth(account, config)

        transfer_playlist = indentify_transfer_playlist(sp, config)
        tracks_on_transfer = get_all(sp, "playlist_tracks",
                                     transfer_playlist.get("id"))
        tracks_id_trans = {}
        for track in tracks_on_transfer["items"]:
            id = track["track"]["id"]
            tracks_id_trans[id] = track["track"].get("name")

        tracks = get_all(sp, "current_user_saved_tracks")
        for track in tracks["items"]:
            if track.get("track").get("id") in tracks_id_trans:
                del tracks_id_trans[track.get("track").get("id")]
        log.info("Missing tracks :" + pformat(tracks_id_trans))
        if args.add and tracks_id_trans:
            log.info("Adding missing tracks")
            sp.current_user_saved_tracks_add(tracks_id_trans.keys())

    if args.empty_transfer:
        sp = auth(config["accounts"][0], config)
        tracks_on_transfer = get_all(sp, "playlist_tracks",
                                     transfer_playlist.get("id"))
        tracks_id_trans = []
        for track in tracks_on_transfer["items"]:
            tracks_id_trans.append(track.get("track").get("id"))

        transfer_playlist = indentify_transfer_playlist(sp, config)
        log.info("Removing tracks (%s) from %s" %
                 (tracks_id_trans, transfer_playlist["name"]))
        sp.playlist_remove_all_occurrences_of_items(
            playlist_id=transfer_playlist["id"],
            items=tracks_id_trans)


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
