# FrontierCS 2.0

240 open-ended CS problems ([FrontierCS/Frontier-CS](https://github.com/FrontierCS/Frontier-CS),
MIT): Erdős-style constructions, BBOPlace placement, NP-hard variants —
continuous scores, expert evaluators, in-task `submit.sh` self-scoring
(exactly tide's untrusted-self-eval convention).

All 20 tasks of the 2.0 track are committed in this folder, generated
verbatim by their official Harbor adapter — including four GPU kernel
optimization tasks (kmeans / knn / ivf-pq / dbscan) whose judge sidecars
demonstrate the compose-overlay wiring from
[docs/components/tasks.md](../../docs/components/tasks.md). Run the demo:

```bash
tide run frontier-cs/frontier-cs-2-0-erdos-demo --agent oracle
tide run frontier-cs/frontier-cs-2-0-erdos-demo --agent claude-code --model anthropic/claude-opus-5
```

Generate any of the other problems into this folder:

```bash
python tasks/frontier-cs/fetch.py                      # list problem ids
python tasks/frontier-cs/fetch.py erdos_unit_distance
```
