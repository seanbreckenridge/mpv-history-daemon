import click
from .daemon import run


@click.group()
def cli():
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

if __name__ == "__main__":
    cli(prog_name="mpv-history-daemon")
