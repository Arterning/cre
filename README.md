 # 基础启动
  gunicorn app:app

  # 生产环境启动
  gunicorn --bind 0.0.0.0:8000 --workers 4 --worker-class sync --timeout 120 --keep-alive 2 --max-requests 1000 --max-requests-jitter 100 app:app

  # 开发环境启动（带重载）
  gunicorn --bind 0.0.0.0:8000 --workers 1 --reload app:app