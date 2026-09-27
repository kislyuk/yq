# Agent Notes

## Python coding style

- Do not use `getattr()` in code you write or change. Use direct attribute access and explicit type checks where needed; use dictionary lookups for genuinely dynamic keyed values.

## Parsing

- Never roll your own parser or pre-parser for command-line options or data formats such as JSON. Use established parsing libraries and the package's existing conventions; extend or configure those parsers instead of replacing them.
- Do not duplicate tokenization, syntax validation, or syntax-based document-boundary detection, or emulate incremental parsing by repeatedly parsing incomplete input. Custom parsing makes APIs brittle and the system harder to maintain.
- If an established parser cannot meet the requirements, explain the limitation and propose a supported library or protocol change. Do not work around it with ad hoc parsing logic.

## Testing

- On Windows/WSL, run the unit suite with `TMPDIR=/tmp python test/test.py` so tests that reopen `/dev/fd/N` temporary files work reliably.
- CLI errors must produce concise diagnostics and exit statuses, never Python tracebacks, including on interrupts and during shutdown.

## YAML streaming

- Benchmark parsing and I/O changes before accepting them. Stop and reevaluate changes that regress performance.
- Preserve leading marker lookahead. Mirroring the presence or absence of an explicit leading `---` in the input stream is an essential usability feature. Do not remove the lookahead or switch to unconditional leading markers to simplify streaming.
- No temporary files or disk-backed spooling may be used by yq, xq, or tomlq, including for lookahead or in-place editing.
- Do not attempt restoration or rollback after a failed or interrupted in-place write. Stop writing and report the failure.
- Input and output streams, including FIFOs, must work without seeking. Only in-place editing may seek its target file. Flush output after each emitted document.
- When converting jq output to YAML/XML/TOML, enforce compact, uncolored JSON with newline terminators and unbuffered output. Discard conflicting jq output flags only in these modes; preserve them for direct jq output.
- Read complete JSON records with native buffered line APIs and decode each record once using the standard library. Do not implement a custom pre-parser or repeatedly decode incomplete documents.
