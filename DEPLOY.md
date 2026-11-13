# 陕西传统村落网站部署说明

## 运行环境

- Python 3.11 或更高版本
- SQLite（当前已预置数据库）
- 可选：Nginx、systemd
- 服务器需要能访问 `api.deepseek.com`

## 一、上传与安装

将压缩包解压到服务器，例如：

```bash
/opt/village-site
```

安装依赖：

```bash
cd /opt/village-site
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
```

## 二、配置环境变量

复制模板：

```bash
cp backend/.env.example .env
```

编辑 `.env`，至少填写：

```env
DEEPSEEK_API_KEY=你的DeepSeek密钥
ADMIN_ACCOUNT=传统村落后台管理
ADMIN_PASSWORD=部署后的新密码
ADMIN_NAME=传统村落后台管理
```

注意：

- 压缩包没有包含 DeepSeek 密钥，必须在服务器上重新配置
- 不要提交 `.env`
- 正式部署后立即执行：

```bash
source .venv/bin/activate
python backend/change_admin_password.py
```

该脚本会交互式设置新密码，不会把密码写进命令历史。

## 三、启动服务

```bash
chmod +x start.sh
./start.sh
```

默认监听：

```text
127.0.0.1:8010
```

检查：

```bash
curl http://127.0.0.1:8010/api/health
```

## 四、Nginx 反向代理

示例配置：

```nginx
server {
    listen 80;
    server_name your-domain.example;

    client_max_body_size 10m;

    location / {
        proxy_pass http://127.0.0.1:8010;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
    }
}
```

启用 HTTPS 时使用 Certbot 或云服务商证书。

## 五、systemd

参考 `deployment/village-site.service`，把项目路径和环境文件路径改成服务器上的实际位置：

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now village-site
sudo systemctl status village-site
```

## 六、数据与备份

运行时数据：

```text
data/app.db
data/uploads/
```

必须定期备份。示例：

```bash
mkdir -p /var/backups/village-site
sqlite3 data/app.db ".backup '/var/backups/village-site/app-$(date +%F).db'"
tar -czf "/var/backups/village-site/uploads-$(date +%F).tar.gz" data/uploads
```

## 七、注意事项

1. 压缩包中的数据库已预置 37 个村落，不要随意再次运行 `backend/seed.py`。
2. `backend/seed.py` 会重新导入并覆盖对应村落的内容模块，只用于首次初始化或明确需要重新导入时。
3. `data/app.db` 中保留当前管理员账号，但建议部署后立即修改密码。
4. AI 联网检索只接受政府、官方媒体和传统村落官网白名单域名。
5. 如果未配置 `TAVILY_API_KEY`，联网检索会使用 Bing RSS 并继续执行白名单过滤。
6. 反馈邮件通知需要配置 SMTP；不配置时反馈仍会保存到后台。
7. 服务日志不要上传到公开目录，API 文档在正式环境可按需关闭。
