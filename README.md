# mpv-history-daemon

This functions by connecting to socket files created by [`mpv-sockets`](https://github.com/seanbreckenridge/mpv-sockets). That launches mpv with unique mpv sockets at `/tmp/mpvsockets/`.

For each `mpv` socket, this attaches event handlers which tell me whenever a file in a playlist ends, whenever I seek (skip), what the current working directory/path is, and whenever I play/pause an item. Once the `mpv` instance quits, it saves all the events to a JSON file.

Later, I can reconstruct whether or not a file was paused/playing based on the events, how long `mpv` was open, and which file was playing, in addition to being able to see what file/URL I was playing.

### Install

Requires `python3.6+`

    pip install mpv-history-daemon

### Known Issues

For whatever reason, this stops working after a few days of continuous use, so I wrap this with another script which restarts this every so often. I would recommend starting this by running:

```
mpv_history_daemon_restart /your/data/dir
```

## Usage

### daemon

```
Usage: mpv-history-daemon daemon [OPTIONS] SOCKET_DIR DATA_DIR

  Socket dir is the directory with mpv sockets (/tmp/mpvsockets, probably)
  Data dir is the directory to store the history JSON files

Options:
  --log-file PATH  location of logfile
  --help           Show this message and exit.
```

Some logs, to get an idea of what this captures:

```
[D 200901 03:47:54 mpv-history-daemon:115] 1598956534118491075|1598957274.3349547|mpv-launched|1598957274.334953
[D 200901 03:47:54 mpv-history-daemon:115] 1598956534118491075|1598957274.335344|working-directory|/home/sean/Music
[D 200901 03:47:54 mpv-history-daemon:115] 1598956534118491075|1598957274.3356173|playlist-count|12
[D 200901 03:47:54 mpv-history-daemon:115] 1598956534118491075|1598957274.3421223|playlist-pos|2
[D 200901 03:47:54 mpv-history-daemon:115] 1598956534118491075|1598957274.342346|path|Masayoshi Takanaka/Masayoshi Takanaka - Alone (1988)/02 - Feedback's Feel.mp3
[D 200901 03:47:54 mpv-history-daemon:115] 1598956534118491075|1598957274.3425295|media-title|Feedback's Feel
[D 200901 03:47:54 mpv-history-daemon:115] 1598956534118491075|1598957274.3427346|metadata|{'title': "Feedback's Feel", 'album': 'Alone', 'genre': 'Jazz', 'album_artist': '高中正義', 'track': '02/8', 'disc': '1/1', 'artist': '高中正義', 'date': '1981'}
[D 200901 03:47:54 mpv-history-daemon:115] 1598956534118491075|1598957274.342985|duration|351.033469
[D 200901 03:47:54 mpv-history-daemon:115] 1598956534118491075|1598957274.343794|resumed|{'percent-pos': 66.85633}
[D 200901 03:48:41 mpv-history-daemon:115] 1598956534118491075|1598957321.3952177|eof|None
[D 200901 03:48:41 mpv-history-daemon:115] 1598956534118491075|1598957321.3955588|mpv-quit|1598957321.395554
[W 200901 03:48:41 mpv-history-daemon:186] Ignoring error: [Errno 32] Broken pipe
[D 200901 03:48:44 mpv-history-daemon:236] Connected refused for socket at /tmp/mpvsockets/1598956534118491075, removing dead socket file...
[I 200901 03:48:44 mpv-history-daemon:314] /tmp/mpvsockets/1598956534118491075: writing to file...
```

More events would keep getting logged, as I pause/play, or the file ends and a new file starts. The key for each JSON value is the epoch time, so everything is timestamped.

### parse

The daemon saves the raw event data above in JSON files, which can then be parsed into individual instances of media:

```
$ mpv-history-daemon parse --help
Usage: mpv-history-daemon parse [OPTIONS] DATA_DIR

  Takes the data directory and parses events into Media

Options:
  --all-events  return all events, even ones which by context you probably
                didn't listen to

  --debug       Increase log verbosity/print warnings while parsing JSON files
  --help        Show this message and exit.
```

As an example:

```json
{
  "path": "/home/data/media/music/MF DOOM/Madvillain - Madvillainy/04 - Madvillain - Bistro.mp3",
  "is_stream": false,
  "start_time": 1614905952,
  "end_time": 1614906040,
  "pause_duration": 20.578377723693848,
  "media_duration": 67.578776,
  "media_title": "04 - Madvillain - Bistro.mp3",
  "percents": [
    [1614905960, 11.150022],
    [1614905981, 11.151141]
  ],
  "metadata": {}
}
```

This can also be called from python:

```python
>>> from pathlib import Path
>>> from mpv_history_daemon.events import history
>>> list(history([Path("1611383220380934268.json")]))
[
  Media(path='/home/data/media/music/MF DOOM/Madvillain - Madvillainy/05 - Madvillain - Raid [feat. M.E.D. aka Medaphoar].mp3',
  is_stream=False,
  start_time=datetime.datetime(2021, 1, 23, 6, 27, tzinfo=datetime.timezone.utc),
  end_time=datetime.datetime(2021, 1, 23, 6, 29, 30, tzinfo=datetime.timezone.utc),
  pause_duration=0.0,
  media_duration=150.569796,
  media_title='Raid [feat. M.E.D. aka Medaphoar]',
  percents=[(datetime.datetime(2021, 1, 23, 6, 27, 2, tzinfo=datetime.timezone.utc), 1.471624)]
  metadata={})
]
```
