import re
from typing import Any, Dict, List

import yaml

from .loader import hash_key, set_yaml_grammar
from .yaml_support import (
    CommentPreservingDumperMixin,
    decode_comment,
    normalize_comment_values,
    yaml_item_comment_annotation_re,
    yaml_value_comment_annotation_re,
)

# try:
#     from yaml import CSafeDumper as default_dumper
# except ImportError:
#     from yaml import SafeDumper as default_dumper


class OrderedIndentlessDumper(yaml.SafeDumper):
    pass


class OrderedDumper(yaml.SafeDumper):
    def increase_indent(self, flow=False, indentless=False):
        return super(OrderedDumper, self).increase_indent(flow, False)

    def ignore_aliases(self, data):
        return True


class OrderedIndentlessCommentDumper(CommentPreservingDumperMixin, OrderedIndentlessDumper):
    pass


class OrderedCommentDumper(CommentPreservingDumperMixin, OrderedDumper):
    pass


yaml_value_annotation_re = re.compile(r"^__yq_(?P<type>tag|style)_(?P<key>.+)__$")
yaml_item_annotation_re = re.compile(r"^__yq_(?P<type>tag|style)_(?P<key>\d+)_(?P<value>.+)__$")


def get_dumper(use_annotations=False, indentless=False, grammar_version="1.1"):
    # if not (use_annotations or indentless):
    #     return default_dumper

    def represent_dict(dumper, data):
        pairs, custom_styles, custom_tags = [], {}, {}
        custom_comments: Dict[str, Dict[str, List[str]]] = {}
        for k, v in data.items():
            if use_annotations and isinstance(k, str):
                if k == "__yq_alias__":
                    continue
                comment_annotation = yaml_value_comment_annotation_re.match(k)
                if comment_annotation:
                    comment_key = comment_annotation.group("key")
                    placement = comment_annotation.group("placement")
                    custom_comments.setdefault(comment_key, {}).setdefault(placement, []).extend(
                        normalize_comment_values(v)
                    )
                    continue
                value_annotation = yaml_value_annotation_re.match(k)
                if value_annotation and value_annotation.group("type") == "style":
                    custom_styles[value_annotation.group("key")] = v
                    continue
                elif value_annotation and value_annotation.group("type") == "tag":
                    custom_tags[value_annotation.group("key")] = v
                    continue
            pairs.append((k, v))
        mapping = dumper.represent_mapping("tag:yaml.org,2002:map", pairs)
        if use_annotations:
            for k, v in mapping.value:
                hashed_key = hash_key(k.value)
                comments = custom_comments.get(hashed_key, {})
                if "before" in comments:
                    k.yaml_comment_before = comments["before"]
                if "inline" in comments:
                    v.yaml_comment_inline = comments["inline"]
                if hashed_key in custom_styles:
                    if isinstance(v, yaml.nodes.ScalarNode):
                        v.style = custom_styles[hashed_key]
                    elif custom_styles[hashed_key] == "flow":
                        v.flow_style = True
                if hashed_key in custom_tags:
                    v.tag = custom_tags[hashed_key]
        return mapping

    def represent_list(dumper, data):
        raw_list, custom_styles, custom_tags = [], {}, {}
        custom_comments: Dict[str, Dict[str, List[str]]] = {}
        for v in data:
            if use_annotations and isinstance(v, str):
                comment_annotation = yaml_item_comment_annotation_re.match(v)
                if comment_annotation:
                    comment_key = comment_annotation.group("key")
                    placement = comment_annotation.group("placement")
                    comment = decode_comment(comment_annotation.group("value"))
                    custom_comments.setdefault(comment_key, {}).setdefault(placement, []).append(comment)
                    continue
                annotation = yaml_item_annotation_re.match(v)
                if annotation and annotation.group("type") == "style":
                    custom_styles[annotation.group("key")] = annotation.group("value")
                    continue
                elif annotation and annotation.group("type") == "tag":
                    custom_tags[annotation.group("key")] = annotation.group("value")
                    continue
            raw_list.append(v)
        sequence = dumper.represent_list(raw_list)
        if use_annotations:
            for i, v in enumerate(sequence.value):
                item_key = str(i)
                comments = custom_comments.get(item_key, {})
                if "before" in comments:
                    v.yaml_comment_before = comments["before"]
                if "inline" in comments:
                    v.yaml_comment_inline = comments["inline"]
                if item_key in custom_styles:
                    if isinstance(v, yaml.nodes.ScalarNode):
                        v.style = custom_styles[item_key]
                    elif custom_styles[item_key] == "flow":
                        v.flow_style = True
                if item_key in custom_tags:
                    v.tag = custom_tags[item_key]
        return sequence

    dumper: Any
    if use_annotations:
        dumper = OrderedIndentlessCommentDumper if indentless else OrderedCommentDumper
    else:
        dumper = OrderedIndentlessDumper if indentless else OrderedDumper
    dumper.add_representer(dict, represent_dict)
    dumper.add_representer(list, represent_list)
    set_yaml_grammar(dumper, grammar_version=grammar_version)
    return dumper
