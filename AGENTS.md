# Agent Notes

## Testing

- On Windows/WSL, run the unit suite with `TMPDIR=/tmp python test/test.py` so tests that reopen `/dev/fd/N` temporary files work reliably.
