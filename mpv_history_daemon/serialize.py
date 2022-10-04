import os
import json
from typing import Any

# try using orjson to speedup load/compact dumped data
# if its installed, otherwise use default stdlib module

try:
    import orjson  # type: ignore[import]

    def parse_json_file(file: os.PathLike) -> Any:
        with open(file) as f:
            return orjson.loads(f.read())

    def dump_json(data: Any) -> str:
        bdata: bytes = orjson.dumps(data, option=orjson.OPT_NON_STR_KEYS)
        return bdata.decode("utf-8")

except ImportError:

    def parse_json_file(file: os.PathLike) -> Any:
        import json

        with open(file) as f:
            return json.load(f)

    def dump_json(data: Any) -> str:
        return json.dumps(data)
