# String compression

Compress `/app/corpus.txt` (about 9 KB of text) as tightly as you can, by
shipping a **decompressor program plus a payload**.

**Reward = corpus bytes / (decompressor source bytes + payload string bytes).**
zlib gets ≈ 3.5; the corpus has structure worth exploiting for more.

## Output format

Write to `/app/best/solution.json`:

```json
{"decompressor": "<python source>", "payload": "<any string, e.g. base64>"}
```

When graded, your decompressor runs as a Python program with a global
variable `PAYLOAD` holding your payload string; it must print the exact
corpus to stdout (byte-exact, 15 s limit, decompressor ≤ 100 KB).

## Scoring integrity

The trusted grade runs in a clean container where **every copy of the corpus
is deleted before your decompressor executes** — a "decompressor" that reads
the corpus from disk finds nothing and scores 0. It must reconstruct the
text from the payload alone.

## Protocol

- Whenever you improve the ratio, **atomically** rewrite
  `/app/best/solution.json` (temp file + rename); only that file is graded.
- On each improvement, append `{"t": <seconds since start>, "score": <s>}`
  to `/app/best/score_log.jsonl`.
