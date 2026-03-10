# 股票复盘系统

本地部署的股票交易记录管理工具，支持买卖登记、数据分析。

## 功能
- 添加/查看交易记录
- 数据分析（收益率、持仓）
- 图表展示

## 本地运行

```bash
pip install -r requirements.txt
python3 app.py
```

访问 http://localhost:5000

## 部署到Railway

[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/new/template?repository=)

### 步骤：
1. Fork 本项目
2. 在 Railway 新建项目，选择 GitHub
3. 选择仓库，设置环境变量
4. 部署完成

## 目录结构
- app.py - 主程序
- models.py - 数据模型
- routes/ - 路由
- templates/ - 前端页面

## Vercel 部署（yfinance）

项目已包含 `vercel.json`，可直接在 Vercel 导入仓库部署。

1. Vercel 导入 GitHub 仓库
2. 使用默认 Build/Install（自动执行 `pip install -r requirements.txt`）
3. 可选配置环境变量：
   - `SECRET_KEY`：建议配置
   - `DATABASE_URL`：如需持久化，建议使用外部数据库
4. 部署后访问 `/market/query`，输入 `600519`、`000001.SZ`、`AAPL` 测试行情
