# Lab & store

`tide/lab.py` · `tide/store.py` — **the frozen surface**. Everything else in
tide (and everything users build) depends on exactly two things: the signature
of `Lab.run` / `Lab.probe`, and the results table. Change anything here as an
addition, never a mutation.

## What it does

- `Lab(root, executor=…, prober=…, concurrency=…)` — a Lab **is a
  directory**: `results.sqlite` plus (for the Harbor executor) `trials/`.
- `run(task, agent, *, tags, key, **overrides) → Row` — one episode.
  Checks the idempotency key, bounds concurrency with a semaphore, executes,
  stores one `episode` row plus `key#t<i>` `trace` rows for any ingested
  score trajectory.
- `probe(probe, model, *, tags, key) → Row` — one direct-inference probe.
- `df(kind=None)` — the store as pandas, tags/rewards expanded to columns.

## The row model

| kind | meaning | key shape |
|---|---|---|
| `episode` | trusted, verifier-backed score | `<key>` |
| `trace` | untrusted intermediate score from inside an episode | `<key>#t<i>` |
| `probe` | direct-inference measurement | `probe:<digest>` or yours |

Column collisions in `df()` are resolved with prefixes (`tag_`, `reward_`) so
every column stays 1-dimensional — base columns win over tags, tags over
rewards.

## Invariants (do not break)

1. **Append-only.** The only sanctioned delete is `delete_prefix("<key>#")` —
   clearing a retried episode's partial trace before re-running.
2. **Idempotency is exact.** The auto-key digests (task, agent, tags,
   overrides); any semantic change to what "the same episode" means is a
   breaking change for every user's resume behavior.
3. **Raw rewards only.** Normalization lives in `tide/metrics.py`, applied at
   query time.
4. **Duplicate keys raise.** A silent overwrite would corrupt resumes; loud
   beats lenient here.

## How to modify

- **New row kind** (e.g. `audit` for re-graded trajectories): add the kind
  string, write rows with a distinct key shape, filter with `df(kind=…)`.
  No schema change needed.
- **New key policy**: pass `key=` explicitly from your script — do not change
  `_default_key`.
- **New backend**: that's an executor, not a Lab change — see
  [executors.md](executors.md).
- **Schema additions**: new columns are fine (idempotency: old rows read as
  NULL); renames/type changes are forbidden.
