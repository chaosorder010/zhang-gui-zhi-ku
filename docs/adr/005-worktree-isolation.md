# ADR-005: 并行开发的 Git Worktree 隔离

> 状态: 已接受
> 日期: 2026-07-15
> 决策者: 开发团队
> 相关: ADR-004 (HyDE/Rerank 双开关)

---

## 背景

开发 ADR-004 的 HyDE 和 Rerank 特性时,两个 agent 并行工作。初始方案让两个 agent 共享主 repo 的不同分支 (`feat/hyde`, `feat/rerank`),结果发生**分支污染**: HyDE agent 误把 commit 47067c3 落到 feat/rerank 分支,导致 T05 分支损坏,T04 的未提交代码丢失。

---

## 决策

### 1. 物理隔离: Git Worktree

每个并行 agent 分配独立的 worktree:

```
zhang-gui-zhi-ku/          ← 主 repo (master)
zgzk-wt-rerank/            ← feat/rerank worktree
zgzk-wt-hyde/              ← feat/hyde worktree
```

创建命令:
```bash
git worktree add ../zgzk-wt-rerank -b feat/rerank
git worktree add ../zgzk-wt-hyde -b feat/hyde
```

### 2. 环境同步

Worktree 不自动复制 gitignored 文件,需手动同步:

| 资源 | 同步方式 |
|---|---|
| `.env` (API keys) | `cp .env ../zgzk-wt-xxx/.env` |
| `.venv` (依赖) | `ln -s /path/to/main/.venv ../zgzk-wt-xxx/.venv` |

`.venv` 用 symlink 而非复制,避免重复安装 torch 等大包。

### 3. Agent 约束

派发给并行 agent 的 prompt 必须包含:
- 明确告知当前目录 (worktree 路径)
- **禁止 `git checkout` 其他分支**
- **禁止推送到 origin**
- 测试范围限定 (只跑本特性的测试文件,不跑全量)

### 4. 合并顺序

特性有依赖时按顺序合并 (如 T04 HyDE 先合,T05 Rerank 后合)。合并冲突在主 repo 手动解决。

---

## 后果

### 正面
- 物理隔离,零交叉污染风险
- 两个 agent 可同时改同一文件 (如 graph.py),最后在主 repo merge
- 失败恢复简单: `git worktree remove` 即可清理

### 负面 / 成本
- 需要手动同步 `.env` / `.venv` (一次性)
- 每个 worktree 占用磁盘空间 (symlink .venv 可缓解)
- 合并冲突仍需人工解决 (但冲突范围明确,只在 graph.py)

---

## 失败案例 (2026-07-14)

**事故**: HyDE agent 误 commit 到 feat/rerank 分支
**根因**: 共享 working directory,agent 执行 `git checkout` 时切到错误分支
**恢复**: cherry-pick 3 个 rerank commit 到新分支,reset feat/hyde 后重新实现 HyDE 节点
**教训**: 物理隔离 > 纪律约束 — 不要信任 agent 遵守"不切分支"的指令

---

## 代码位置

- 主 repo: `/home/leon/projects/shangguigu-learning/zhang-gui-zhi-ku`
- Worktree 目录: 主 repo 的兄弟目录 (`../zgzk-wt-xxx`)
- 清理命令: `git worktree remove <path> --force`
