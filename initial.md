# clinical-research 首次初始化说明

本文档用于指导 agent 在安装 `clinical-research` skill 后完成首次初始化。用户可以对 agent 发送：

```text
请按照 clinical-research/initial.md 初始化临床数据目录。
```

## 默认初始化约定

- 默认数据目录：`~/clinical`
- 配置文件：首次初始化时生成 `config.yaml`

初始化后应形成以下数据目录：

```text
~/clinical/
├── raw/
├── summary/      # 规范摘要（按药品分子目录组织：summary/{药品名}/）
├── drug/         # 药品索引（平铺：{药品名}.md）
├── indication/
├── trials/
└── attachments/
```

## Agent 初始化步骤

### 1. 询问数据目录

先询问用户希望把临床数据保存在哪里，并说明默认值是 `~/clinical`：

```text
请提供 clinical-research 的数据目录。直接回车或未指定时使用默认值：~/clinical
```

如果用户没有指定目录，使用：

```text
~/clinical
```

如果用户指定了其他目录，后续所有路径都以用户指定目录为准。

下面用 `{data_dir}` 表示最终确认的数据目录。

### 2. 生成 config.yaml

在当前 skill 目录下生成 `config.yaml`。不要假设该文件已经存在；如果不存在，直接新建。

生成内容格式如下：

```yaml
# clinical-research 数据目录配置
# 所有子 skill 共享此配置

# 根目录
data_dir: {data_dir}

# 子目录
raw_dir: {data_dir}/raw              # 原始资料存放目录
summary_dir: {data_dir}/summary      # 规范摘要存放目录（按药品分子目录组织）
drug_dir: {data_dir}/drug            # 药品索引存放目录（平铺）
indication_dir: {data_dir}/indication  # 适应症索引存放目录
trials_dir: {data_dir}/trials        # 临床试验查询结果存放目录
attachments_dir: {data_dir}/attachments  # 图片附件存放目录
```

如果 `{data_dir}` 是 `~/clinical`，则配置应为：

```yaml
# clinical-research 数据目录配置
# 所有子 skill 共享此配置

# 根目录
data_dir: ~/clinical

# 子目录
raw_dir: ~/clinical/raw              # 原始资料存放目录
summary_dir: ~/clinical/summary      # 规范摘要存放目录（按药品分子目录组织）
drug_dir: ~/clinical/drug            # 药品索引存放目录（平铺）
indication_dir: ~/clinical/indication  # 适应症索引存放目录
trials_dir: ~/clinical/trials        # 临床试验查询结果存放目录
attachments_dir: ~/clinical/attachments  # 图片附件存放目录
```

如果 `config.yaml` 已经存在，说明可能已经初始化过。此时不要直接覆盖，应先询问用户是否要重新生成配置。

### 3. 创建数据目录

创建数据目录及其子目录。

如果使用默认目录：

```bash
mkdir -p ~/clinical/raw
mkdir -p ~/clinical/summary
mkdir -p ~/clinical/drug
mkdir -p ~/clinical/indication
mkdir -p ~/clinical/trials
mkdir -p ~/clinical/attachments
```

在 Windows PowerShell 中可使用：

```powershell
New-Item -ItemType Directory -Force `
  ~/clinical/raw, `
  ~/clinical/summary, `
  ~/clinical/drug, `
  ~/clinical/indication, `
  ~/clinical/trials, `
  ~/clinical/attachments
```

如果用户指定了其他 `{data_dir}`，把上面的 `~/clinical` 替换为用户指定目录。

### 4. 验证初始化结果

检查以下目录存在：

```text
{data_dir}/raw
{data_dir}/summary
{data_dir}/drug
{data_dir}/indication
{data_dir}/trials
{data_dir}/attachments
```

同时确认 `config.yaml` 中的 `data_dir` 和各子目录路径与用户选择一致。

### 5. 完成提示

初始化完成后，告诉用户可以这样使用：

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
