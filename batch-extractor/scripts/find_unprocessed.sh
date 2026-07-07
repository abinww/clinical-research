#!/bin/bash
# find_unprocessed.sh - 找出未被摘要的 raw/ 文件

# 读取 config.yaml 获取目录路径
CONFIG_FILE="$(dirname "$0")/../../config.yaml"
RAW_DIR=$(grep "^raw_dir:" "$CONFIG_FILE" | sed 's/raw_dir: *//' | xargs)
SOURCE_DIR=$(grep "^source_dir:" "$CONFIG_FILE" | sed 's/source_dir: *//' | xargs)

# 如果解析失败使用默认值
[ -z "$RAW_DIR" ] && RAW_DIR="/mnt/ur/notes/资料/clinical/raw"
[ -z "$SOURCE_DIR" ] && SOURCE_DIR="/mnt/ur/notes/资料/clinical/source"

echo "扫描目录:"
echo "  raw_dir: $RAW_DIR"
echo "  source_dir: $SOURCE_DIR"
echo ""

# 收集已处理的 raw 文件（从 source/ 的 YAML 中提取 source_raw）
declare -A PROCESSED

for source_file in "$SOURCE_DIR"/*.md; do
    [ -e "$source_file" ] || continue
    
    # 提取 YAML frontmatter 中的 source_raw
    source_raw=$(sed -n '/^---$/,/^---$/p' "$source_file" | grep "^source_raw:" | sed 's/source_raw: *//' | tr -d '"' | xargs)
    
    if [ -n "$source_raw" ]; then
        PROCESSED["$source_raw"]=1
    fi
done

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
