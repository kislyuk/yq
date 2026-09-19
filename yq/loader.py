from __future__ import annotations

import re
from base64 import b64encode
from hashlib import sha224
from typing import Any, Pattern, TypedDict

import yaml
from yaml.tokens import (
    AliasToken,
    AnchorToken,
    FlowMappingEndToken,
    FlowMappingStartToken,
    KeyToken,
    ScalarToken,
    ValueToken,
)

from .yaml_support import (
    COMMENT_PLACEMENT_BEFORE,
    COMMENT_PLACEMENT_INLINE,
    CommentPreservingLoader,
    consume_comments_for_node,
    make_mapping_comment_key,
    make_sequence_comment_annotation,
)

default_loader: Any = getattr(yaml, "CSafeLoader", yaml.SafeLoader)


class ResolverSpec(TypedDict):
    tag: str
    regexp: Pattern[str]
    start_chars: list[str]


# Note the 1.1 resolver is modified from the default and only safe for use in dumping, not loading.
core_resolvers: dict[str, list[ResolverSpec]] = {
    "1.1": [
        {
            "tag": "tag:yaml.org,2002:bool",
            "regexp": re.compile(
                r"""^(?:yes|Yes|YES|no|No|NO
            |true|True|TRUE|false|False|FALSE
            |on|On|ON|off|Off|OFF)$""",
                re.VERBOSE,
            ),
            "start_chars": list("yYnNtTfFoO"),
        },
        {
            "tag": "tag:yaml.org,2002:float",
            "regexp": re.compile(
                r"""^(?:[-+]?(?:[0-9][0-9_]*)\.[0-9_]*(?:[eE][-+]?[0-9]+)?
            |[-+]?[0-9][0-9_]*(?:[eE][-+]?[0-9]+)
            |\.[0-9_]+(?:[eE][-+]?[0-9]+)?
            |[-+]?[0-9][0-9_]*(?::[0-5]?[0-9])+\.[0-9_]*
            |[-+]?\.(?:inf|Inf|INF)
            |\.(?:nan|NaN|NAN))$""",
                re.VERBOSE,
            ),
            "start_chars": list("-+0123456789."),
        },
        {
            "tag": "tag:yaml.org,2002:int",
            # Line 2 of regexp modified to match all decimal digits, not just 0-7, to induce quoting of string scalars
            "regexp": re.compile(
                r"""^(?:[-+]?0b[0-1_]+
            |[-+]?0o[0-7]+
            |[-+]?0[0-9_]+
            |[-+]?(?:0|[1-9][0-9_]*)
            |[-+]?0x[0-9a-fA-F_]+
            |[-+]?[1-9][0-9_]*(?::[0-5]?[0-9])+)$""",
                re.VERBOSE,
            ),
            "start_chars": list("-+0123456789"),
        },
        {
            "tag": "tag:yaml.org,2002:null",
            "regexp": re.compile(
                r"""^(?: ~
            |null|Null|NULL
            | )$""",
                re.VERBOSE,
            ),
            "start_chars": ["~", "n", "N", ""],
        },
        {
            "tag": "tag:yaml.org,2002:timestamp",
            "regexp": re.compile(
                r"""^(?:[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]
            |[0-9][0-9][0-9][0-9] -[0-9][0-9]? -[0-9][0-9]?
            (?:[Tt]|[ \t]+)[0-9][0-9]?
            :[0-9][0-9] :[0-9][0-9] (?:\.[0-9]*)?
            (?:[ \t]*(?:Z|[-+][0-9][0-9]?(?::[0-9][0-9])?))?)$""",
                re.VERBOSE,
            ),
            "start_chars": list("0123456789"),
        },
        {"tag": "tag:yaml.org,2002:value", "regexp": re.compile(r"^(?:=)$"), "start_chars": ["="]},
    ],
    "1.2": [
        {
            "tag": "tag:yaml.org,2002:bool",
            "regexp": re.compile(r"^(?:|true|True|TRUE|false|False|FALSE)$", re.VERBOSE),
            "start_chars": list("tTfF"),
        },
        {
            "tag": "tag:yaml.org,2002:int",
            "regexp": re.compile(r"^(?:|0o[0-7]+|[-+]?(?:[0-9]+)|0x[0-9a-fA-F]+)$", re.VERBOSE),
            "start_chars": list("-+0123456789"),
        },
        {
            "tag": "tag:yaml.org,2002:float",
            "regexp": re.compile(
                r"^(?:[-+]?(?:\.[0-9]+|[0-9]+(\.[0-9]*)?)(?:[eE][-+]?[0-9]+)?|[-+]?\.(?:inf|Inf|INF)|\.(?:nan|NaN|NAN))$",
                re.VERBOSE,
            ),
            "start_chars": list("-+0123456789."),
        },
        {
            "tag": "tag:yaml.org,2002:null",
            "regexp": re.compile(r"^(?:~||null|Null|NULL)$", re.VERBOSE),
            "start_chars": ["~", "n", "N", ""],
        },
    ],
}

merge_resolver: ResolverSpec = {
    "tag": "tag:yaml.org,2002:merge",
    "regexp": re.compile(r"^(?:<<)$"),
    "start_chars": ["<"],
}


def set_yaml_grammar(resolver, grammar_version="1.2", expand_merge_keys=True):
    if grammar_version not in core_resolvers:
        raise ValueError(f"Unknown grammar version {grammar_version}")
    resolvers = list(core_resolvers[grammar_version])
    if expand_merge_keys:
        resolvers.append(merge_resolver)
    resolver.yaml_implicit_resolvers = {}
    for r in resolvers:
        for start_char in r["start_chars"]:
            resolver.yaml_implicit_resolvers.setdefault(start_char, [])
            resolver.yaml_implicit_resolvers[start_char].append((r["tag"], r["regexp"]))


def construct_yaml_1_2_int(loader, node):
    value = loader.construct_scalar(node).replace("_", "")
    sign = +1
    if value[0] == "-":
        sign = -1
    if value[0] in "+-":
        value = value[1:]
    if value.startswith("0o"):
        return sign * int(value, 0)
    if value.startswith("0x"):
        return sign * int(value, 0)
    return sign * int(value, 10)


def hash_key(key):
    return b64encode(sha224(key.encode() if isinstance(key, str) else key).digest()).decode()


class CustomLoader(yaml.SafeLoader):
    expand_aliases = False

    def emit_yq_kv(self, key, value, original_token):
        marks = {"start_mark": original_token.start_mark, "end_mark": original_token.end_mark}
        self.tokens.append(FlowMappingStartToken(**marks))
        self.tokens.append(KeyToken(**marks))
        self.tokens.append(ScalarToken(value=key, plain=True, **marks))
        self.tokens.append(ValueToken(**marks))
        self.tokens.append(ScalarToken(value=value, plain=True, **marks))
        self.tokens.append(FlowMappingEndToken(**marks))

    def fetch_alias(self):
        if self.expand_aliases:
            return super().fetch_alias()
        self.save_possible_simple_key()
        self.allow_simple_key = False
        alias_token = self.scan_anchor(AliasToken)
        self.emit_yq_kv("__yq_alias__", alias_token.value, original_token=alias_token)

    def fetch_anchor(self):
        if self.expand_aliases:
            return super().fetch_anchor()
        self.save_possible_simple_key()
        self.allow_simple_key = False
        anchor_token = self.scan_anchor(AnchorToken)  # noqa: F841
        # self.emit_yq_kv("__yq_anchor__", anchor_token.value, original_token=anchor_token)


class CommentPreservingCustomLoader(CommentPreservingLoader):
    expand_aliases = False

    def emit_yq_kv(self, key, value, original_token):
        marks = {"start_mark": original_token.start_mark, "end_mark": original_token.end_mark}
        self.tokens.append(FlowMappingStartToken(**marks))
        self.tokens.append(KeyToken(**marks))
        self.tokens.append(ScalarToken(value=key, plain=True, **marks))
        self.tokens.append(ValueToken(**marks))
        self.tokens.append(ScalarToken(value=value, plain=True, **marks))
        self.tokens.append(FlowMappingEndToken(**marks))

    def fetch_alias(self):
        if self.expand_aliases:
            return super().fetch_alias()
        self.save_possible_simple_key()
        self.allow_simple_key = False
        alias_token = self.scan_anchor(AliasToken)
        self.emit_yq_kv("__yq_alias__", alias_token.value, original_token=alias_token)

    def fetch_anchor(self):
        if self.expand_aliases:
            return super().fetch_anchor()
        self.save_possible_simple_key()
        self.allow_simple_key = False
        anchor_token = self.scan_anchor(AnchorToken)  # noqa: F841
        # self.emit_yq_kv("__yq_anchor__", anchor_token.value, original_token=anchor_token)


def get_loader(use_annotations=False, expand_aliases=True, expand_merge_keys=True):
    def construct_sequence(loader, node):
        annotations = []
        for i, v_node in enumerate(node.value):
            if not use_annotations:
                break
            comments = consume_comments_for_node(loader, v_node)
            for comment in comments[COMMENT_PLACEMENT_BEFORE]:
                annotations.append(make_sequence_comment_annotation(COMMENT_PLACEMENT_BEFORE, i, comment))
            for comment in comments[COMMENT_PLACEMENT_INLINE]:
                annotations.append(make_sequence_comment_annotation(COMMENT_PLACEMENT_INLINE, i, comment))
            if v_node.tag and v_node.tag.startswith("!") and not v_node.tag.startswith("!!") and len(v_node.tag) > 1:
                annotations.append(f"__yq_tag_{i}_{v_node.tag}__")
            if isinstance(v_node, yaml.nodes.ScalarNode) and v_node.style:
                annotations.append(f"__yq_style_{i}_{v_node.style}__")
            elif isinstance(v_node, (yaml.nodes.SequenceNode, yaml.nodes.MappingNode)) and v_node.flow_style is True:
                annotations.append("__yq_style_{}_{}__".format(i, "flow"))
        return [loader.construct_object(i) for i in node.value] + annotations

    def construct_mapping(loader, node):
        loader.flatten_mapping(node)  # TODO: is this needed?
        pairs = []
        for k_node, v_node in node.value:
            key = loader.construct_object(k_node)
            value = loader.construct_object(v_node)
            pairs.append((key, value))
            if not use_annotations:
                continue
            comments = consume_comments_for_node(loader, k_node, v_node)
            if not isinstance(key, (str, bytes)):
                continue
            hashed_key = hash_key(key)
            for placement, values in comments.items():
                if values:
                    pairs.append((make_mapping_comment_key(placement, hashed_key), values))
            if v_node.tag and v_node.tag.startswith("!") and not v_node.tag.startswith("!!") and len(v_node.tag) > 1:
                pairs.append((f"__yq_tag_{hashed_key}__", v_node.tag))
            if isinstance(v_node, yaml.nodes.ScalarNode) and v_node.style:
                pairs.append((f"__yq_style_{hashed_key}__", v_node.style))
            elif isinstance(v_node, (yaml.nodes.SequenceNode, yaml.nodes.MappingNode)) and v_node.flow_style is True:
                pairs.append((f"__yq_style_{hashed_key}__", "flow"))
        return dict(pairs)

    def parse_unknown_tags(loader, tag_suffix, node):
        if isinstance(node, yaml.nodes.ScalarNode):
            return loader.construct_scalar(node)
        elif isinstance(node, yaml.nodes.SequenceNode):
            return construct_sequence(loader, node)
        elif isinstance(node, yaml.nodes.MappingNode):
            return construct_mapping(loader, node)

    loader_class: Any
    if use_annotations:
        loader_class = CommentPreservingLoader if expand_aliases else CommentPreservingCustomLoader
    else:
        loader_class = default_loader if expand_aliases else CustomLoader
    loader_class.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, construct_mapping)
    loader_class.add_constructor(yaml.resolver.BaseResolver.DEFAULT_SEQUENCE_TAG, construct_sequence)
    loader_class.add_constructor("tag:yaml.org,2002:int", construct_yaml_1_2_int)
    loader_class.add_multi_constructor("", parse_unknown_tags)
    loader_class.yaml_constructors.pop("tag:yaml.org,2002:binary", None)
    loader_class.yaml_constructors.pop("tag:yaml.org,2002:set", None)
    set_yaml_grammar(loader_class, expand_merge_keys=expand_merge_keys)
    return loader_class
