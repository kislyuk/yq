from __future__ import annotations

import io
import json
import os
import select
import stat
from collections import deque

import yaml


class JSONInputStreamWrapper:
    """Read the complete JSON records emitted by jq's compact output mode."""

    def __init__(self, stream, decoder):
        self.stream = stream
        self.decoder = decoder

    def __iter__(self):
        return self

    def has_next(self):
        return bool(self.stream.peek(1))

    def __next__(self):
        text = self.stream.readline().decode("utf-8")
        if not text:
            raise StopIteration
        if not text.endswith("\n"):
            # A terminated record distinguishes a complete number from a prefix
            # left behind when jq is interrupted during serialization.
            raise json.JSONDecodeError("Missing newline after jq output", text, len(text))
        return self.decoder.decode(text)


class YAMLInputStreamWrapper:
    """Replay only the prefix consumed while inspecting the leading marker."""

    def __init__(self, stream, flush=None):
        self.stream = stream
        self.flush = flush
        try:
            self.name = stream.name
        except AttributeError:
            self.name = "<file>"
        self.prefix: deque[str | bytes] = deque()
        self.offset = 0
        self.recording = False

    def read(self, size):
        if self.prefix and not self.recording:
            text = self.prefix[0][self.offset : self.offset + size]
            self.offset += len(text)
            if self.offset == len(self.prefix[0]):
                self.prefix.popleft()
                self.offset = 0
            return text
        # Deliver completed input to jq before a read can wait for more data.
        # Between reads, TextIOWrapper can batch writes from small documents.
        if self.flush is not None:
            self.flush()
        text = self.stream.read(size)
        if self.recording and text:
            self.prefix.append(text)
        return text

    def read_explicit_yaml_start(self, loader_class):
        # Use a separate parser because the C and Python composers consume start
        # events differently. Replay their bounded read-ahead even on nonseekable input.
        self.recording = True
        events = yaml.parse(self, Loader=loader_class)
        try:
            next(events)  # StreamStartEvent
            event = next(events)
            return isinstance(event, yaml.events.DocumentStartEvent) and event.explicit
        finally:
            events.close()
            self.recording = False


class InputBytesStreamWrapper(io.RawIOBase):
    """Wait for readable input while checking whether jq has already exited."""

    def __init__(self, stream, jq):
        self.source = stream
        self.stream = stream.buffer
        self.jq = jq
        self.name = stream.name
        self.wait_for_input = os.name == "posix" and not stat.S_ISREG(os.fstat(stream.fileno()).st_mode)

    def readable(self):
        return True

    def read(self, size=-1):
        if size == 0:
            return b""
        if size < 0:
            return self.readall()
        while True:
            # The main thread waits for jq before joining the input worker.
            if self.jq is not None and self.jq.returncode is not None:
                raise BrokenPipeError
            if not self.wait_for_input or select.select([self.stream], [], [], 0.1)[0]:
                # read1 returns available bytes without waiting to fill size.
                return self.stream.read1(size)

    read1 = read


def wrap_input_stream(stream, jq):
    return io.TextIOWrapper(
        InputBytesStreamWrapper(stream, jq), encoding=stream.encoding, errors=stream.errors, newline=""
    )
