"""
Reads the JSON event files and constructs media files
"""

import os
import re
import logging
from itertools import chain
from datetime import datetime, timezone
from pathlib import Path, PurePath
from typing import (
    Iterator,
    Sequence,
    List,
    NamedTuple,
    Set,
    Any,
    Dict,
    Tuple,
    Optional,
    Union,
    Callable,
)

from logzero import setup_logger  # type: ignore[import]

from .daemon import SCAN_TIME
from .serialize import parse_json_file

# TODO: better logger setup?
loglevel: int = int(os.environ.get("MPV_HISTORY_EVENTS_LOGLEVEL", logging.INFO))
logger = setup_logger("mpv_history_events", level=loglevel)

EventType = str
EventData = Any


def parse_datetime_sec(d: Union[str, float, int]) -> datetime:
    return datetime.fromtimestamp(float(d), tz=timezone.utc)


# changed to 'since_started' rather than using a timedelta
# so this is cachew compliant
# see https://github.com/karlicoss/cachew/issues/28
class Action(NamedTuple):
    # this event happened this many seconds after this media was started
    since_started: float
    action: str
    percentage: Optional[float]  # this can be None if its a livestream, those dont have a percent-pos


class Media(NamedTuple):
    path: str  # local or URL path
    is_stream: bool  # if streaming from a URL
    start_time: datetime  # when the media started playing
    end_time: datetime  # when the media was closed/finished
    pause_duration: float  # how long the media was paused for (typically 0)
    media_duration: Optional[float]  # length of the media
    # title of the media (if URL, could be <title>...</title> from ytdl
    media_title: Optional[str]
    # additional metadata on what % I was through the media while pausing/playing/seeking
    actions: List[Action]
    metadata: Dict[str, Any]  # metadata from the file, if it exists

    @property
    def score(self) -> float:
        """Describes how much data this piece of media has, to resolve conflicts"""
        sc = 0
        if self.media_title is not None:
            sc = sc + 1
        if self.media_duration is not None:
            sc = sc + 1
        if self.pause_duration > 1.0:
            sc = sc + 1
        sc = sc + int(len(self.metadata) / 4)
        sc = sc + int(len(self.actions) / 8)
        return float(sc)

    @property
    def listen_time(self) -> float:
        return (self.end_time - self.start_time).total_seconds() - self.pause_duration


Results = Iterator[Media]


def all_history(input_files: Sequence[Path]) -> Results:
    yield from chain(*map(_parse_history_file, input_files))


# use some of the context of what this piece of media
# is to figure out if I actually watched/listened to it.
# I may have skipped a song if it only has a couple
# seconds between when it started/ended
def _actually_listened_to(m: Media, require_listened_to_percent: float = 0.75) -> bool:
    listen_time: float = m.listen_time
    # if this is mpv streaming something from /dev/
    # (like my camera), ignore
    if not m.is_stream and m.path.startswith("/dev/"):
        return False
    if m.media_duration is not None and m.media_duration != 0:
        percentage_listened_to = listen_time / m.media_duration
        # if under 10 minutes (probably a song?), if I listened to at least 75% (by default)
        if m.media_duration < 600:
            return percentage_listened_to > require_listened_to_percent
    # otherwise, just check if return if I listened to at least a minute
    return listen_time > 60


# filter out items I probably didn't listen to
def history(
    input_files: Sequence[Path],
    filter_function: Callable[[Media], bool] = _actually_listened_to,
) -> Results:
    """
    can supply a function which accepts a 'Media' object as
    the first argument as the filter function
    """
    yield from filter(filter_function, all_history(input_files))


def _parse_history_file(p: Path) -> Results:
    event_data = parse_json_file(p)
    # mapping signifies this is a merged file, whose key is the old filename
    # and value is the JSON data
    if "mapping" in event_data:
        for name, data in event_data["mapping"].items():
            yield from _read_event_stream(data, filename=name)
    else:
        yield from _read_event_stream(event_data, filename=str(p))


def _read_event_stream(
    events: Any, filename: str, *, allow_if_playing_for: int = 60
) -> Results:
    # if theres a conflict, keep a 'score' by adding non-null fields on an item,
    # and return the one that has the most
    #
    # sometimes youtube-dl will show up twice ...?
    # use 'path' as a primary key to remove possible
    # duplicate event data
    items: Dict[str, Media] = {}
    for d in _reconstruct_event_stream(
        events, filename=filename, allow_if_playing_for=allow_if_playing_for
    ):
        # required keys
        if not REQUIRED_KEYS.issubset(set(d)):
            # logger.debug("Doesnt have required keys, ignoring...")
            continue
        if d["end_time"] < d["start_time"]:
            logger.warning(f"End time is less than start time! {d}")
        fdur: Optional[float] = None
        if "duration" in d:
            fdur = float(d["duration"])
        start_time = parse_datetime_sec(float(d["start_time"]))
        m = Media(
            path=d["path"],
            is_stream=d["is_stream"],
            start_time=start_time,
            end_time=parse_datetime_sec(float(d["end_time"])),
            pause_duration=float(d["pause_duration"]),
            media_duration=fdur,
            media_title=d.get("media_title"),
            actions=[
                Action(
                    since_started=(
                        parse_datetime_sec(timestamp) - start_time
                    ).total_seconds(),
                    action=data[0],
                    percentage=data[1],
                )
                for timestamp, data in d["actions"].items()
            ],
            metadata=d.get("metadata", {}),
        )
        key = m.path
        if key not in items:
            items[key] = m
        else:
            # use item with better score
            if m.score > items[key].score:
                logger.debug(f"replacing {items[key]} with {m}")
                items[key] = m
    yield from list(items.values())


REQUIRED_KEYS = set(["playlist_pos", "start_time", "path"])

IGNORED_EVENTS: Set[EventType] = set(
    [
        "playlist",
        "playlist-count",
    ]
)


URL_REGEX = re.compile(
    r"^(?:http|ftp)s?://"  # http:// or https://
    r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|"  # domain...
    r"localhost|"  # localhost...
    r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"  # ...or ip
    r"(?::\d+)?"  # optional port
    r"(?:/?|[/?]\S+)$",
    re.IGNORECASE,
)


# https://stackoverflow.com/a/7160778/9348376
def _is_urlish(url: str) -> bool:
    return re.match(URL_REGEX, url) is not None


homedir = os.path.expanduser("~")


def _reconstruct_event_stream(
    events: Any, filename: str, *, allow_if_playing_for: int
) -> Iterator[Dict[str, Any]]:
    """
    Takes about a dozen events receieved chronologically from the MPV
    socket, and reconstructs what I was doing while it was playing.
    """
    # mpv socket names are created like:
    #
    # declare -a mpv_options
    # mpv_options=(--input-ipc-server="${socket_dir}/$(date +%s%N)")
    # exec "$mpv_path" "${mpv_options[@]}"
    #
    # get when mpv launched from the filename
    start_time: Optional[float] = None
    try:
        start_time = float(int(PurePath(filename).stem) / 1e9)
    except ValueError as ve:
        logger.warning(str(ve))

    # dictionary for storing data while we parse though events
    media_data: Dict[str, Any] = {}

    # 'globals', set at the beginning
    working_dir = homedir
    is_first_item = True  # helps control how to handle duration
    # playlist_count = None
    most_recent_time: float = 0.0

    # used to help determine state
    is_playing = True  # assume playing at beginning
    pause_duration = 0.0  # pause duration for this entry
    pause_start_time: Optional[float] = None  # if the entry is paused, when it started
    actions: Dict[float, Tuple[str, float]] = {}

    # a heuristic to determine if this is an old file, is-paused can be useful
    # to help dedupe incorrect 'resumed' events that happen when a socket first connects
    seen_pause_event = False

    logger.debug(f"Reading events from {filename}")

    # sort by timestamp, incase
    for dt_s in sorted(events):
        dt_float = float(dt_s)
        most_recent_time = dt_float
        # the value is a dictionary of event_name (str) -> event_data (depends on the event)
        event_name, event_data = next(iter(events[dt_s].items()))
        if event_name in IGNORED_EVENTS:
            continue
        elif event_name == "playlist-pos":
            # reliable event to use to set start time of an item
            # the first item might have been off for 5 or so seconds
            # because of the socket_scan, so we cant use playlist-pos's
            # timestamp as the start of the mpv instance.
            # instead, we use the timestamp from the /tmp/mpvsocket/ filename
            #
            # but, if this is not the first item in the event stream,
            # use playlist-pos's timestamp as when a file starts
            if (
                "playlist_pos" in media_data
                and media_data["playlist_pos"] == event_data
            ):
                logger.debug(
                    f"Got same playlist position {event_data} twice. Current data: {media_data}"
                )
                continue
            media_data["playlist_pos"] = event_data
            if is_first_item:
                # if this is the first item, set the start time to when mpv launched
                media_data["start_time"] = start_time
                is_first_item = False  # stays false the entire function call
            else:
                media_data["start_time"] = dt_float
        elif event_name == "socket-added":
            if start_time is None:
                start_time = int(float(event_data))
        elif event_name == "working-directory":
            # shouldnt be added to media_data, affects path, but is the
            # same across the entire run of mpv
            working_dir = event_data
        elif event_name == "is-paused":
            seen_pause_event = True  # sets true for this entire file
            # if this was paused when we connected to the socket,
            # assume its been paused since close to it was launched
            if event_data is True:
                is_playing = False
                pause_start_time = start_time
        elif event_name == "path":
            media_data["is_stream"] = False
            # if its ytdl://scheme
            if event_data.startswith("ytdl://"):
                media_data[event_name] = event_data.lstrip("ytdl://")
                media_data["is_stream"] = True
                continue
            if _is_urlish(event_data):
                media_data[event_name] = event_data
                media_data["is_stream"] = True
                continue
            # test if this is an absolute path
            if event_data.startswith("/"):
                media_data[event_name] = event_data
            else:
                # I think this is fine to do?
                full_path: str = os.path.join(working_dir, event_data)
                media_data[event_name] = full_path
        elif event_name == "metadata":
            # TODO: how to parse this better?
            media_data[event_name] = event_data
        elif event_name == "media-title":
            media_data["media_title"] = event_data
        elif event_name == "duration":
            # note: path is already set (if streaming, we may not get any duration)
            assert event_data is not None
            media_data[event_name] = float(event_data)
        elif event_name in ["seek", "paused", "resumed"]:
            if event_data is not None and "percent-pos" in event_data:
                assert event_name in ["seek", "resumed", "paused"]
                if event_name in ["seek", "paused"]:
                    actions[dt_float] = (event_name, event_data["percent-pos"])
                else:
                    assert event_name == "resumed"
                    if seen_pause_event:
                        # this is a newer file which has the is-paused event, so the only action we should ignore is
                        # the 'resumed' event that happens when a socket first connects,
                        # if the file was already not playing
                        if is_playing and len(actions) == 0:
                            # the user hasnt pasued/played since actions is 0, so this must be the resumed event that
                            # happens when a socket first connects. And since it is not paused and we've seen a pause event,
                            # we are sure that the media is already playing
                            logger.debug("We've seen an is-paused event and the file is already playing, ignoring resume event")
                        else:
                            actions[dt_float] = (event_name, event_data["percent-pos"])

                    else:
                        # NOTE: theres a lot of logic here, but its mostly just for myself
                        # if you started using this at any point recently, you likely have the is-paused event in your files,
                        # which means all the heuristics here are ignored (this issue is why I added the is-paused event in the first place)
                        #
                        # the last data I have that actually uses this code is from 2021-03-18 16:52:45.565000
                        # https://github.com/seanbreckenridge/mpv-history-daemon/commit/451afb4d841262cfe0aa1a6f81fd44ef110407f6


                        # this is an old file, so we have to guess if the resume was correct by checking if it was within
                        # the first 20 seconds (would be 10, but lets give double that for the scan time/possibly rebooting daemon)
                        # of the file (the default for older versions of the daemon)
                        #
                        # if it was, then this is the 'resumed' event that happens when a socket first connects
                        # if it wasnt, then this is a resume event that happened after the file was paused
                        # so we should add it to the actions
                        if start_time is not None and dt_float - start_time <= 20 and is_playing and len(actions) == 0:
                            # this was in the first 10 seconds of the file, and its already playing, so
                            # lets assume this is the 'resumed' event that happens when a socket first connects
                            # and ignore it
                            #
                            # this should be fine anyways, as its just the action we're ignoring here, the file
                            # is already playing and we received a resume event, so we are not changing the state
                            logger.debug("Ignoring resume event in the first 20 seconds of the file while we are already playing, we cant know if this is a real resume event or not")
                        else:
                            # this might have also been a case in which mpv was already playing and you started the daemon afterwards
                            # if playlist position is higher than 0, then this was probably already paused mpv connected (but this is an old file)
                            # so we have no way to know if it was already paused with the is-paused event
                            #
                            # so, lets just yield it in this case, since it was probably real
                            #
                            # it could also just be an old file, and we're resuming after a pause. i.e. the normal case
                            actions[dt_float] = (event_name, event_data["percent-pos"])

            if event_name == "paused":
                # if a pause event was received while mpv was still playing,
                # save when it was paused, we can calculate complete pause time
                # while this piece of media was playing by combining sequences of
                # pause times
                if is_playing:
                    is_playing = False
                    pause_start_time = dt_float
            elif event_name == "resumed":
                # if its currently paused, and we received a resume event
                if not is_playing:
                    is_playing = True
                    # if we know when it was paused, add how long it was paused to pause_duration
                    # otherwise, we cant know if it had started paused before the daemon connected to the socket
                    if pause_start_time is not None:
                        pause_duration = pause_duration + (dt_float - pause_start_time)
                        pause_start_time = None
        elif event_name == "eof":
            # eof is *ALWAYS* before new data gets loaded in
            # if mpv is force quit, may not have an eof.
            # check after to make sure eof/mpv-quit/final-write
            # was the last item, else write out whatever
            # media_data has in the dict currently
            if not is_playing:
                pause_duration = pause_duration + (dt_float - pause_start_time)  # type: ignore[operator]
            media_data["end_time"] = dt_float
            media_data["pause_duration"] = pause_duration
            media_data["actions"] = actions
            pause_duration = 0
            yield media_data
            media_data = {}
            actions = {}
        elif event_name in ["mpv-quit", "final-write"]:
            # if this happened right after an eof, it can be ignored

            # if the eof didnt happen and mpv was quit manually, save
            # quit time as end_time
            if REQUIRED_KEYS.issubset(set(media_data)):
                # if I quit while it was paused
                if not is_playing and pause_start_time is not None:
                    pause_duration = pause_duration + (dt_float - pause_start_time)
                media_data["end_time"] = dt_float
                media_data["pause_duration"] = pause_duration
                media_data["actions"] = actions
                yield media_data
            return
        else:
            logger.warning(f"Unexpected event name {event_name}")

    if len(media_data) != 0:
        # if we have enough of the fields in the namedtuple, then this isnt
        # a corrupted file, its one that didnt have an eof/had events
        # after an eof for some reason
        if not REQUIRED_KEYS.issubset(set(media_data)):
            logger.debug("Ignoring leftover data... {}".format(media_data))
        else:
            # if we got through all the keys, and this has been playing for at least a minute (or allow_if_playing_for)
            # even though this is sorta broken, log it anyways
            if most_recent_time - int(media_data["start_time"]) > allow_if_playing_for:
                # if it crashed while it was paused
                if not is_playing and pause_start_time is not None:
                    pause_duration = pause_duration + (
                        most_recent_time - pause_start_time
                    )
                logger.debug(
                    "slightly broken, but yielding anyways... {}".format(media_data)
                )
                media_data["end_time"] = most_recent_time
                media_data["pause_duration"] = pause_duration
                media_data["actions"] = actions
                yield media_data
