import sys
import datetime
from pathlib import Path
from typing import Any

import click
import simplejson
from logzero import setup_logger  # type: ignore[import]

from .daemon import run
from .events import history, all_history
from .events import logger as event_logger


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
    default="/tmp/mpv-history-daemon.log",
    help="location of logfile",
)
def daemon(socket_dir: str, data_dir: str, log_file: str) -> None:
    """
    Socket dir is the directory with mpv sockets (/tmp/mpvsockets, probably)
    Data dir is the directory to store the history JSON files
    """
    run(socket_dir, data_dir, log_file)


def default_encoder(o: Any) -> Any:
    if isinstance(o, datetime.datetime):
        return int(o.timestamp())
    raise TypeError(f"{o} of type {type(o)} is not serializable")


@cli.command()
@click.argument("DATA_DIR")
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
def parse(data_dir: str, all_events: bool, debug: bool) -> None:
    """
    Takes the data directory and parses events into Media
    """
    global event_logger
    if debug:
        event_logger = setup_logger(__name__, level="DEBUG")
    events_func: Any = all_history if all_events else history
    ddir: Path = Path(data_dir)
    if not ddir.exists():
        click.echo(f"{data_dir} does not exist", err=True)
        sys.exit(1)
    if not ddir.is_dir():
        click.echo(f"{data_dir} is not a directory", err=True)
        sys.exit(1)
    click.echo(
        simplejson.dumps(
            list(events_func(list(ddir.iterdir()))),
            default=default_encoder,
            namedtuple_as_object=True,
        )
    )


if __name__ == "__main__":
    cli(prog_name="mpv-history-daemon")
