# FrontierCS 2.0

240 open-ended CS problems ([FrontierCS/Frontier-CS](https://github.com/FrontierCS/Frontier-CS),
MIT): Erdős-style constructions, BBOPlace placement, NP-hard variants —
continuous scores, expert evaluators, in-task `submit.sh` self-scoring
(exactly tide's untrusted-self-eval convention).

`frontier-cs-2-0-erdos-demo/` is vendored as a working sample, generated
verbatim by their official Harbor adapter. Run it:

```bash
python examples/run_frontiercs.py                      # oracle
python examples/run_frontiercs.py --agent claude-code --model anthropic/claude-opus-5
```

Generate any of the other problems into this folder:

```bash
python tasks/frontier-cs/fetch.py                      # list problem ids
python tasks/frontier-cs/fetch.py erdos_unit_distance
```
