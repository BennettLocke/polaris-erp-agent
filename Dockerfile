FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制源码
COPY . .
RUN cd scripts/bag_template && npm ci --omit=dev

# 创建日志目录
RUN mkdir -p logs

# 暴露端口
EXPOSE 5000 8080

# 启动命令
CMD ["python", "main.py", "--mode", "all"]
