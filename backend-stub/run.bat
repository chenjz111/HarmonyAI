@echo off
chcp 65001 >nul
echo 正在安装依赖（首次运行需要）...
pip install -r requirements.txt -q
echo.
echo 启动 HarmonyAI 后端 Stub...
echo 接口文档：http://localhost:8000/docs
python server.py
pause
