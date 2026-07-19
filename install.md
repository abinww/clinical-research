# clinical-research 安装说明

本文档用于指导**当前正在执行本说明的 agent** 下载并安装 `clinical-research` skill。

用户可以直接对当前 agent 发送：

```text
请按照 https://github.com/abinww/clinical-research/blob/main/install.md 安装 clinical-research skill。
```

## 核心原则

- 当前执行安装说明的 agent，就是安装目标。
- 不要询问用户“要安装到哪个 agent”。
- 优先使用当前 agent 自带的 skill/plugin 安装机制。
- 如果当前 agent 没有原生安装命令，再安装到当前 agent 的本地 skill 目录。
- 不要只复制 `SKILL.md`，必须安装完整仓库目录。
- 如果无法确认当前 agent 的 skill 目录，再询问用户该 agent 的 skill 目录位置。

## 安装目标

- GitHub 仓库：`https://github.com/abinww/clinical-research.git`
- Skill 名称：`clinical-research`
- 安装结果：当前 agent 能发现并调用 `clinical-research/SKILL.md`

## Agent 安装步骤

### 1. 识别当前 agent 的安装方式

先判断当前 agent 是否提供原生 skill/plugin 安装命令或安装工具。

如果当前 agent 提供原生安装机制，优先使用它。例如：

```text
install skill from GitHub repository
```

或该 agent 文档中定义的等价命令。

如果当前 agent 支持从 Git 仓库安装 skill，应使用仓库地址：

```text
https://github.com/abinww/clinical-research.git
```

如果当前 agent 没有原生安装机制，进入下一步，使用本地目录安装。

### 2. 找到当前 agent 的 skill 根目录

根据当前 agent 的运行环境、配置文件或官方文档，找到它加载本地 skill 的根目录。

常见名称包括：

```text
skills/
tools/
workflows/
plugins/
extensions/
```

下面统一用 `{skill_root}` 表示当前 agent 的本地 skill 根目录。

如果无法自动确认 `{skill_root}`，只询问这个目录位置：

```text
我需要当前 agent 的本地 skill 目录，才能安装 clinical-research。请提供该目录路径。
```

不要询问用户要安装到哪个 agent。

### 3. 下载完整仓库

将仓库安装为：

```text
{skill_root}/clinical-research/
```

如果 `{skill_root}/clinical-research/` 不存在，执行：

```bash
git clone https://github.com/abinww/clinical-research.git {skill_root}/clinical-research
```

如果目标目录已经存在，先检查它是否已经是本仓库：

```bash
git -C {skill_root}/clinical-research remote -v
```

如果远程地址是 `https://github.com/abinww/clinical-research.git`，可更新到最新版本：

```bash
git -C {skill_root}/clinical-research pull
```

如果目标目录存在但不是本仓库，不要覆盖、删除或合并用户文件，应停止并询问用户如何处理。

如果当前环境没有 Git，可下载 GitHub 仓库压缩包并解压到：

```text
{skill_root}/clinical-research/
```

### 4. 检查安装完整性

安装后确认以下文件和目录存在：

```text
{skill_root}/clinical-research/SKILL.md
{skill_root}/clinical-research/install.md
{skill_root}/clinical-research/initial.md
{skill_root}/clinical-research/schema/
{skill_root}/clinical-research/clinical-extractor/
{skill_root}/clinical-research/batch-extractor/
{skill_root}/clinical-research/clinical-indexer/
{skill_root}/clinical-research/clinical-wiki/
{skill_root}/clinical-research/clinical-drug-summarizer/
{skill_root}/clinical-research/drug-trials-search/
{skill_root}/clinical-research/clinical-trial-evaluator/
```

如果缺少任一关键文件或目录，说明安装不完整，应重新下载完整仓库。

### 5. 刷新当前 agent 的 skill 列表

根据当前 agent 的机制刷新 skill/plugin 列表。常见方式包括：

- 重启当前 agent。
- 开启一个新会话。
- 执行当前 agent 的 reload/refresh skills 命令。
- 等待当前 agent 的 skill watcher 自动刷新。

不要编造当前 agent 不支持的命令。

### 6. 首次初始化

安装完成后，检查已安装目录中是否存在：

```text
{skill_root}/clinical-research/config.yaml
```

如果不存在，读取并执行：

```text
{skill_root}/clinical-research/initial.md
```

`initial.md` 会询问用户数据目录，默认使用 `~/clinical`，然后生成 `config.yaml` 并创建数据目录。

如果 `config.yaml` 已经存在，不要重复初始化，直接保留现有配置。

## 安装完成后的验证

安装和初始化完成后，确认当前 agent 能够读取：

```text
clinical-research/SKILL.md
```

并告诉用户可以这样使用：

```text
提取临床数据: <URL>
```

```text
查询某个药品的临床试验
```

```text
更新药品索引
```

```text
评价这项临床试验数据
```

## 安全要求

- 安装前应确认仓库来源是 `https://github.com/abinww/clinical-research.git`。
- 不要执行来源不明的安装脚本。
- 不要覆盖同名但来源不同的本地目录。
- 不要把患者隐私数据、API key、账号凭证或商业敏感资料写入仓库目录。
