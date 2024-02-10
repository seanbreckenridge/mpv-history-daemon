import os
import json
from typing import Any

from kompress import CPath  # type: ignore[import]

# try using orjson to speedup load/compact dumped data
# if its installed, otherwise use default stdlib module

try:
    import orjson  # type: ignore[import]

    def parse_json_file(file: os.PathLike) -> Any:
        pth = CPath(file) if not isinstance(file, CPath) else file  # type: ignore[no-untyped-call]

        with pth.open() as f:  # type: ignore[no-untyped-call]
            return orjson.loads(f.read())  # type: ignore[no-untyped-call]

    def dump_json(data: Any) -> str:
        bdata: bytes = orjson.dumps(data, option=orjson.OPT_NON_STR_KEYS)
        return bdata.decode("utf-8")

except ImportError:

    def parse_json_file(file: os.PathLike) -> Any:
        import json

        pth = CPath(file) if not isinstance(file, CPath) else file  # type: ignore[no-untyped-call]

        with pth.open() as f:  # type: ignore[no-untyped-call]
            return json.load(f)

    def dump_json(data: Any) -> str:
        return json.dumps(data)
