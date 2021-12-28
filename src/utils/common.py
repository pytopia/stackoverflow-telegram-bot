import datetime
import itertools
import json
from typing import Iterable, Tuple


def human_readable_size(size, decimal_places=1):
    for unit in ['B', 'KiB', 'MiB', 'GiB', 'TiB']:
        if size < 1024.0:
            break
        size /= 1024.0
    return f"{size:.{decimal_places}f} {unit}"


def human_readable_unix_time(unix_time, timezone=None):
    if timezone is None:
        timezone = datetime.timezone.utc
    return datetime.datetime.fromtimestamp(unix_time, timezone).strftime('%B %d %Y %H:%M:%S')


def json_encoder(obj):
    try:
        json.dumps(obj)
        return obj
    except Exception as e:
        return None


def chunked_iterable(iterable: Iterable, size: int) -> Tuple:
    """Yield successive n-sized chunks from iterable.
    :param iterable: Iterable to chunk
    :param size: Chunks size
    :yield: Chunk in tuple format
    """
    it = iter(iterable)
    while True:
        chunk = tuple(itertools.islice(it, size))
        if not chunk:
            break
        yield chunk
