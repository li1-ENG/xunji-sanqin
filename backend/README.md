# 陕西传统村落后端管理

## 技术栈

- FastAPI
- SQLAlchemy 2
- SQLite（默认，可切换 PostgreSQL）
- 原生 HTML/CSS/JavaScript 管理页面

## 启动

在项目根目录 `D:\传智杯` 执行：

```powershell
python backend\seed.py
python -m uvicorn backend.app.main:app --reload --port 8010
```

访问：

- 管理后台：http://127.0.0.1:8010/admin
- API 文档：http://127.0.0.1:8010/docs
- 健康检查：http://127.0.0.1:8010/api/health

默认管理员：

```text
账号：传统村落后台管理
密码：SX666
```

正式部署前必须通过环境变量修改：

```text
ADMIN_ACCOUNT
ADMIN_PASSWORD
ADMIN_NAME
```

## 首次数据导入

运行：

```powershell
python backend\seed.py
```

会把以下数据导入数据库：

- 10 个城市
- 37 个陕西村落
- 939 个内容模块
- 历史人物、历史环境要素
- 图片和视频元数据

也可以在管理后台的“数据导入”页面点击“开始导入”。

## 主要接口

### 公开接口

```text
GET  /api/stats
GET  /api/cities
GET  /api/cities/{slug}/villages
GET  /api/villages
GET  /api/villages/{id_or_source_id}
POST /api/feedback
```

### 管理员接口

```text
POST /api/admin/auth/login
POST /api/admin/auth/logout
GET  /api/admin/auth/me

GET    /api/admin/stats
GET    /api/admin/cities
POST   /api/admin/cities
PUT    /api/admin/cities/{id}
DELETE /api/admin/cities/{id}

GET    /api/admin/villages
POST   /api/admin/villages
GET    /api/admin/villages/{id}
PUT    /api/admin/villages/{id}
PATCH  /api/admin/villages/{id}/status
DELETE /api/admin/villages/{id}

POST   /api/admin/villages/{id}/sections
PUT    /api/admin/sections/{id}
DELETE /api/admin/sections/{id}
PUT    /api/admin/villages/{id}/sections/reorder

POST   /api/admin/villages/{id}/figures
PUT    /api/admin/figures/{id}
DELETE /api/admin/figures/{id}

POST   /api/admin/villages/{id}/historic-elements
PUT    /api/admin/historic-elements/{id}
DELETE /api/admin/historic-elements/{id}

POST   /api/admin/villages/{id}/media
PUT    /api/admin/media/{id}
DELETE /api/admin/media/{id}

GET    /api/admin/feedback
PATCH  /api/admin/feedback/{id}
DELETE /api/admin/feedback/{id}

POST   /api/admin/import/processed
```

## 数据库切换

默认数据库文件：

```text
D:\传智杯\data\app.db
```

如需切换 PostgreSQL，设置环境变量：

```powershell
$env:DATABASE_URL='postgresql+psycopg://user:password@localhost:5432/villages'
```

同时需要安装 PostgreSQL 驱动和 pgvector 扩展。当前版本先把数据、内容和反馈管理跑通，AI 向量检索可以在此数据库基础上继续增加。

## 内容模型说明

- `cities`：城市
- `villages`：村落基础信息
- `village_sections`：历史、建筑、环境、民俗、非遗等可选内容模块
- `village_figures`：历史人物
- `historic_elements`：历史环境要素
- `media_items`：图片、视频、全景数据
- `feedback`：意见与反馈
- `admin_users` / `admin_sessions`：管理员和登录会话

不同村落的内容模块数量不同，前端根据 `sections` 动态渲染即可。

## AI 问答与联网检索

公开接口：

```text
POST /api/ai/chat
```

请求示例：

```json
{
  "message": "党家村有哪些代表性建筑？",
  "history": [],
  "deep_thinking": true
}
```

处理流程：

1. 从本地村落档案中检索最相关的章节
2. 使用 DeepSeek `deepseek-reasoner` 深度思考并生成回答
3. 只允许引用后端返回的资料编号
4. 本地资料不足时，尝试检索白名单中的政府、官方媒体和传统村落官网
5. 大模型不可用时自动退回本地档案摘录
6. 没有可靠来源时明确返回资料不足，不凭空生成

环境变量：

```text
DEEPSEEK_API_KEY=你的密钥
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_CHAT_MODEL=deepseek-chat
DEEPSEEK_REASONER_MODEL=deepseek-reasoner
AI_REQUEST_TIMEOUT=75
AI_MAX_OUTPUT_TOKENS=2200
AI_WEB_SEARCH_ENABLED=1
TAVILY_API_KEY=可选的联网搜索密钥
```

联网结果只接受以下白名单域名及其子域名：

```text
gov.cn
dmctv.cn
ncha.gov.cn
mct.gov.cn
xinhuanet.com
people.com.cn
shaanxi.gov.cn
whhlyt.shaanxi.gov.cn
cnwest.com
```

如果未配置 `TAVILY_API_KEY`，系统会使用 Bing RSS 作为补充检索，并继续执行域名白名单过滤。

## 图片上传

后台接口：

```text
POST   /api/admin/villages/{village_id}/media/upload
DELETE /api/admin/media/{media_id}
```

上传限制：

- 支持 JPG、PNG、WebP
- 默认最大 8MB
- 最长边压缩到 2600px
- 去除 EXIF 并统一转为 WebP
- 文件保存在 `data/uploads/villages/...`
- 数据库只保存 `/uploads/...` 访问地址
- 删除媒体记录时同步删除本地文件

## 反馈防刷与邮件通知

公开接口：

```text
POST /api/feedback
```

当前保护：

- 邮箱格式校验
- 反馈类型白名单
- 名称、城市和正文长度限制
- 同一 IP 60 秒内只能提交一次
- 同一 IP 每小时最多提交 5 条
- 隐藏蜜罐字段拦截简单机器人
- 10 分钟内相同内容不重复写入

可选 SMTP 通知：

```text
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
SMTP_FROM=
FEEDBACK_TO=
SMTP_USE_TLS=1
```

未配置 SMTP 时，反馈仍会正常保存到后台，只是不发送邮件。
