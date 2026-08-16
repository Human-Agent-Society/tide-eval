# 🌊 tide

[![CI](https://github.com/Human-Agent-Society/tide-eval/actions/workflows/ci.yml/badge.svg)](https://github.com/Human-Agent-Society/tide-eval/actions/workflows/ci.yml)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](pyproject.toml)
[![License](https://img.shields.io/badge/license-Apache--2.0-green.svg)](LICENSE)

**基于 [Harbor](https://github.com/laude-institute/harbor) 任务标准的 autoresearch 与 continual learning 评测框架。**

[English](README.md) | **中文**

tide 评测的是"随经验变强的 agent",支持两种模式。

**Autoresearch**——DeepMind 的
[AlphaEvolve](https://deepmind.google/discover/blog/alphaevolve-a-gemini-powered-coding-agent-for-designing-advanced-algorithms/)
和 [Karpathy 的 autoresearch](https://github.com/karpathy/autoresearch)
做的就是这类工作:开放式优化问题,数小时的预算、连续的分数、一个持续
迭代逼近更优解的 agent。这里没有"通过/不通过",只有*多好、多快*。学习
发生在**单个任务内部**:

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/assets/readme-hero-dark.svg">
  <img src="docs/assets/readme-hero-light.svg" alt="The agent searches however it likes and submits what is worth scoring, within a submission limit. The judge holds all scoring code and data and scores every submission into a log. An optional final judge with hidden tests runs once on the best submission and locks the session. The reward and the submission log land in one table shared by every run, where agents can be compared." width="100%">
</picture>

**Continual learning**——同一个 agent 按顺序做完一条任务[流](docs/api/streams.md)
([AgentStream](https://arxiv.org/abs/2608.00155) 的设定;支持的 benchmark
是 [terminal-bench 2.0](tasks/terminal-bench) 和
[SWE-bench Verified](tasks/swebench-verified)),把自己的记忆从一个任务
带到下一个。重要的不是任何单个任务的分数,而是*经验有没有积累起来*。
学习发生在**任务与任务之间**:

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/assets/readme-stream-dark.svg">
  <img src="docs/assets/readme-stream-light.svg" alt="One agent works through a stream of tasks in order. Each task runs in its own fresh container and is scored on its own, but the agent's memory directory is carried from task to task, with a snapshot kept at every step. Every task's reward lands in the same table as every other run, so the learning curve over the stream is a single query." width="100%">
</picture>

任务是 100% 原生 Harbor 任务(有测试强制保证)。agent 是任何能在容器里工作
的东西——包括你自己的 harness 或方法。

## 为什么不直接用 Harbor?

Harbor 解决的是最难的基础设施——任务格式、让 agent 对着容器运行、现成的
agent 适配器生态——tide 正是把它当库来用。而这两种模式在此之上还需要五
样东西,它们就是 tide 存在的理由:

| 直接用 Harbor | tide |
|---|---|
| 每次 trial 只有一个 reward 数字,过程信息丢了 | judge 给每次提交打分并记录在案:anytime 曲线、AUC、到达阈值的时间各是一个查询,而且每个点都可信 |
| 每次 trial 都从零开始 | [`Stream`](docs/api/streams.md) 把 agent 的记忆(一个状态目录)从一个任务带到下一个,每一步都留快照——学习曲线、迁移、遗忘各是一个查询 |
| 统计只在单个 job 内部(pass@k) | 预算是普通标签,"8 小时比 2 小时多买到多少分"是跨任意 run 集合的一个查询 |
| 一个任务一次运行——而覆盖全套件、重复取方差、扫预算档会把它放大成几天的机器时间,一次崩溃全部报废 | 重跑同一个脚本,已完成的 episode 自动跳过,只有没跑完的部分重新执行 |
| 每次运行是一个一次性 job 目录 | 所有运行落进同一张表,跨运行比较不同 agent 只是一个查询,`tide report` 直接读 |

一个诚实的边界:续跑的粒度是 episode。一批实验会从崩溃处继续,但一个跑了
一半的 12 小时 episode 本身要重来。

完整设计——信任模型、任务约定、数据模型、扩展性:
**[docs/introduction/design.md](docs/introduction/design.md)**(英文)。

## 使用 tide

### 跑起来

```bash
# PyPI 发布前,先从源码安装:
git clone https://github.com/Human-Agent-Society/tide-eval && cd tide-eval
pip install -e ".[harbor]"               # 容器模式需要;仅 --local 和 API 的话 -e . 即可

tide list                                # 有哪些任务可跑
tide run autoresearch --agent oracle     # oracle = 内置 agent,运行每个任务的参考解
tide run autoresearch/tsp-tour --agent claude-code --model anthropic/claude-opus-5 --budget 2h  # 时间(2h / 30m / 90s;裸数字 = 小时)
tide fetch terminal-bench                # continual learning 的 benchmark:89 个通过/不通过任务,pin 在 v2.0
tide stream week1 terminal-bench --agent claude-code --model anthropic/claude-opus-5            # continual learning:记忆跨任务传递
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
[lab](docs/api/lab.md) · [streams](docs/api/streams.md) ·
[metrics](docs/api/metrics.md) · [executors](docs/api/executors.md)。

### Continual learning:任务流

`Stream` 让同一个 agent 按顺序跑一列任务。每个任务的容器里都挂载着
同一个状态目录(`$TIDE_STATE_DIR`),agent 的记忆、技能库、自我演化出的
harness 就随流从一个任务带到下一个——而"带着它到底有没有用"正是被测的
东西:

```python
# 先执行:tide fetch terminal-bench
from tide import Lab, Stream, metrics

lab = Lab("runs/cl")
stream = Stream(
    "week1",  # 有序任务列表,允许重复出现——重访正是"遗忘"显形的地方
    ["tasks/terminal-bench/chess-best-move", "tasks/terminal-bench/build-pmars", "tasks/terminal-bench/chess-best-move"],
)
rows = await stream.run(lab, agent={"name": "claude-code", "model_name": "anthropic/claude-opus-5"}, budget="30m")

df = lab.df("episode")
metrics.learning_curve(df, by=["stream"])  # 经验积累起来了吗?
metrics.forgetting(df)  # 重访的任务退步了吗?
metrics.transfer(df, baseline_df)  # 对比同一批任务的孤立运行(普通 lab.run)
```

流里的每个任务就是一次普通的 Harbor trial、一个独立容器。每个任务开始
前,记忆重置为上一步留下的快照;结束后再存一份新快照——所以流崩溃后能
从断点继续,agent 每一步"知道什么"事后都能查。在末尾追加任务是继续一条
已跑完的流;修改前面的任务会让其后的部分全部重测。完整说明:
**[docs/api/streams.md](docs/api/streams.md)**(英文)。

### 接入你自己的 agent

每个任务都给你的 agent 一个 `$JUDGE_URL` 和一份提交额度;无论用哪种方式
接入,任务、judge、结果库都完全相同——所以不同方法的数字可以直接比较:

| 你有什么 | 接入方式 |
|---|---|
| 主流 harness(`claude-code`、`codex`、`aider` 等) | `--agent <名字> --model <模型>`,零代码 |
| 你自己的 harness | 一个 `BaseAgent` 子类,用 `import_path` 引用——可运行的模板:[`examples/minimal_harness.py`](examples/minimal_harness.py) |
| OpenEvolve、Codex 或 CORAL | 版本固定的可运行适配器:[`examples/run_harness.py`](examples/run_harness.py) |
| 其他根本不是 "agent" 的方法(进化搜索、求解器) | 把候选解 POST 到 `$JUDGE_URL/submit`,收到 429 就停——约 20 行 |

所有任务的协议完全一致,一次接入覆盖全套。唯一不能自带的是 judge。完整
指南(`BaseAgent` 骨架 + OpenEvolve 接法):
**[docs/guides/integration.md](docs/guides/integration.md)**。

## Benchmark 目录

### Autoresearch 模式

| Benchmark | 任务数 | 上游 | 运行方式 |
|---|---|---|---|
| [第一方任务](tasks/autoresearch) ↓ | 6 | 本仓库 | `tide run autoresearch --agent <a>` |
| [EdgeBench](tasks/edgebench) | 51 · 2–12 小时预算 | [ByteDance-Seed/EdgeBench](https://github.com/ByteDance-Seed/EdgeBench) | `tide run edgebench/<task> --budget <h>` |
| [FrontierCS](tasks/frontier-cs) | 188 算法赛道 + 20 研究赛道 · 含 4 个 GPU kernel | [FrontierCS/Frontier-CS](https://github.com/FrontierCS/Frontier-CS) | `tide run frontier-cs/<task> --agent <a>` |

下一批转换目标(已按 autoresearch 契合度筛过)在
[Roadmap](https://github.com/Human-Agent-Society/tide-eval/issues/19) 里跟踪。

### Continual learning 模式

两个 stream benchmark,都从 Harbor registry pin 死的那个 commit 拉取
(所以每次 fetch 都可复现),而且本身就是标准 Harbor 格式——不需要任何
转换:

| Benchmark | 任务数 | 上游 | 运行方式 |
|---|---|---|---|
| [terminal-bench](tasks/terminal-bench) | 89 · **只支持 v2.0**(不含 1.x) | [terminal-bench-2](https://github.com/laude-institute/terminal-bench-2)(Apache-2.0) | `tide fetch terminal-bench`,然后 `tide stream week1 terminal-bench --agent <a>` |
| [SWE-bench Verified](tasks/swebench-verified) | 500 | [harbor-datasets](https://github.com/laude-institute/harbor-datasets) | `tide fetch swebench-verified --limit 50`,然后 `tide stream week1 swebench-verified --agent <a>` |
| [CL-bench](tasks/cl-bench) | 1,899(500 个 context) | [clbench.com](https://www.clbench.com)(仅限评测用途) | `tide fetch cl-bench --contexts 5`,然后 `tide stream week1 cl-bench --agent <a>` |

放 SWE-bench Verified 是因为 [AgentStream](https://arxiv.org/abs/2608.00155)
的任务流由六个 benchmark 组成,而它是其中已有 Harbor 版本的最难的一个
——论文里测出最难的两个(HLE 和 BrowseComp-Plus)目前还没有 Harbor 版。
[CL-bench](tasks/cl-bench) 测的是从上下文材料(规则书、操作规程、实验
数据)里学新知识的能力(前沿模型只解出约 17%),超过一半的任务是同一
context 的连续轮次——转换后每个 context 的轮次在携带记忆下按序成流,由
官方 rubric judge 判分(判分时需要 LLM API key)。stream 也接受你自己排
的任意任务列表,允许重复出现(重复正是测"遗忘"的方式)——见
[streams](docs/api/streams.md)。

### 每个第一方任务教什么

每个第一方任务教会 autoresearch 类别里的一个难点(oracle 在真容器中验证
过,作弊用例在 CI 中持续复测):

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
**[docs/guides/authoring-tasks.md](docs/guides/authoring-tasks.md)**。

## 贡献

最受欢迎的贡献是新任务:复制模板、逐个替换 `TODO(task)` 标记,测试套件
会自动完成任务校验——见上文[定义新任务](#定义新任务)和指南
**[docs/guides/authoring-tasks.md](docs/guides/authoring-tasks.md)**。

benchmark 转换器、指标和运行时的改动,从源码 checkout 开发:

```bash
git clone https://github.com/Human-Agent-Society/tide-eval && cd tide-eval
uv venv --python 3.12 && uv pip install -e . pytest pytest-asyncio ruff
.venv/bin/python -m pytest tests/ -q     # 未安装 harbor 时相关测试自动跳过
.venv/bin/ruff check . && .venv/bin/ruff format --check .
```

PR 遵循的设计规则见 [CONTRIBUTING.md](CONTRIBUTING.md)。
