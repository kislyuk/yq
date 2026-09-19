# Agent Notes

## Python coding style

- Do not use `getattr()` in code you write or change. Use direct attribute access and explicit type checks where needed; use dictionary lookups for genuinely dynamic keyed values.

## Testing

- On Windows/WSL, run the unit suite with `TMPDIR=/tmp python test/test.py` so tests that reopen `/dev/fd/N` temporary files work reliably.

## YAML streaming

- Preserve leading marker lookahead. Mirroring the presence or absence of an explicit leading `---` in the input stream is an essential usability feature. Do not remove the lookahead or switch to unconditional leading markers to simplify streaming.
