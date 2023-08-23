"""
Utility scripts or functions that could be useful for other projects

As these have no dependencies, locating it here makes it easier to use in lots of places
"""

import os
import logging
from urllib.parse import urlparse
from typing import Dict, Optional, Tuple, Any, NamedTuple, List

from .events import Media


class MusicMetadata(NamedTuple):
    title: str
    album: str
    artist: str


def music_parse_metadata_from_blob(
    data: Dict[str, Any],
    strip_whitespace: bool = False,
) -> Optional[MusicMetadata]:
    if "title" not in data or "album" not in data or "artist" not in data:
        return None
    title = data["title"]
    album = data["album"]
    artist = data["artist"]
    if title and artist and album:
        if strip_whitespace:
            return MusicMetadata(title.strip(), album.strip(), artist.strip())
        else:
            return MusicMetadata(title, album, artist)
    return None


class MediaAllowed:
    """
    A helper class to organize/filter media based on prefixes, extensions, and streaming etc.

    Typically used to filter out media streams (from your camera), livestreams (watching youtube/twitch) through mpv
    And generally just using mpv while editing videos/viewing things in your media folder that arent Movies/TV/Music etc.

    allow_prefixes: A list of prefixes that are allowed, like ["/home/user/Music", "/home/user/Videos"]
    ignore_prefixes: A list of prefixes that are ignored, like ["/home/user/Downloads", "/home/user/.cache"]
    allow_extensions: A list of extensions that are allowed, like [".mp3", ".mp4", ".mkv"]
    ignore_extensions: A list of extensions that are ignored, like [".jpg", ".png", ".gif"]
    allow_stream: If True, allow streams (like from your camera, youtube etc)
    strict: If True, only allow media that is in allow_prefixes and not in ignore_prefixes, warns otherwise
    logger: A logger to log to, if None, no logging is done
    """

    def __init__(
        self,
        *,
        allow_prefixes: Optional[List[str]] = None,
        ignore_prefixes: Optional[List[str]] = None,
        allow_extensions: Optional[List[str]] = None,
        ignore_extensions: Optional[List[str]] = None,
        allow_stream: bool = False,
        strict: bool = True,
        logger: Optional[logging.Logger] = None,
    ):
        self.allow_prefixes = allow_prefixes if allow_prefixes else []
        self.ignored_prefixes = ignore_prefixes if ignore_prefixes else []
        self.ignored_prefixes.extend(self.__class__.default_ignore())
        ignored_ext = ignore_extensions if ignore_extensions else []
        self.ignore_extensions = [
            self.__class__._fix_extension(ext) for ext in ignored_ext
        ]
        allowed_ext = allow_extensions if allow_extensions else []
        self.allow_extensions = [
            self.__class__._fix_extension(ext) for ext in allowed_ext
        ]
        self.allow_stream = allow_stream
        self.strict = strict
        self._logger = logger

    def __str__(self) -> str:
        return f"{self.__class__.__name__}(allow_prefixes={self.allow_prefixes}, ignored_prefixes={self.ignored_prefixes}, allow_extensions={self.allow_extensions}, ignore_extensions={self.ignore_extensions}, allow_stream={self.allow_stream}, strict={self.strict})"

    def __repr__(self) -> str:
        return str(self)

    @staticmethod
    def _fix_extension(ext: str) -> str:
        if ext.startswith("."):
            return ext.lower()
        return f".{ext}".lower()

    @staticmethod
    def _parse_url_extension(ext: str) -> str:
        """
        receives something like .ext?query=1&query2=2, returns .ext
        """
        if "?" in ext:
            parts = urlparse(ext)
            return parts.path
        return ext

    @classmethod
    def default_ignore(cls) -> List[str]:
        return ["/tmp", "/dev"]

    def is_allowed(self, media: Media) -> bool:
        # allow/ignore based on streaming
        if not self.allow_stream and media.is_stream:
            if self._logger:
                self._logger.debug(f"Media {media.path} is a stream")
            return False

        # allow/ignore based on extension
        _, ext = os.path.splitext(media.path)
        if ext:
            ext = self.__class__._parse_url_extension(ext.lower())
            if ext in self.ignore_extensions:
                if self._logger:
                    self._logger.debug(
                        f"Media {media.path} has an ignored extension {ext}"
                    )
                return False
            if self.allow_extensions and ext not in self.allow_extensions:
                if self._logger:
                    self._logger.warning(
                        f"Media {media.path} has an extension {ext} not in allowed extensions={self.allow_extensions} or ignored extensions={self.ignore_extensions}"
                    )
                return False

        if self.allow_prefixes and any(
            media.path.startswith(prefix) for prefix in self.allow_prefixes
        ):
            return True

        if self.ignored_prefixes and any(
            media.path.startswith(prefix) for prefix in self.ignored_prefixes
        ):
            if self._logger:
                self._logger.debug(
                    f"Media {media.path} is in ignore prefixes {self.ignored_prefixes}, ignoring..."
                )
            return False

        if len(self.allow_prefixes) > 0 and self.strict:
            if self._logger:
                self._logger.warning(
                    f"Media {media.path} is not in allowed prefixes {self.allow_prefixes}. Add it to allow_prefixes or ignore_prefixes, or set False to automatically allow non-matching paths"
                )
            return False

        return True
