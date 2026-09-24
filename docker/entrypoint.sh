#!/bin/sh
# 容器启动入口：
# 1. 启动时安装/校验依赖（已安装则秒过，缺失时自动补装）
# 2. 初始化数据目录
# 3. 执行容器命令（默认 uvicorn）
set -e

echo "[entrypoint] 校验 Python 依赖..."
if ! python -c "import fastapi, uvicorn, pydantic" 2>/dev/null; then
    echo "[entrypoint] 检测到依赖缺失，开始安装..."
    pip install --no-cache-dir -r /app/requirements.txt
else
    echo "[entrypoint] 依赖已就绪"
fi

DATA_DIR="${DATA_DIR:-/data}"
mkdir -p "$DATA_DIR"
echo "[entrypoint] 数据目录: $DATA_DIR"

echo "[entrypoint] 启动: $*"
exec "$@"
