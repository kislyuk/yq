from __future__ import annotations

import base64
import re
from dataclasses import dataclass
from typing import Any, cast

import yaml
from yaml.emitter import Emitter
from yaml.events import (
    AliasEvent,
    CollectionStartEvent,
    MappingEndEvent,
    ScalarEvent,
    SequenceEndEvent,
)
from yaml.serializer import Serializer

COMMENT_PLACEMENT_BEFORE = "before"
COMMENT_PLACEMENT_INLINE = "inline"

yaml_value_comment_annotation_re = re.compile(r"^__yq_comment_(?P<placement>before|inline)_(?P<key>.+)__$")
yaml_item_comment_annotation_re = re.compile(
    r"^__yq_comment_(?P<placement>before|inline)_(?P<key>\d+)_(?P<value>.+)__$"
)


@dataclass
class YamlComment:
    value: str
    line: int
    inline: bool
    consumed: bool = False


def encode_comment(value: str) -> str:
    return base64.urlsafe_b64encode(value.encode()).decode().rstrip("=")


def decode_comment(value: str) -> str:
    value += "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value.encode()).decode()


def make_mapping_comment_key(placement: str, key: str) -> str:
    return f"__yq_comment_{placement}_{key}__"


def make_sequence_comment_annotation(placement: str, index: int, value: str) -> str:
    return f"__yq_comment_{placement}_{index}_{encode_comment(value)}__"


def normalize_comment_values(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)]


def consume_comments_for_node(
    loader: CommentPreservingLoader, anchor_node: Any, value_node: Any | None = None
) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {COMMENT_PLACEMENT_BEFORE: [], COMMENT_PLACEMENT_INLINE: []}
    comments = loader.yaml_comments
    if not comments:
        return result

    inline_nodes = [anchor_node]
    if value_node is not None:
        inline_nodes.append(value_node)
    inline_lines = {node.end_mark.line for node in inline_nodes}

    for comment in comments:
        if not comment.consumed and not comment.inline and comment.line < anchor_node.start_mark.line:
            result[COMMENT_PLACEMENT_BEFORE].append(comment.value)
            comment.consumed = True

    for comment in comments:
        if not comment.consumed and comment.inline and comment.line in inline_lines:
            result[COMMENT_PLACEMENT_INLINE].append(comment.value)
            comment.consumed = True

    return result


class CommentPreservingLoader(yaml.SafeLoader):
    def __init__(self, stream: Any) -> None:
        self.yaml_comments: list[YamlComment] = []
        self.yaml_document_constructed = False
        super().__init__(stream)

    def parse_document_start(self) -> Any:
        # yq constructs each document before advancing to the next one. Clear
        # its comments before the parser scans the next document's leading comments.
        if self.yaml_document_constructed:
            self.yaml_comments.clear()
            self.yaml_document_constructed = False
        return super().parse_document_start()

    def construct_document(self, node: Any) -> Any:
        document = super().construct_document(node)
        self.yaml_document_constructed = True
        return document

    def scan_to_next_token(self) -> None:
        if self.index == 0 and self.peek() == "\ufeff":
            self.forward()
        found = False
        while not found:
            while self.peek() == " ":
                self.forward()
            if self.peek() == "#":
                mark = self.get_mark()
                inline = not self.allow_simple_key
                self.forward()
                chunks = []
                while self.peek() not in "\0\r\n\x85\u2028\u2029":
                    chunks.append(self.peek())
                    self.forward()
                self.yaml_comments.append(YamlComment(value="".join(chunks), line=mark.line, inline=inline))
            if self.scan_line_break():
                if not self.flow_level:
                    self.allow_simple_key = True
            else:
                found = True


class CommentPreservingDumperMixin(Emitter):
    def serialize_node(self, node: Any, parent: Any, index: Any) -> None:
        before = node.yaml_comment_before if hasattr(node, "yaml_comment_before") else None
        inline = node.yaml_comment_inline if hasattr(node, "yaml_comment_inline") else None
        if not (before or inline):
            Serializer.serialize_node(cast(Serializer, self), node, parent, index)
            return

        dumper = cast(Any, self)
        original_emit = dumper.emit
        attached = False

        def emit_with_comments(event: Any) -> None:
            nonlocal attached
            if not attached and isinstance(event, (AliasEvent, CollectionStartEvent, ScalarEvent)):
                comment_event = cast(Any, event)
                if before:
                    comment_event.yaml_comment_before = before
                if inline:
                    comment_event.yaml_comment_inline = inline
                attached = True
            original_emit(event)

        dumper.emit = emit_with_comments
        try:
            Serializer.serialize_node(cast(Serializer, self), node, parent, index)
        finally:
            dumper.emit = original_emit

    def expect_node(
        self, root: bool = False, sequence: bool = False, mapping: bool = False, simple_key: bool = False
    ) -> Any:
        if not (root or simple_key) and isinstance(self.event, CollectionStartEvent):
            if hasattr(self.event, "yaml_comment_inline"):
                self.write_inline_comments(self.event.yaml_comment_inline)
        return Emitter.expect_node(self, root=root, sequence=sequence, mapping=mapping, simple_key=simple_key)

    def expect_block_mapping_key(self, first: bool = False) -> Any:
        if not first and isinstance(self.event, MappingEndEvent):
            return Emitter.expect_block_mapping_key(self, first=first)
        if self.event is not None and hasattr(self.event, "yaml_comment_before"):
            self.write_comments_before(self.event.yaml_comment_before)
        return Emitter.expect_block_mapping_key(self, first=first)

    def expect_block_sequence_item(self, first: bool = False) -> Any:
        if not first and isinstance(self.event, SequenceEndEvent):
            return Emitter.expect_block_sequence_item(self, first=first)
        if self.event is not None and hasattr(self.event, "yaml_comment_before"):
            self.write_comments_before(self.event.yaml_comment_before)
        return Emitter.expect_block_sequence_item(self, first=first)

    def process_scalar(self) -> None:
        Emitter.process_scalar(self)
        if self.event is not None and hasattr(self.event, "yaml_comment_inline"):
            self.write_inline_comments(self.event.yaml_comment_inline)

    def write_comments_before(self, comments: list[str] | None) -> None:
        for comment in comments or []:
            self.write_indent()
            self.write_comment(comment)
            self.write_line_break()

    def write_inline_comments(self, comments: list[str] | None) -> None:
        if not comments:
            return
        self.write_comment(comments[0])
        for comment in comments[1:]:
            self.write_line_break()
            self.write_indent()
            self.write_comment(comment)

    def write_comment(self, comment: str) -> None:
        emitter = cast(Any, self)
        if comment and not comment.startswith(" "):
            comment = " " + comment
        data: Any = "#" + comment
        if emitter.column and not emitter.whitespace:
            data = " " + data
        emitter.whitespace = False
        emitter.indention = False
        emitter.column += len(data)
        emitter.open_ended = False
        if emitter.encoding:
            data = data.encode(emitter.encoding)
        emitter.stream.write(data)
