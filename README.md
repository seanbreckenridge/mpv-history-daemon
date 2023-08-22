# mpv-history-daemon

This functions by connecting to socket files created by [`mpv-sockets`](https://github.com/seanbreckenridge/mpv-sockets). The `mpv` script there launches mpv with unique mpv sockets at `/tmp/mpvsockets/`.

For each `mpv` socket, this attaches event handlers which tell me whenever a file in a playlist ends, whenever I seek (skip), what the current working directory/path is, and whenever I play/pause an item. Once the `mpv` instance quits, it saves all the events to a JSON file.

Later, I can reconstruct whether or not a file was paused/playing based on the events, how long `mpv` was open, and which file was playing, in addition to being able to see what file/URL I was playing.

### Install

Requires `python3.8+`

    pip install mpv-history-daemon

### Known Issues

For whatever reason, this stops working after a few days of continuous use (perhaps because of my laptop suspending?), so I wrap this with another script which restarts this every so often if there are no open `mpv` instances. I would recommend starting this by running:

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
  --log-file PATH         location of logfile
  --write-period INTEGER  How often to write to files while mpv is open
  --help                  Show this message and exit.
```

Some logs, to get an idea of what this captures:

```
1598956534118491075|1598957274.3349547|mpv-launched|1598957274.334953
1598956534118491075|1598957274.335344|working-directory|/home/sean/Music
1598956534118491075|1598957274.3356173|playlist-count|12
1598956534118491075|1598957274.3421223|playlist-pos|2
1598956534118491075|1598957274.342346|path|Masayoshi Takanaka/Masayoshi Takanaka - Alone (1988)/02 - Feedback's Feel.mp3
1598956534118491075|1598957274.3425295|media-title|Feedback's Feel
1598956534118491075|1598957274.3427346|metadata|{'title': "Feedback's Feel", 'album': 'Alone', 'genre': 'Jazz', 'album_artist': '高中正義', 'track': '02/8', 'disc': '1/1', 'artist': '高中正義', 'date': '1981'}
1598956534118491075|1598957274.342985|duration|351.033469
1598956534118491075|1598957274.343794|resumed|{'percent-pos': 66.85633}
1598956534118491075|1598957321.3952177|eof|None
1598956534118491075|1598957321.3955588|mpv-quit|1598957321.395554
Ignoring error: [Errno 32] Broken pipe
Connected refused for socket at /tmp/mpvsockets/1598956534118491075, removing dead socket file...
/tmp/mpvsockets/1598956534118491075: writing to file...
```

More events would keep getting logged, as I pause/play, or the file ends and a new file starts. The key for each JSON value is the epoch time, so everything is timestamped.

By default, this scans the socket directory every 10 seconds -- to increase that you can set the `MPV_HISTORY_DAEMON_SCAN_TIME` environment variable, e.g. `MPV_HISTORY_DAEMON_SCAN_TIME=5`

#### custom SocketData class

You can pass a custom socket data class with to `daemon` with `--socket-class-qualname`, which lets you customize the behaviour of the `SocketData` class. For example, I override particular events (see [`SocketDataServer`](https://github.com/seanbreckenridge/currently_listening/blob/main/currently_listening_py/currently_listening_py/socket_data.py)) to intercept data and send it to my [`currently_listening`](https://github.com/seanbreckenridge/currently_listening) server, which among other things displays my currently playing mpv song in discord:

![demo discord image](https://github.com/seanbreckenridge/currently_listening/blob/main/.github/discord.png?raw=true)

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

### merge

After a while using this, I end up with thousands of JSON files in my data directory, which does use up some unnecessary space, and increases time to parse since it has to open thousands of files.

Those can be merged into a single file (which `parse` can still read fine) using the `merge` command:

```
Usage: mpv-history-daemon merge [OPTIONS] DATA_FILES...

  merges multiple files into a single merged event file

Options:
  --move DIRECTORY         Directory to move 'consumed' event files to, i.e.,
                           a 'remove' these from the source directory once
                           they've been merged
  --write-to PATH          File to merge all data into  [required]
  --mtime-seconds INTEGER  If files have been modified in this amount of time,
                           don't merge them
  --help                   Show this message and exit.
```

Merged files look like:

```json
{
  "mapping": {
    "1611383220380934268.json": {"1619915695.2387643":{"socket-added":1619915695.238762}},
    ...
  }
}
```

... saving the filename and the corresponding data from the original files

It doesn't merge any event files who've recently (within an hour) been written to, to avoid possibly interfering with current files the daemon may be writing to.

If you want to automatically remove files which get merged into the one file, you can use the `--move` flag, like:

`mpv-history-daemon merge ~/data/mpv --move ~/.cache/mpv_removed --write-to ~/data/mpv/"merged-$(date +%s).json"`

That takes any eligible files in `~/data/mpv` (merged or new event files), merges them all into `~/data/mpv/merged-...json` (unique filename using the date), and then moves all the files that were merged to `~/.cache/mpv_removed` (moving them to some temporary directory so you can review the merged file, instead of deleting)

My personal script which does this is synced up [here](https://github.com/seanbreckenridge/bleanser/blob/master/bin/merge-mpv-history)
