import os
import sys
from flask import Flask
from config import Config
from models import db
from routes import api_bp, views_bp

def get_resource_path(relative_path):
    """获取资源文件的绝对路径"""
    if hasattr(sys, '_MEIPASS'):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

def create_app(config_class=Config):
    template_folder = get_resource_path('templates')

    app = Flask(__name__, template_folder=template_folder)
    app.config.from_object(config_class)

    # Railway环境
    if os.environ.get('RAILWAY_STATIC_URL') or os.environ.get('PORT'):
        port = int(os.environ.get('PORT', 5000))
        app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL') or \
            f'sqlite:///{os.path.join(os.path.dirname(__file__), "stock_review.db")}'
    else:
        # 本地/Windows打包
        base_dir = os.path.dirname(os.path.abspath(__file__))
        app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(base_dir, "stock_review.db")}'

    db.init_app(app)
    app.register_blueprint(views_bp)
    app.register_blueprint(api_bp, url_prefix='/api')

    with app.app_context():
        db.create_all()

    return app

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app = create_app()
    print("=" * 50)
    print("股票复盘系统 启动成功!")
    print(f"访问地址: http://localhost:{port}")
    print("=" * 50)
    app.run(host='0.0.0.0', port=port, debug=False)
