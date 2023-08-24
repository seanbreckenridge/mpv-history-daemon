import os
import datetime
import shutil
import logging
import importlib
from pathlib import Path
from typing import Any, Optional, Sequence, Iterator, Optional
from tempfile import gettempdir

import click
import simplejson
from logzero import setup_logger  # type: ignore[import]

from .daemon import run, SocketData
from .events import history, all_history
from .merge import merge_files
from .serialize import dump_json
from . import events as events_module


@click.group()
def cli():
    """
    Connects to mpv socket files and saves a history of events
    """
    pass


@cli.command()
@click.argument("SOCKET_DIR")
@click.argument("DATA_DIR")
@click.option(
    "--log-file",
    type=click.Path(),
    default=os.path.join(gettempdir(), "mpv-history-daemon.log"),
    help="location of logfile",
)
@click.option(
    "--write-period",
    type=int,
    default=None,
    help="How often to write to files while mpv is open",
)
@click.option(
    "--socket-class-qualname",
    type=str,
    default=None,
    help="Fully qualified name of the class to use for socket data, e.g., 'mpv_history_daemon.daemon.SocketData'. This imports the class and uses it for socket data.",
)
def daemon(
    socket_dir: str,
    data_dir: str,
    log_file: str,
    write_period: Optional[int],
    socket_class_qualname: Optional[str],
) -> None:
    """
    Socket dir is the directory with mpv sockets (/tmp/mpvsockets, probably)
    Data dir is the directory to store the history JSON files
    """
    socketclass = SocketData
    if socket_class_qualname is not None:
        module_name, class_name = socket_class_qualname.rsplit(".", 1)
        module = importlib.import_module(module_name)
        socketclass = getattr(module, class_name)
        assert issubclass(socketclass, SocketData)
    run(
        socket_dir=socket_dir,
        data_dir=data_dir,
        log_file=log_file,
        write_period=write_period,
        socket_data_cls=socketclass,
    )


def default_encoder(o: Any) -> Any:
    if isinstance(o, datetime.datetime):
        return int(o.timestamp())
    raise TypeError(f"{o} of type {type(o)} is not serializable")


def _resolve_paths(paths: Sequence[str]) -> Iterator[Path]:
    for p in map(Path, paths):
        if p.is_dir():
            yield from p.iterdir()
        else:
            yield p


@cli.command()
@click.argument("DATA_FILES", type=click.Path(exists=True), nargs=-1, required=True)
@click.option(
    "--all-events",
    is_flag=True,
    default=False,
    help="return all events, even ones which by context you probably didn't listen to",
)
@click.option(
    "--debug",
    is_flag=True,
    default=False,
    help="Increase log verbosity/print warnings while parsing JSON files",
)
def parse(data_files: Sequence[str], all_events: bool, debug: bool) -> None:
    """
    Takes the data directory and parses events into Media
    """
    if debug:
        events_module.logger = setup_logger("mpv_history_events", level=logging.DEBUG)
    events_func: Any = all_history if all_events else history
    json_files = list(_resolve_paths(data_files))
    click.echo(
        simplejson.dumps(
            list(events_func(json_files)),
            default=default_encoder,
            namedtuple_as_object=True,
        )
    )


@cli.command()
@click.argument("DATA_FILES", type=click.Path(exists=True), nargs=-1, required=True)
@click.option(
    "--move",
    type=click.Path(path_type=Path, file_okay=False, dir_okay=True),
    required=False,
    default=None,
    help="Directory to move 'consumed' event files to, i.e., a 'remove' these from the source directory once they've been merged",
)
@click.option(
    "--write-to",
    type=click.Path(path_type=Path),
    required=True,
    help="File to merge all data into",
)
@click.option(
    "--mtime-seconds",
    type=int,
    default=3600,
    help="If files have been modified in this amount of time, don't merge them",
)
def merge(
    data_files: Sequence[str], move: Optional[Path], write_to: Path, mtime_seconds: int
) -> None:
    """
    merges multiple files into a single merged event file
    """
    json_files = list(_resolve_paths(data_files))
    if move is not None:
        move.mkdir(parents=True, exist_ok=True)
    res = merge_files(json_files, mtime_seconds_since=mtime_seconds)
    data = dump_json(res.merged_data)
    if move is not None:
        for old in res.consumed_files:
            new = move / old.name
            events_module.logger.info(f"Moving {old} to {new}")
            shutil.move(str(old), str(new))
    write_to.write_text(data)


if __name__ == "__main__":
    cli(prog_name="mpv-history-daemon")
