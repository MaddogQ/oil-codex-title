# oil-codex-title 个人 fork

这是 [MaddogQ/oil-codex-title](https://github.com/MaddogQ/oil-codex-title) 的个人标题策略，基于 [oil-oil/oil-codex-title](https://github.com/oil-oil/oil-codex-title)。开发分支为 `codex/personal-title-policy`。

用户明确收尾或最新最终答复报告 PR 已合入 main 时触发 Stop 检查；会话结束时由 SessionEnd 补查。插件在后台参考原始目标和最近 3～5 轮有效对话，维护整个话题的持续主线。合并报告只触发评估，仍有待办时不标记完成。标题格式为：

```text
260904 [分析] Codex｜Luna 后台调用
✓ 260904 [分析] Codex｜Luna 后台调用
```

- 日期使用 thread 的真实 `createdAt`，转换为运行插件机器的本机时区后生成六位 `YYMMDD`。不使用 `updatedAt`，后续活动不会改变创建日期。
- 类别只允许实现、设计、排障、优化、配置、分析、调研、规划、创作。对象在前，目标在后，保留一个全角 `｜`，不使用类别 emoji。
- `✓ ` 表示用户明确收尾，或要求的最终交付已完成且无剩余工作。判断不确定时保持 `active`；用户提出新的实质任务后移除 `✓ `，保留原始日期。
- 标题尽量稳定。临时测试、提交、排错或“继续”不会取代主线；只有长期目标转移才重新命名。
- CLI 正常退出触发 SessionEnd 时，评估尚未处理的内容。退出不等于任务完成；`/clear` 切换新会话后，要等旧会话真正结束才评估，不能保证即时更新。
- 安装或升级不会扫描历史话题，也不会仅为统一格式迁移旧标题。新规则在明确收尾的 Stop、SessionEnd 或用户主动检查时应用。
- completion 与归档独立，本 fork 不自动归档。上游归档实现保留并默认关闭。
- 保留手工标题锁定、并发锁与 stale-result 防护。后台只通过官方接口改标题，不往原对话添加命名消息。

## 安装个人 fork

复制下面这段话发给 Codex：

```text
帮我克隆 GitHub 仓库 MaddogQ/oil-codex-title 的 codex/personal-title-policy 分支，按 docs/Windows安装与验证.md 创建本地插件市场并安装完整插件，包含 Stop 和 SessionEnd Hook，不要只安装 Skill。检查 PATH 中的 Python 3.10+、已登录的 Codex CLI、hooks 开关和 doctor。告诉我需要在界面安装、启用与信任 Hook 的具体操作。保留 upstream remote，不开启归档，也不批量改写历史标题。
```

详细命令见 [Windows 安装与验证](docs/Windows安装与验证.md)。本 fork 保持上游现有模型选择、reasoning effort 和服务档位配置，通过既有 Codex CLI 调用；不新增模型路由，不强制切换主对话模型。后台命名仍消耗当前 Codex 账号的模型额度。

当前个人使用范围为中文会话生成中文标题；多语言与历史英文标题迁移暂不扩展。Windows 入口使用 `python -X utf8`，无需 `py` Launcher。

## 日常使用

可以说“预览这个话题的新标题”“固定这个话题的标题”“暂停自动命名”“恢复自动命名”或“查看命名用量”。

这是预览版。本机 172 项程序测试通过，本次 5 个合并交付合成案例通过真实模型评测，见 [合并评测记录](docs/naming-merge-evaluation.json)。此前 95 个真实模型合成案例中，经过程序保护的决策有 89 项通过，6 个多语言/跨语言案例仍未通过，详见验证记录。Windows Desktop 自然 Hook 触发尚未验收。桌面置顶列表也可能继续显示旧缓存，标题元数据写入与实际显示需分别核验。

[分类与完成状态](docs/使用与边界.md) · [命名与回归规范](docs/命名与回归规范.md) · [验证记录](docs/发布验收.md) · [MIT 许可证](LICENSE)
