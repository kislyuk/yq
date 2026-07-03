from datetime import date, datetime, time

import tomlkit
from tomlkit.items import AoT, Array, Bool, Float, InlineTable, Integer, String, Table
from tomlkit.toml_document import TOMLDocument

TOML_META_KEY = "__tomlq_meta__"


def tomlkit_to_json(value, use_annotations=False):
    if isinstance(value, (TOMLDocument, Table, InlineTable)):
        result = {}
        for key, item in value.items():
            result[key] = tomlkit_to_json(item, use_annotations=use_annotations)
        if use_annotations:
            result[TOML_META_KEY] = {"source": _toml_fragment(value), "type": type(value).__name__}
        return result
    if isinstance(value, AoT):
        return [tomlkit_to_json(item, use_annotations=use_annotations) for item in value]
    if isinstance(value, Array):
        return [tomlkit_to_json(item, use_annotations=use_annotations) for item in value]
    if hasattr(value, "unwrap"):
        return value.unwrap()
    return value


def tomlkit_from_json(value):
    if not isinstance(value, dict):
        return value

    meta = value.get(TOML_META_KEY)
    if isinstance(meta, dict) and isinstance(meta.get("source"), str):
        try:
            doc = tomlkit.parse(meta["source"])
        except Exception:
            doc = tomlkit.document()
    else:
        doc = tomlkit.document()

    _apply_mapping(doc, value)
    return doc


def _toml_fragment(value):
    if isinstance(value, InlineTable):
        return tomlkit.dumps(value.unwrap())
    return value.as_string()


def _plain_items(mapping):
    return [(key, value) for key, value in mapping.items() if key != TOML_META_KEY]


def _apply_mapping(container, data):
    desired = {key for key, _ in _plain_items(data)}
    for key in list(container.keys()):
        if key not in desired:
            del container[key]

    for key, value in _plain_items(data):
        if key in container:
            current = container[key]
            replacement = _overlay_item(current, value)
            if replacement is not current:
                container[key] = replacement
        else:
            container[key] = _new_item(value)

    return container


def _overlay_item(current, value):
    if isinstance(value, dict):
        if isinstance(current, (Table, InlineTable, TOMLDocument)):
            return _apply_mapping(current, value)
        return tomlkit_from_json(value)

    if isinstance(value, list):
        if isinstance(current, AoT) and all(isinstance(item, dict) for item in value):
            _apply_aot(current, value)
            return current
        if isinstance(current, Array):
            _apply_array(current, value)
            return current
        return [_new_plain_value(item) for item in value]

    if _json_value(current) == value:
        return current

    return _replacement_item(current, value)


def _apply_array(array, values):
    common_len = min(len(array), len(values))
    for index in range(common_len):
        replacement = _overlay_item(array[index], values[index])
        if replacement is not array[index]:
            array[index] = replacement

    while len(array) > len(values):
        del array[-1]

    for value in values[common_len:]:
        array.append(_new_plain_value(value))


def _apply_aot(aot, values):
    common_len = min(len(aot), len(values))
    for index in range(common_len):
        _apply_mapping(aot[index], values[index])

    while len(aot) > len(values):
        del aot[-1]

    for value in values[common_len:]:
        table = tomlkit.table()
        _apply_mapping(table, value)
        aot.append(table)


def _replacement_item(current, value):
    if isinstance(current, String) and isinstance(value, str):
        try:
            item = String.from_raw(value, current.type)
        except Exception:
            item = tomlkit.item(value)
    elif isinstance(current, Integer) and isinstance(value, int) and not isinstance(value, bool):
        item = tomlkit.integer(value)
    elif isinstance(current, Float) and isinstance(value, (float, int)) and not isinstance(value, bool):
        item = tomlkit.float_(value)
    elif isinstance(current, Bool) and isinstance(value, bool):
        item = tomlkit.boolean(value)
    else:
        item = tomlkit.item(_new_plain_value(value))

    _copy_trivia(current, item)
    return item


def _copy_trivia(source, target):
    if hasattr(source, "trivia") and hasattr(target, "trivia"):
        target.trivia.indent = source.trivia.indent
        target.trivia.comment_ws = source.trivia.comment_ws
        target.trivia.comment = source.trivia.comment
        target.trivia.trail = source.trivia.trail


def _new_item(value):
    value = _new_plain_value(value)
    if isinstance(value, dict):
        table = tomlkit.table()
        _apply_mapping(table, value)
        return table
    if isinstance(value, list):
        return [_new_plain_value(item) for item in value]
    return value


def _new_plain_value(value):
    if isinstance(value, dict):
        return {key: _new_plain_value(item) for key, item in _plain_items(value)}
    if isinstance(value, list):
        return [_new_plain_value(item) for item in value]
    return value


def _json_value(item):
    if hasattr(item, "unwrap"):
        value = item.unwrap()
    else:
        value = item
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    return value
