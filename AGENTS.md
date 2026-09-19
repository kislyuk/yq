# Agent Notes

## Testing

- On Windows/WSL, run the unit suite with `TMPDIR=/tmp python test/test.py` so tests that reopen `/dev/fd/N` temporary files work reliably.

## YAML streaming

- Preserve leading marker lookahead. Mirroring the presence or absence of an explicit leading `---` in the input stream is an essential usability feature. Do not remove the lookahead or switch to unconditional leading markers to simplify streaming.
