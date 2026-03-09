import os
import sys
from flask import Flask
from config import Config

current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

def create_app(config_class=Config):
    app = Flask(__name__, template_folder=os.path.join(current_dir, 'templates'))
    app.config.from_object(config_class)

    # Vercel 无服务器环境使用内存数据库
    is_vercel = os.environ.get('VERCEL') or os.environ.get('VERCEL_URL')
    if is_vercel:
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'

    from models import db, ensure_trade_schema
    from routes.views import views_bp
    from routes.api import api_bp

    db.init_app(app)
    app.register_blueprint(views_bp)
    app.register_blueprint(api_bp, url_prefix='/api')

    # Vercel 环境每次请求创建新表
    with app.app_context():
        db.create_all()
        ensure_trade_schema()

    return app

# 创建应用实例
app = create_app()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    print("=" * 50)
    print("股票复盘系统 启动成功!")
    print(f"访问地址: http://localhost:{port}")
    print("=" * 50)
    app.run(host='0.0.0.0', port=port, debug=False)
