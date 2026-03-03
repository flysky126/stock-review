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

    db_path = os.path.join(current_dir, 'stock_review.db')
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'

    from models import db
    from routes.views import views_bp
    from routes.api import api_bp

    db.init_app(app)
    app.register_blueprint(views_bp)
    app.register_blueprint(api_bp, url_prefix='/api')

    with app.app_context():
        db.create_all()

    return app

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    app = create_app()
    print("=" * 50)
    print("股票复盘系统 启动成功!")
    print(f"访问地址: http://localhost:{port}")
    print("=" * 50)
    app.run(host='0.0.0.0', port=port, debug=False)
