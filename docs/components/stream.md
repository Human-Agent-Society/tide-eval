# Stream tooling

`tide/stream.py` — the state machinery stream scripts need. Note what is
*not* here: a stream runner. Protocols are Python scripts by design (feedback
policies, probe sampling, and orderings are natural `if`s and `for`s; a DSL
would grow fields forever). The litmus test of tide's decoupling is that any
stream is writable as a **pure caller of `Lab`** — if you find yourself
needing a core change to express a protocol, that's a design bug; file it.

## StateDir — the single crossing channel

A git-versioned folder. In a stream, **this is the only thing that crosses
episode boundaries.**

```python
state = StateDir("runs/exp/state")
ref = state.snapshot("phase 3")  # commit → ref (idempotent if unchanged)
old = state.materialize(ref)  # historical version in a FRESH dir
state.refs()  # all snapshots, oldest first
state.diff(ref_a, ref_b)  # the audit trail: what did it learn?
```

Rules:

- **Probe against `materialize()`d copies, never the live folder** — probing
  must not mutate evolving state, and historical re-probes (matrix cells)
  need old versions on demand.
- Snapshot **after every learning episode**, so every stored row can carry a
  `version` tag that is actually reproducible.
- The folder maps into episodes via Harbor's existing channels (skills
  injection / mounts) — environments stay disposable; state never lives in a
  container.

## WeightPlane — when the state is weights

```python
class WeightPlane(Protocol):
    def snapshot(self) -> str: ...  # freeze → durable version ref
    def serve(self, ref: str) -> str: ...  # ref → OpenAI-compatible base URL
```

Two methods are the *entire* contract with any serving/training stack.
`StaticWeightPlane` (a model that never learns) is the reference
implementation and the standard fresh-control arm. reef's implementation
lives on the reef side (see `examples/reef_weightplane.py`); tide never
imports it.

Discipline for asynchronous training: **a probe battery pins the ref it
started with** — pass the ref into every `serve()` call for that battery, so
a mid-battery publish can't dirty the matrix.

## How to modify

- **New file-state backend** (S3, DVC): match StateDir's four methods;
  scripts don't care what's underneath.
- **New weight stack**: implement the two methods; nothing else changes.
- **Common protocol helpers**: if the same loop shape appears in ≥2 real
  scripts, promote it here — that's the abstraction-earning rule this repo
  is built on.
