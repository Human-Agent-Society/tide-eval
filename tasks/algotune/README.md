# AlgoTune

154 "speed up this code" tasks from
[oripress/AlgoTune](https://github.com/oripress/AlgoTune) (MIT): each
gives a reference implementation, and the score is your solver's speedup
over it — measured with an interleaved timing protocol, with a mercy
floor of 1.0 for invalid or slower solutions.

## What we changed, and why

The [official Harbor adapter](https://github.com/laude-institute/harbor/tree/main/adapters/algotune)
times your solver **once, at the end** (100 instances × 10 repeats): one
final number, no record of how you got there. `fetch.py` re-shapes its
output into the judge protocol:

- **every submission gets session feedback** — a light run of the same
  interleaved protocol (5 instances × 3 repeats), so a judge-timed
  score-over-time curve exists;
- **the final judge re-times the best submission once with the official
  protocol** (100 × 10, upstream's exact scoring and mercy rules) — the
  reported number means the same thing as upstream's;
- **a submission budget** (100) bounds the judge's timing compute.

The official metric is untouched; what changes is that the process
becomes measurable. `tests/test_algotune_converter.py` runs a converted
task through the local judge end to end.

## Usage

```bash
# 1. generate task dirs with the official adapter (see its README), then:
python tasks/algotune/fetch.py <adapter-output>/algotune__psd_cone_projection

# 2. run like any other task:
tide run algotune/algotune__psd_cone_projection --agent claude-code --model ...
```

Converted folders stay local (gitignored) — the official adapter is the
source of truth for task content. The plain registry route still works
too, yielding upstream's single final score with no submission log:

```bash
tide run algotune/<registry-task-id> --agent <a>
```

One upstream caveat carries over: timing is hardware-sensitive, so
compare runs from the same machine.
