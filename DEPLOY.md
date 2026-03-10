# 部署指南

## 一、推送到 GitHub

### 1. 创建 GitHub 仓库
1. 登录 https://github.com
2. 点击 "+" → "New repository"
3. 输入名称: `stock-review`
4. 点击 "Create repository"

### 2. 本地推送

```bash
# 初始化
cd stock_review
git init
git add .
git commit -m "Initial commit"

# 关联仓库 (替换为你的仓库地址)
git remote add origin https://github.com/你的用户名/stock-review.git

# 推送
git push -u origin main
```

---

## 二、免费部署平台

### 方案1: Railway (推荐)

1. 注册 https://railway.app
2. 点击 "New Project" → "Deploy from GitHub repo"
3. 选择 `stock-review` 仓库
4. 等待部署完成，获取访问URL

**免费额度**: $5/月，500小时运行

---

### 方案2: Render

1. 注册 https://render.com
2. 连接 GitHub 仓库
3. 创建 Web Service
4. 设置:
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `python app.py`

**免费额度**: 750小时/月

---

### 方案3: Fly.io

1. 安装 flyctl
2. 注册并登录
3. 创建应用:
   ```bash
   fly launch
   fly deploy
   ```

---

### 方案4: PythonAnywhere

1. 注册 https://www.pythonanywhere.com
2. 上传代码或从GitHub拉取
3. 配置 Web App
4. 设置虚拟环境

**免费额度**: 1个Web应用

---

### 方案5: Vercel

1. 注册并登录 https://vercel.com
2. Import Git Repository，选择本仓库
3. 保持默认构建配置（项目已提供 `vercel.json`）
4. 可选设置环境变量：
   - `SECRET_KEY`（建议）
   - `DATABASE_URL`（若需要持久化数据）
5. 部署完成后访问 `/market/query`，输入 `600519` / `000001.SZ` / `AAPL` 验证 `yfinance` 查询

---

## 三、一键部署按钮

项目已配置 Render 和 Railway 部署按钮。

在 GitHub 仓库页面添加:

```markdown
[![Deploy to Render](https://render.com/deploytobutton.svg)](https://render.com/deploy?repo=https://github.com/你的用户名/stock-review)
```

---

## 四、数据持久化

部署到云端时注意：
- 数据库文件可能需要存储到云存储
- 或使用云数据库（如 Railway PostgreSQL）

如需持久化数据，可在平台环境变量中设置 `DATABASE_URL`。
