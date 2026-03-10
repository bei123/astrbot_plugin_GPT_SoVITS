# 解决 PR #1 合并冲突说明

[PR #1](https://github.com/bei123/astrbot_plugin_GPT_SoVITS/pull/1) 将 **Zhalslar:main** 合并进 **bei123:main**，因两边已严重分叉（上游已重构为 `core/` 模块、异步、新配置等），产生合并冲突。

推荐做法：**在 fork 仓库中合并上游并全部采用上游（Zhalslar）版本**，这样 PR 即可无冲突合并。

---

## 一、在 fork 仓库中解决冲突（bei123 维护者）

在**单独克隆的** bei123 仓库中执行（不要在主项目 AstrBot 里做）：

### 1. 克隆 fork 并添加上游

```bash
git clone https://github.com/bei123/astrbot_plugin_GPT_SoVITS.git
cd astrbot_plugin_GPT_SoVITS
git remote add upstream https://github.com/Zhalslar/astrbot_plugin_GPT_SoVITS.git
git fetch upstream
```

### 2. 合并上游 main，并采用“上游版本”解决冲突

```bash
git checkout main
git merge upstream/main
```

出现冲突时，若希望**完全采用 Zhalslar 的重构版本**（推荐），可对冲突文件统一采用“他们的”版本：

```bash
# 列出冲突文件
git status

# 对所有冲突文件采用上游（Zhalslar）版本
git checkout --theirs .
git add .
```

若有想保留的 bei123 本地修改，请只对需要保留的文件用 `git checkout --ours <文件>`，其余用 `--theirs`。

### 3. 完成合并并推送

```bash
git commit -m "Merge upstream/main from Zhalslar, resolve conflicts by accepting upstream"
git push origin main
```

推送后，PR #1 会变为可合并状态，在 GitHub 上合并即可。

---

## 二、冲突原因简述

| 分支 | 状态 |
|------|------|
| **bei123/main** | 旧版：单文件 `main.py`、同步 `requests`、`@register`、`filter.regex` 等 |
| **Zhalslar/main** | 新版：`core/` 模块、异步、`PluginConfig`、`filter.command("说")`、`filter.llm_tool()`、缓存与情绪判断等 |

两边对同一批功能做了不同实现，直接合并会产生大量冲突。采用“全部接受上游”的方式可以干净地同步到 Zhalslar 的最新实现。

---

## 三、本仓库（AstrBot）中的插件

当前 `data/plugins/astrbot_plugin_GPT_SoVITS/` 是**旧版**结构（与 bei123 一致）。  
若要在本项目中改用 Zhalslar 的重构版，需要：

1. 从 [Zhalslar/astrbot_plugin_GPT_SoVITS](https://github.com/Zhalslar/astrbot_plugin_GPT_SoVITS) 拉取完整代码（含 `core/`、`metadata.yaml`、`_conf_schema.json` 等）。
2. 用其完整替换当前插件目录内容（或先备份再替换）。

如需，我可以按你当前目录结构写一份“本地替换为 Zhalslar 版本”的具体步骤（含要保留/覆盖的文件列表）。
