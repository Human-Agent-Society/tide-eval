# 🌊 tide

[![CI](https://github.com/Human-Agent-Society/tide-eval/actions/workflows/ci.yml/badge.svg)](https://github.com/Human-Agent-Society/tide-eval/actions/workflows/ci.yml)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](pyproject.toml)
[![License](https://img.shields.io/badge/license-Apache--2.0-green.svg)](LICENSE)

**基于 [Harbor](https://github.com/laude-institute/harbor) 任务标准的 autoresearch 评测框架。**

[English](README.md) | **中文**

Autoresearch 任务——AlphaEvolve / OpenEvolve 那一类工作负载——是开放式优化
问题:数小时的预算、连续的分数、一个在过程中给自己打几百次分的 agent。这里没有"通过/不通过",只有*多好、多快*。tide 把这
种形态的评测做扎实:

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/assets/readme-hero-dark.svg">
  <img src="docs/assets/readme-hero-light.svg" alt="The agent scores itself while it searches, but its own scores are not trusted. Its best solution crosses to an isolated verifier, which re-scores it while ignoring what the agent claimed. The trusted score and the agent's own scores land in one table, with score over time as a curve." width="100%">
</picture>

任务是 100% 原生 Harbor 任务(有测试强制保证)。agent 是任何能在容器里工作
的东西——包括你自己的 harness 或方法。

## 为什么不直接用 Harbor?

Harbor 把一件事做得非常好——在一个任务上、以可信的方式给 agent 打一次分——
tide 正是把它当库来做这件事。而 autoresearch 在此之上还需要四样东西,它们就
是 tide 存在的理由:

| 直接用 Harbor | tide |
|---|---|
| 每次 trial 只有一个 reward 数字,agent 的自评曲线丢了 | score log 变成 `trace` 行:anytime 曲线、AUC、到达阈值的时间各是一个查询 |
| 统计只在单个 job 内部(pass@k) | 预算是普通标签,"8 小时比 2 小时多买到多少分"是跨任意 run 集合的一个查询 |
| sweep 崩了从零重来 | 幂等键让重跑自动跳过已完成的 episode——当一个 episode 要跑几小时,这是刚需 |
| 每次运行是一个一次性 job 目录 | 一个 append-only 结果库按周累积,`tide report` 直接读 |

一个诚实的边界:续跑的粒度是 episode。sweep 会从崩溃处继续,但一个跑了一半
的 12 小时 episode 本身要重来。

完整设计——信任模型、任务约定、数据模型、扩展性:
**[docs/design.md](docs/design.md)**(英文)。

## 跑起来

```bash
# PyPI 发布前(见 Roadmap),先从源码安装:
git clone https://github.com/Human-Agent-Society/tide-eval && cd tide-eval
pip install -e ".[harbor]"               # 容器模式需要;仅 --local 和 API 的话 -e . 即可

tide list                                # 有哪些任务可跑
tide run autoresearch --agent oracle     # oracle = 内置 agent,运行每个任务的参考解
tide run edgebench/ann_vector_search_qps --agent codex --budget 2   # 小时
tide report                              # 汇总结果库
```

### 没有 Docker?本地开发,容器验证

`--local` 让你的方法在本机直接对着任务**真实的 scorer 和真实的 grader**运行,
完全不涉及容器:

```bash
tide run autoresearch/circle-packing --local \
  --command "python examples/minimal_harness_search.py" --budget 0.01
```

你的命令读两个环境变量——`$APP`(工作目录,`scorer.py` 和 `best/` 都在里面)
和 `$BUDGET_SEC`——命令结束(或被预算掐掉)后,任务真实的 `grade.py` 给它留
下的产物打分。本地行的 uri 标记为 `local://`,因为没有任何隔离:它用于开发你
的方法,正式报告的数字应来自容器运行。(`python examples/quickstart.py` 和
`--fake` 依然零依赖可用,但它们的分数是模拟的。)

有 Docker 之后,`python examples/run_circle_packing.py` 端到端验证真实流水线
——oracle 必须恰好得 0.75 分——而 `python examples/minimal_harness.py` 是最小
的完整容器 harness:三十行左右的适配器,包着同一个随机搜索循环。

## 用 API

`Lab` 是一个目录。每次 `run` 调用是一个 episode(即一次 Harbor trial),
`df` 把已记录的一切以 pandas DataFrame 返回:

```python
# Lab 基于 asyncio:这段要放在 async 函数或 notebook 里运行。
from tide import Lab, metrics

lab = Lab("runs/exp1")
row = await lab.run(
    "tasks/autoresearch/circle-packing",  # 任意任务目录或 Harbor registry id
    agent={"name": "claude-code", "model_name": "anthropic/claude-opus-5"},
    tags={"budget": 2},  # 自由标签 = 你的结果格式
)
row.rewards  # 可信分数          row.uri → 可审计的 trial 目录

curve = metrics.anytime(lab.df("trace"))  # agent 自己的分数随时间的变化
metrics.auc(curve)  # anytime 分数
metrics.scaling(lab.df("episode"), by=["model"])  # 更多预算买到多少分?
```

重跑任何脚本都会自动续跑。参考:
[lab](docs/components/lab.md) · [metrics](docs/components/metrics.md) ·
[executors](docs/components/executors.md)。

## 接入*你的* agent

无论用哪种方式接入,任务、隔离的 verifier、结果库都完全相同——所以不同方法
的数字可以直接比较:

| 你有什么 | 接入方式 |
|---|---|
| 主流 harness(`claude-code`、`codex`、`aider` 等) | `--agent <名字> --model <模型>`,零代码 |
| 你自己的 harness | 一个 `BaseAgent` 子类,用 `import_path` 引用——可运行的模板:[`examples/minimal_harness.py`](examples/minimal_harness.py) |
| 根本不是 "agent" 的方法(OpenEvolve 式搜索、求解器) | 把最优解保持写在产物路径上,可选地记录自评分数 |

六个第一方任务的容器内契约完全一致,一次接入覆盖全套。唯一不能自带的是
grader。完整指南(`BaseAgent` 骨架 + OpenEvolve 实例):
**[docs/integration.md](docs/integration.md)**。

## 定义新任务

```bash
cp -r tasks/_template tasks/autoresearch/my-task
pytest tests/test_task_suite.py          # 自动被识别——而且直接是绿的
```

模板本身就是一个完整可跑的任务,所以你从全绿开始,一次替换一个
`TODO(task)` 标记的部分(配置、题面、公开 scorer、私有 grader、作弊用例、
参考解)。GPU 任务只多两行配置。指南:
**[docs/components/tasks.md](docs/components/tasks.md)**。

## 任务目录

| Benchmark | 任务数 | 运行方式 |
|---|---|---|
| [第一方任务](tasks/autoresearch) ↓ | 6 | `tide run autoresearch --agent <a>` |
| [EdgeBench](tasks/edgebench) | 51 · 2–12 小时预算 | `tide run edgebench/<task> --budget <h>` |
| [FrontierCS 2.0](tasks/frontier-cs) | 20 · 含 4 个 GPU kernel | `python examples/run_frontiercs.py` |
| [AlgoTune](https://github.com/oripress/AlgoTune) | 154 · 走 Harbor registry | `tide run algotune/<task> --agent <a>` |

每个第一方任务教会这个类别里的一个难点(oracle 在真容器中验证过,作弊用例
在 CI 中持续复测):

| 任务 | 教什么 |
|---|---|
| [`circle-packing`](tasks/autoresearch/circle-packing) | 完整协议;精确算术判分 |
| [`function-minimization`](tasks/autoresearch/function-minimization) | 探索 vs 局部搜索 |
| [`tsp-tour`](tasks/autoresearch/tsp-tour) | 组合搜索、连续信号 |
| [`bin-packing`](tasks/autoresearch/bin-packing) | 精确约束检查 |
| [`symbolic-regression`](tasks/autoresearch/symbolic-regression) | 防过拟合:用 agent 没见过的点判分 |
| [`string-compression`](tasks/autoresearch/string-compression) | 安全地给 agent 提交的代码判分 |

## Roadmap

- [ ] 发布 PyPI(`tide-eval`,名字已预留,尚未发布)
- [ ] GPU 示例任务,在 CI 中以 oracle 把关
- [ ] Harbor 版本升级的安全流程
- [ ] 更多 autoresearch 转换器
- [ ] 托管的结果查看器
- [ ] autoresearch 之外:持续学习任务流与在线任务——以
  [扩展](docs/design.md#extensibility)的形式落地,而不是重写

## 开发

```bash
git clone https://github.com/Human-Agent-Society/tide-eval && cd tide-eval
uv venv --python 3.12 && uv pip install -e . pytest pytest-asyncio ruff
.venv/bin/python -m pytest tests/ -q     # 未安装 harbor 时相关测试自动跳过
.venv/bin/ruff check . && .venv/bin/ruff format --check .
```

PR 遵循的设计规则:[CONTRIBUTING.md](CONTRIBUTING.md) ·
许可证:[Apache-2.0](LICENSE)
