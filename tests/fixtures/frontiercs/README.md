# Frontier-CS fixture

`frontier-cs-2-0-erdos-demo/` was generated verbatim by the official
Frontier-CS 2.0 → Harbor adapter
([FrontierCS/Frontier-CS](https://github.com/FrontierCS/Frontier-CS), MIT):

```bash
PYTHONPATH=adapters/frontier-cs-2.0/src python -m frontier_cs_2_0.main \
    --source . --output-dir <here> --task-ids erdos_demo --overwrite
```

It pins tide's claim that FrontierCS exports run unchanged: the test suite
validates it under Harbor's `TaskConfig` and it is directly runnable with
`lab.run(<this dir>, agent)`.
