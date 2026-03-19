# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

长江雨课堂(Changjiang RainClassroom)自动化工具，用于自动签到、自动答题和课堂监控。目标平台：`https://changjiang.yuketang.cn/`

## Commands

```bash
# 安装依赖
uv sync

# 运行主程序
uv run start.py

# 所有配置直接在 config.py 顶部的"用户配置区域"修改
```

## Architecture

### 入口与配置

- `start.py` — 程序入口，启动时调用 `ensure_session()` 确保 SESSION 可用，然后进入主循环调用签到和监听逻辑，SESSION 过期时自动重新获取
- `config.py` — 纯 Python 配置文件：顶部为用户可编辑的 PHONE、PASSWORD、SESSION、AI_KEY、FILTERED_COURSES，下方为 API 端点、请求头、题目类型映射、签到来源等系统配置

### 核心业务逻辑 (`function/`)

- `check_in.py` — 主编排模块：获取正在上课/考试列表、执行签到、区分"过滤课程"（签到+监听答题）和普通课程（仅签到），启动多线程 WebSocket 监听
- `listening_socket.py` — WebSocket 实时监听：连接 `wss://changjiang.yuketang.cn/wsapp/`，监测课堂消息（题目推送、课程结束），检测到题目后获取 PPT 内容提取题目元数据，调用 AI 答题并提交答案。答题流程有 30s 超时保护，超时选第一个选项
- `user.py` — 获取用户信息（姓名、学号等）

### 工具模块 (`util/`)

- `ai.py` — Google Gemini API 调用（模型 `gemini-3-flash-preview`），构造结构化 prompt 含题型、选项、OCR 结果，返回 JSON 格式 `{"thinking": "...", "answer": [...]}`。AI 请求有 30s 超时保护，超时或失败时选择题选第一项，其他题型返回空
- `login.py` — DrissionPage 自动登录模块：SESSION 缓存（session.txt）、验证、自动浏览器登录、ensure_session 整合流程
- `ocr.py` — PaddleOCR 封装，从 URL 下载图片并识别文字，全局单例初始化
- `file.py` — JSON 日志读写（`log.json`）
- `timestamp.py` — 时间戳工具

### 关键数据流

1. `start.py` → `ensure_session()` 检查/获取有效 SESSION
2. `start.py` → `check_in.get_listening_classes_and_sign(filtered_courses)`
3. 获取当前活跃课堂列表 → 对每个课堂执行签到
4. 过滤课程列表中的课堂 → 启动 WebSocket 线程监听
5. WebSocket 检测到题目 → 获取 PPT → OCR 提取图片文字 → Gemini 生成答案 → 提交答案（30s 超时保护）
6. 签到和答题结果写入 `log.json`
7. SESSION 过期时自动触发 `ensure_session()` 重新获取

### 超时机制

答题流程有双层超时保护：
- **AI 层**（`util/ai.py`）：`concurrent.futures` 包裹 Gemini API 调用，30s 超时
- **流程层**（`listening_socket.py`）：`concurrent.futures` 包裹整个答题流程（含 OCR + AI），30s 超时
- 超时后选择题选第一个选项，填空/主观题返回空答案，POST 提交始终执行

### 部署方式

本地/服务器部署：在 `config.py` 顶部配置凭证，用 cron 或面板定时任务调度 `python start.py`

### 注意事项

- `FILTERED_COURSES` 列表控制哪些课程开启答题监听，空列表表示所有课程都监听，其余课程仅签到
- WebSocket 连接可能因超时断开，但已入队的监听任务会继续执行
- PaddleOCR 首次运行会下载模型文件（约500MB+）
- 项目无测试用例
