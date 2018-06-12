from collections.abc import Iterator, Mapping
from datetime        import datetime
from enum            import Enum

def for_json(obj):
    # For use as the `default` argument to `json.dump`
    if hasattr(obj, 'for_json'):
        return obj.for_json()
    elif hasattr(obj, 'as_dict'):
        return obj.as_dict()
    elif hasattr(obj, '_asdict'):
        return obj._asdict()
    elif isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, Mapping):
        return dict(obj)
    elif isinstance(obj, (Iterator, tuple, set, frozenset)):
        ### Sort sets and frozensets?
        return list(obj)
    elif isinstance(obj, Enum):
        return str(obj)
    else:
        try:
            data = vars(obj).copy()
        except TypeError:
            data = {"__repr__": repr(obj)}
        data["__class__"] = type(obj).__name__
        return data
