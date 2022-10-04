import time
from pathlib import Path
from typing import List, Any, Dict, NamedTuple

from .serialize import parse_json_file


def _is_merged_data(data: Dict[Any, Any]) -> bool:
    assert isinstance(data, dict), f"{data}"
    # top-level mapping key to indicate this is a merged datafile
    return "mapping" in data


class MergeResult(NamedTuple):
    merged_data: Dict[str, Any]
    consumed_files: List[Path]


def merge_files(files: List[Path], mtime_seconds_since: int = 3600) -> MergeResult:
    """
    files can be either merged files, event files or a combination
    mtime_seconds_since makes sure were not writing to files that were
    recently modified
    """
    merged_files: Dict[Path, Dict[Any, Any]] = {}
    event_files: List[Path] = []
    consumed_files: List[Path] = []
    for f in files:
        data = parse_json_file(f)
        if _is_merged_data(data):
            merged_files[f] = data
        else:
            since_write = time.time() - f.stat().st_mtime
            if since_write < mtime_seconds_since:
                continue
            event_files.append(f)

    # merge merged files
    merged = {}
    for merged_path, merged_data in merged_files.items():
        assert "mapping" in merged_data
        merged.update(merged_data["mapping"])
        consumed_files.append(merged_path)

    # merge event files
    for event_f in event_files:
        event_data = parse_json_file(event_f)
        assert "mapping" not in event_data
        merged[event_f.name] = event_data
        consumed_files.append(event_f)

    return MergeResult(
        merged_data={"mapping": dict(sorted(merged.items()))},
        consumed_files=consumed_files,
    )
