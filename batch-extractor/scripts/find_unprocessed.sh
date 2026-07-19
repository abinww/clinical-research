#!/bin/bash
# find_unprocessed.sh - 找出未被摘要的 raw/ 文件

# 读取 config.yaml 获取目录路径
CONFIG_FILE="$(dirname "$0")/../../config.yaml"
RAW_DIR=$(grep "^raw_dir:" "$CONFIG_FILE" | sed 's/raw_dir: *//' | xargs)
SUMMARY_DIR=$(grep "^summary_dir:" "$CONFIG_FILE" | sed 's/summary_dir: *//' | xargs)

expand_path() {
    case "$1" in
        "~") printf "%s\n" "$HOME" ;;
        "~/"*) printf "%s/%s\n" "$HOME" "${1#~/}" ;;
        *) printf "%s\n" "$1" ;;
    esac
}

RAW_DIR=$(expand_path "$RAW_DIR")
SUMMARY_DIR=$(expand_path "$SUMMARY_DIR")

# 如果解析失败使用默认值
[ -z "$RAW_DIR" ] && RAW_DIR="$HOME/clinical/raw"
[ -z "$SUMMARY_DIR" ] && SUMMARY_DIR="$HOME/clinical/summary"

echo "扫描目录:"
echo "  raw_dir: $RAW_DIR"
echo "  summary_dir: $SUMMARY_DIR"
echo ""

# 收集已处理的 raw 文件（从 summary/{药品}/ 各子目录的 YAML 中提取 source_raw）
# 注意：摘要按药品分子目录组织，文件位于 summary/{药品名}/{药品名}@{适应症}.md
declare -A PROCESSED

# 递归遍历 summary_dir 下所有 .md 文件（跳过顶层可能存在的 INDEX.md 等清单文件）
while IFS= read -r -d '' summary_file; do
    # 提取 YAML frontmatter 中的 source_raw
    source_raw=$(sed -n '/^---$/,/^---$/p' "$summary_file" | grep "^source_raw:" | sed 's/source_raw: *//' | tr -d '"' | xargs)

    if [ -n "$source_raw" ]; then
        PROCESSED["$source_raw"]=1
    fi
done < <(find "$SUMMARY_DIR" -mindepth 2 -name "*.md" -type f -print0 2>/dev/null)

echo "已摘要文件数: ${#PROCESSED[@]}"
echo ""

# 找出未处理的 raw 文件
echo "未处理的 raw 文件:"
FOUND=0
for raw_file in "$RAW_DIR"/*.md; do
    [ -e "$raw_file" ] || continue

    filename=$(basename "$raw_file")
    relative_path="raw/$filename"

    if [ -z "${PROCESSED[$relative_path]}" ]; then
        echo "  $relative_path"
        FOUND=$((FOUND + 1))
    fi
done

echo ""
echo "总计: $FOUND 个文件待处理"

# 如果没有未处理文件，返回空列表
if [ $FOUND -eq 0 ]; then
    echo "raw/ 目录下无新增文件需要处理"
    exit 0
fi