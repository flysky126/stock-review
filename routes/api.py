from flask import Blueprint, jsonify, request
from models import db, Stock, Trade
import sqlalchemy as sa

api_bp = Blueprint('api', __name__)

@api_bp.route('/stocks', methods=['GET'])
def get_stocks():
    stocks = Stock.query.all()
    return jsonify([{'id': s.id, 'code': s.code, 'name': s.name} for s in stocks])

@api_bp.route('/stock/<int:stock_id>', methods=['GET'])
def get_stock(stock_id):
    stock = Stock.query.get_or_404(stock_id)
    trades = Trade.query.filter_by(stock_id=stock_id).order_by(Trade.trade_date).all()

    return jsonify({
        'stock': {'id': stock.id, 'code': stock.code, 'name': stock.name},
        'trades': [{
            'id': t.id,
            'type': t.trade_type,
            'price': t.price,
            'quantity': t.quantity,
            'commission': t.commission,
            'total': t.total_amount,
            'date': t.trade_date.isoformat(),
            'buy_reason': t.buy_reason,
            'notes': t.notes
        } for t in trades]
    })

@api_bp.route('/statistics', methods=['GET'])
def get_statistics():
    total_trades = Trade.query.count()

    buys = db.session.query(
        sa.func.sum(Trade.price * Trade.quantity + Trade.commission)
    ).filter_by(trade_type='buy').scalar() or 0

    sells = db.session.query(
        sa.func.sum(Trade.price * Trade.quantity - Trade.commission)
    ).filter_by(trade_type='sell').scalar() or 0

    holdings_data = db.session.query(
        Stock.code,
        sa.func.sum(
            sa.case(
                (Trade.trade_type == 'buy', Trade.quantity),
                (Trade.trade_type == 'sell', -Trade.quantity),
                else_=0
            )
        ).label('qty')
    ).join(Trade).group_by(Stock.id).all()

    current_qty = sum(h[1] for h in holdings_data if h[1] and h[1] > 0)

    return jsonify({
        'total_trades': total_trades,
        'total_buy': float(buys),
        'total_sell': float(sells),
        'current_position': current_qty,
        'profit_loss': float(sells - buys)
    })

@api_bp.route('/chart/monthly', methods=['GET'])
def get_monthly_chart():
    trades = Trade.query.all()

    monthly_data = {}
    for t in trades:
        month_key = t.trade_date.strftime('%Y-%m')
        if month_key not in monthly_data:
            monthly_data[month_key] = {'buy': 0, 'sell': 0}

        if t.trade_type == 'buy':
            monthly_data[month_key]['buy'] += t.total_amount
        else:
            monthly_data[month_key]['sell'] += t.total_amount

    return jsonify(monthly_data)
