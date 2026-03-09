from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import sqlalchemy as sa

db = SQLAlchemy()

class Stock(db.Model):
    __tablename__ = 'stocks'

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(10), nullable=False)
    name = db.Column(db.String(50), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    trades = db.relationship('Trade', backref='stock', lazy=True)

class Trade(db.Model):
    __tablename__ = 'trades'

    id = db.Column(db.Integer, primary_key=True)
    stock_id = db.Column(db.Integer, db.ForeignKey('stocks.id'), nullable=False)
    trade_type = db.Column(db.String(10), nullable=False)  # 'buy' or 'sell'
    price = db.Column(db.Float, nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    commission = db.Column(db.Float, default=0)
    trade_date = db.Column(db.Date, nullable=False)
    notes = db.Column(db.Text, nullable=True)
    buy_reason = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def total_amount(self):
        return self.price * self.quantity + self.commission


def ensure_trade_schema():
    """Add backward-compatible columns for existing deployments."""
    inspector = sa.inspect(db.engine)
    if 'trades' not in inspector.get_table_names():
        return

    columns = {col['name'] for col in inspector.get_columns('trades')}
    if 'buy_reason' not in columns:
        with db.engine.begin() as conn:
            conn.execute(sa.text('ALTER TABLE trades ADD COLUMN buy_reason TEXT'))
