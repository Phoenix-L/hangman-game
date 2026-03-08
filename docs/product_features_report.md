# Product Features Report (现有产品说明书)

## Scope

This report describes only behavior that is implemented and verifiable in the current repository state.

---

## 1. Product Overview

当前产品是一个基于 **Flask + SQLite + 原生前端（HTML/CSS/JS）** 的 Hangman 单词学习游戏系统。系统已具备：

- 可玩的 Hangman 核心流程（抽词、猜字母、输赢判定、重开）
- 基于主题词库的出题
- 用户登录/注册与游客模式共存
- 学习型选词（复习优先 + 错题优先 + 新词）
- 游戏结果落库、排行榜、学习进度统计

整体上，这是一个已经可以端到端运行的学习型猜词产品，而非仅 demo。

---

## 2. Core Gameplay

已实现的核心玩法：

1. **开局取词**：前端优先调用 `/api/word/next?theme=<id>` 获取目标词。
2. **逐字母输入**：仅接收 `a-z` 键盘输入。
3. **错误次数上限**：最多 6 次错误（`maxWrong = 6`）。
4. **输赢判定**：
   - 全部字母猜中则胜利；
   - 错误次数达到上限则失败。
5. **重开机制**：胜/负后显示 `Play Again` 按钮，点击重新取词。
6. **可视化反馈**：Canvas 动态绘制吊人图形。
7. **声音反馈**：正确、错误、胜利、失败分别播放音效。

---

## 3. Vocabulary System

当前词汇系统已统一为 **`data/*.txt` 单一来源**：

- 每个 txt 文件代表一个主题（theme），文件名即 theme 名称（去扩展名）。
- 每行一个单词，入库时统一转小写。
- 跳过空行，重复词通过 `INSERT OR IGNORE` 自动去重。
- 系统启动时通过数据库初始化流程完成词库落地；也可通过独立脚本手动重刷。

当前仓库中已有多个主题文件（如 `ket_animals.txt`, `pet_travel.txt` 等），可直接用于生产词库种子数据。

---

## 4. Learning Engine

### 4.1 选词引擎（认证用户）

`engine/word_selector.py` 实现了数据库驱动的学习优先级：

1. **due_review**：到期复习词（`next_review_at <= now`）
2. **high_mistake**：历史错词优先（`times_wrong` 高者优先）
3. **new_word**：未学习/未见过的新词
4. **fallback_random**：前述都不命中时在主题内随机

并且会根据最近游戏记录规避近期单词，降低重复感。

### 4.2 游客选词

游客模式走主题内随机（`guest_random`），不使用用户学习进度。

### 4.3 间隔重复（Spaced Repetition）

`update_word_progress` 已实现：

- 记录 `times_seen / times_correct / times_wrong / last_seen_at`
- 正确：`interval_days` 翻倍增长（上限 30 天）
- 错误：`interval_days` 重置为 1
- 自动写入 `next_review_at`

这说明产品不仅能玩，还具备基础学习节奏控制能力。

---

## 5. Player System

### 5.1 账户体系

已实现：

- `POST /api/auth/signup` 注册（用户名、密码校验）
- `POST /api/auth/login` 登录
- `POST /api/auth/logout` 登出
- `GET /api/me` 会话身份查询

密码以哈希形式存储（非明文）。

### 5.2 游客模式

- 游客可正常开始游戏并取词。
- 游客无法提交 `POST /api/leaderboard_entries`（返回 401）。

### 5.3 前端认证交互

页面提供 Sign up / Log in / Log out 入口，登录态会在 UI 顶部显示。

---

## 6. Backend Architecture

### 6.1 技术结构

- Flask 提供 REST API 与静态资源服务
- SQLite 作为持久化存储
- 服务启动即执行 DB 初始化与词库种子导入

### 6.2 已实现 API（按能力域）

**词汇与选词**

- `GET /api/random_word`
- `GET /api/themes`
- `GET /api/word/next?theme=<id>`
- `POST /api/word/progress`

**认证与会话**

- `POST /api/auth/signup`
- `POST /api/auth/login`
- `POST /api/auth/logout`
- `GET /api/me`

**成绩与排行榜**

- `POST /api/game/result`（服务器计算分数；认证用户会更新 user_stats 与 streak，响应中可含 rank / leaderboard_score / current_streak_days）
- `POST /api/leaderboard_entries`
- `GET /api/leaderboard/global?period=today|week|all&limit=N`：按用户聚合的排行榜，每人一行；`leaderboard_score` = 时间衰减得分 + 连续天数加成 + 当日活跃加成；支持今日 / 本周 / 全部时段。

**学习进度**

- `GET /api/progress/summary`

---

## 7. Frontend Features

当前前端能力包括：

- 游戏主界面（单词占位、错误字母区、消息区、重开按钮）
- Play / Progress 双视图切换
- 键盘输入驱动游戏流程
- Canvas 吊人绘制
- 登录注册表单与状态切换
- 进度面板（见词数、掌握词数、7天准确率、连续天数、主题维度统计）
- 进度分享卡（Canvas 生成 PNG 并自动下载）
- 音效（correct / wrong / win / lose）
- Play 页迷你排行榜（本周 Top 5：排名、玩家、综合得分、连续天数；当前用户高亮）
- Progress 页完整排行榜（Today / This Week / All Time 切换；排名、得分、连续天数、最近活跃；当前用户摘要卡与“每日挑战”占位）
- 对局结束消息中展示：得分、准确率、当前排名、连续天数（若已登录）

---

## 8. Data Model

SQLite 当前核心表：

1. `users`：账号信息、密码哈希
2. `themes`：词汇主题
3. `words`：主题词条（`UNIQUE(theme_id, value)`）
4. `games`：局结果与评分相关字段
5. `word_progress`：学习进度与复习计划
6. `leaderboard_entries`：排行榜记录

同时包含兼容迁移逻辑：

- 自动补齐历史库缺失列
- 兼容旧版 `word_progress` 结构并迁移到新模型

---

## 9. Current Product Characteristics

1. **学习导向而非纯娱乐**：具备间隔重复和错词优先。  
2. **游客可玩、账号可成长**：低门槛进入 + 登录后可持续追踪。  
3. **服务端评分与落库**：关键结果由后端计算与保存，前端不可直接篡改分数逻辑。  
4. **词库治理清晰**：词汇来源统一为 `data/*.txt`，易审计、易维护。  
5. **可测试性较高**：仓库内已有覆盖认证、DB、选词、进度、排行榜的测试。

---

## 10. Feature Comparison with PRD

> 说明：PRD 原文未在本仓库直接提供。以下对比基于当前项目需求语义（学习型 Hangman、账号/进度/排行榜）与代码实现状态进行归类。

| Feature | Status | Notes |
| ------- | ------ | ----- |
| Gameplay | Implemented | Hangman 核心流程完整：取词、猜字母、输赢判定、重开、画布绘制。 |
| Vocabulary Themes | Implemented | 已有主题表与 `data/*.txt` 词库文件，`/api/themes` 可用。 |
| Word Engine | Implemented | 数据库驱动选词，支持复习优先/错词优先/新词。 |
| Spaced Repetition | Implemented | `interval_days` 与 `next_review_at` 按正确/错误更新。 |
| Database Persistence | Implemented | 游戏、用户、进度、排行榜均入库。 |
| Player Accounts | Implemented | 注册/登录/登出/当前会话接口齐全。 |
| Guest Play Mode | Implemented | 游客可玩；受限能力（排行榜写入）被拦截。 |
| Leaderboard API | Implemented | 支持写入与全局榜查询（可按主题过滤）。 |
| Leaderboard UI | Partially Implemented | 后端能力完整，但前端暂无排行榜展示页。 |
| Score Calculation | Implemented | 由后端统一计算（准确率 + 速度 + 胜利加成）。 |
| Learning Progress Tracking | Implemented | `/api/progress/summary` + 前端 Progress 视图可用。 |
| Share Card | Implemented | 前端 Canvas 生成并下载进度图片。 |
| Vocabulary Management (Admin UI/API) | Not Implemented | 当前仅脚本导入，暂无在线增删改词管理界面/API。 |
| Theme Selection in Gameplay UI | Partially Implemented | 前端会读取主题列表并默认使用第一项，但无显式主题选择控件。 |
| Runtime File-based Word Loading | Not Implemented (by design) | 运行时不直接读词库文件，改为 DB 读取。 |

