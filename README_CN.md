# 🌊 tide

[![CI](https://github.com/Human-Agent-Society/tide-eval/actions/workflows/ci.yml/badge.svg)](https://github.com/Human-Agent-Society/tide-eval/actions/workflows/ci.yml)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](pyproject.toml)
[![License](https://img.shields.io/badge/license-Apache--2.0-green.svg)](LICENSE)

**基于 [Harbor](https://github.com/laude-institute/harbor) 任务标准的 autoresearch 评测框架。**

[English](README.md) | **中文**

Autoresearch 任务——DeepMind 的
[AlphaEvolve](https://deepmind.google/discover/blog/alphaevolve-a-gemini-powered-coding-agent-for-designing-advanced-algorithms/)
和 [Karpathy 的 autoresearch](https://github.com/karpathy/autoresearch) 做的就是这类工作——是开放式优化
问题:数小时的预算、连续的分数、一个持续迭代逼近更优解的 agent。这里没有
"通过/不通过",只有*多好、多快*。tide 把这种形态的评测做扎实:

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/assets/readme-hero-dark.svg">
  <img src="docs/assets/readme-hero-light.svg" alt="The agent searches however it likes and submits what is worth scoring, within a submission limit. The judge holds all scoring code and data and scores every submission into a log. An optional final judge with hidden tests runs once on the best submission and locks the session. The reward and the submission log land in one table shared by every run, where agents can be compared." width="100%">
</picture>

任务是 100% 原生 Harbor 任务(有测试强制保证)。agent 是任何能在容器里工作
的东西——包括你自己的 harness 或方法。

## 为什么不直接用 Harbor?

Harbor 解决的是最难的基础设施——任务格式、让 agent 对着容器运行、现成的
agent 适配器生态——tide 正是把它当库来用。而 autoresearch 在此之上还需要四
样东西,它们就是 tide 存在的理由:

| 直接用 Harbor | tide |
|---|---|
| 每次 trial 只有一个 reward 数字,过程信息丢了 | judge 给每次提交打分并记录在案:anytime 曲线、AUC、到达阈值的时间各是一个查询,而且每个点都可信 |
| 统计只在单个 job 内部(pass@k) | 预算是普通标签,"8 小时比 2 小时多买到多少分"是跨任意 run 集合的一个查询 |
| 一个任务一次运行——而覆盖全套件、重复取方差、扫预算档会把它放大成几天的机器时间,一次崩溃全部报废 | 重跑同一个脚本,已完成的 episode 自动跳过,只有没跑完的部分重新执行 |
| 每次运行是一个一次性 job 目录 | 所有运行落进同一张表,跨运行比较不同 agent 只是一个查询,`tide report` 直接读 |

一个诚实的边界:续跑的粒度是 episode。一批实验会从崩溃处继续,但一个跑了
一半的 12 小时 episode 本身要重来。

完整设计——信任模型、任务约定、数据模型、扩展性:
**[docs/design.md](docs/design.md)**(英文)。

## 使用 tide

### 跑起来

```bash
# PyPI 发布前(见 Roadmap),先从源码安装:
git clone https://github.com/Human-Agent-Society/tide-eval && cd tide-eval
pip install -e ".[harbor]"               # 容器模式需要;仅 --local 和 API 的话 -e . 即可

tide list                                # 有哪些任务可跑
tide run autoresearch --agent oracle     # oracle = 内置 agent,运行每个任务的参考解
tide run autoresearch/tsp-tour --agent claude-code --model anthropic/claude-opus-5 --budget 2   # 小时
tide report                              # 汇总结果库
```

#### 没有 Docker?本地开发,容器验证

`--local` 在本机把任务**自己的 judge**作为进程启动,让你的命令直接对着它
运行,完全不涉及容器:

```bash
tide run autoresearch/circle-packing --local \
  --command "python examples/minimal_harness_search.py" --budget 0.01
```

你的命令读 `$JUDGE_URL` 和 `$BUDGET_SEC`,把解 POST 到
`$JUDGE_URL/submit`,judge 的裁决就是结果——和容器里作为 sidecar 运行的是
同一份 judge 代码。注意本地模式没有任何防护:包括 hidden tests 在内的一切
在你自己机器上都是可读的——这没关系,因为你只可能骗到你自己。judge 真正
够不着的是容器运行,所以本地行的 uri 标记为 `local://`:本地开发,报容器
数字。(`python examples/quickstart.py` 和
`--fake` 依然零依赖可用,但它们的分数是模拟的。)

有 Docker 之后,`python examples/run_circle_packing.py` 端到端验证真实流水线
——oracle 必须恰好得 0.75 分——而 `python examples/minimal_harness.py` 是最小
的完整容器 harness:二十五行左右的适配器,包着同一个随机搜索循环。

### Python API

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
row.rewards  # judge 的最终裁决
row.uri  # trial 目录,用于审计

curve = metrics.anytime(lab.df("trace"))  # 每次提交的分数随时间的变化
metrics.auc(curve)  # anytime 分数
metrics.scaling(lab.df("episode"))  # 更多预算买到多少分?
```

重跑任何脚本都会自动续跑。参考:
[lab](docs/components/lab.md) · [metrics](docs/components/metrics.md) ·
[executors](docs/components/executors.md)。

### 接入你自己的 agent

每个任务都给你的 agent 一个 `$JUDGE_URL` 和一份提交额度;无论用哪种方式
接入,任务、judge、结果库都完全相同——所以不同方法的数字可以直接比较:

| 你有什么 | 接入方式 |
|---|---|
| 主流 harness(`claude-code`、`codex`、`aider` 等) | `--agent <名字> --model <模型>`,零代码 |
| 你自己的 harness | 一个 `BaseAgent` 子类,用 `import_path` 引用——可运行的模板:[`examples/minimal_harness.py`](examples/minimal_harness.py) |
| 根本不是 "agent" 的方法(OpenEvolve 式搜索、求解器) | 把候选解 POST 到 `$JUDGE_URL/submit`,收到 429 就停——约 20 行 |

所有任务的协议完全一致,一次接入覆盖全套。唯一不能自带的是 judge。完整
指南(`BaseAgent` 骨架 + OpenEvolve 接法):
**[docs/integration.md](docs/integration.md)**。

## 任务目录

| Benchmark | 任务数 | 上游 | 运行方式 |
|---|---|---|---|
| [第一方任务](tasks/autoresearch) ↓ | 6 | 本仓库 | `tide run autoresearch --agent <a>` |
| [EdgeBench](tasks/edgebench) | 51 · 2–12 小时预算 | [ByteDance-Seed/EdgeBench](https://github.com/ByteDance-Seed/EdgeBench) | `tide run edgebench/<task> --budget <h>` |
| [FrontierCS 2.0](tasks/frontier-cs) | 20 · 含 4 个 GPU kernel | [FrontierCS/Frontier-CS](https://github.com/FrontierCS/Frontier-CS) | `tide run frontier-cs/<task> --agent <a>` |
| [AlgoTune](tasks/algotune) | 154 · 走 Harbor registry | [oripress/AlgoTune](https://github.com/oripress/AlgoTune) | `tide run algotune/<task> --agent <a>` |

每个第一方任务教会这个类别里的一个难点(oracle 在真容器中验证过,作弊用例
在 CI 中持续复测):

| 任务 | 教什么 |
|---|---|
| [`circle-packing`](tasks/autoresearch/circle-packing) | 完整协议;精确算术判分 |
| [`function-minimization`](tasks/autoresearch/function-minimization) | 探索 vs 局部搜索 |
| [`tsp-tour`](tasks/autoresearch/tsp-tour) | 组合搜索、连续信号 |
| [`bin-packing`](tasks/autoresearch/bin-packing) | 精确约束检查 |
| [`symbolic-regression`](tasks/autoresearch/symbolic-regression) | final judge:session 用训练点,最终分用 agent 没见过的点 |
| [`string-compression`](tasks/autoresearch/string-compression) | 安全地给 agent 提交的代码判分 |

### 定义新任务

```bash
cp -r tasks/_template tasks/autoresearch/my-task
pytest tests/test_task_suite.py          # 自动被识别——而且直接是绿的
```

模板本身就是一个完整可跑的任务,所以你从全绿开始,一次替换一个
`TODO(task)` 标记的部分:题面、judge 对每次提交运行的那一份 `score.py`、
提交额度、作弊用例、参考解——可选地再加一个 `final.py`(hidden tests,只
在最优提交上跑一次)。GPU 任务只多两行配置。指南:
**[docs/components/tasks.md](docs/components/tasks.md)**。

## Roadmap

- [ ] 发布 PyPI(`tide-eval`,名字已预留,尚未发布)
- [ ] GPU 示例任务,在 CI 中以 oracle 把关
- [ ] Harbor 版本升级的安全流程
- [ ] [Frontier-Eng](https://arxiv.org/abs/2604.12290) 转换器——47 个工程任务,其 interaction budget
  循环与提交额度直接对应——以及更多 autoresearch 转换器
- [ ] 托管的结果查看器
- [ ] autoresearch 之外:持续学习任务流与在线任务——以
  [扩展](docs/design.md#extensibility)的形式落地,而不是重写

## 开发与贡献

```bash
git clone https://github.com/Human-Agent-Society/tide-eval && cd tide-eval
uv venv --python 3.12 && uv pip install -e . pytest pytest-asyncio ruff
.venv/bin/python -m pytest tests/ -q     # 未安装 harbor 时相关测试自动跳过
.venv/bin/ruff check . && .venv/bin/ruff format --check .
```

欢迎贡献——尤其欢迎新任务。PR 遵循的设计规则见
[CONTRIBUTING.md](CONTRIBUTING.md)。许可证:[Apache-2.0](LICENSE)
