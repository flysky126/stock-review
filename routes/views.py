from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from models import db, Stock, Trade
from datetime import datetime
import sqlalchemy as sa

views_bp = Blueprint('views', __name__)


def _parse_month_range(month_value):
    try:
        start_date = datetime.strptime(f'{month_value}-01', '%Y-%m-%d').date()
    except (TypeError, ValueError):
        return None, None

    if start_date.month == 12:
        end_date = start_date.replace(year=start_date.year + 1, month=1, day=1)
    else:
        end_date = start_date.replace(month=start_date.month + 1, day=1)

    return start_date, end_date


def _available_trade_months():
    date_rows = db.session.query(Trade.trade_date).order_by(Trade.trade_date.desc()).all()
    months = []
    seen = set()

    for (trade_date,) in date_rows:
        month_key = trade_date.strftime('%Y-%m')
        if month_key in seen:
            continue
        seen.add(month_key)
        months.append(month_key)

    return months

@views_bp.route('/')
def index():
    stocks = Stock.query.all()
    total_trades = Trade.query.count()

    # 计算当前持仓
    holdings_data = db.session.query(
        Stock.code,
        Stock.name,
        sa.func.sum(
            sa.case(
                (Trade.trade_type == 'buy', Trade.quantity),
                (Trade.trade_type == 'sell', -Trade.quantity),
                else_=0
            )
        ).label('quantity')
    ).join(Trade).group_by(Stock.id).all()

    current_holdings = [{'code': h[0], 'name': h[1], 'quantity': h[2]} for h in holdings_data if h[2] and h[2] > 0]

    return render_template('index.html',
                         stocks=stocks,
                         total_trades=total_trades,
                         holdings=current_holdings)

@views_bp.route('/trades')
def trades():
    page = request.args.get('page', 1, type=int)
    per_page = 20
    view_mode = request.args.get('view', 'all')
    selected_month = request.args.get('month', '').strip()
    sort_mode = request.args.get('sort', 'default')
    available_months = _available_trade_months()

    if view_mode not in {'all', 'month'}:
        view_mode = 'all'
    if sort_mode not in {'default', 'stock_name'}:
        sort_mode = 'default'

    if view_mode == 'month' and not selected_month and available_months:
        selected_month = available_months[0]

    trades_query = Trade.query
    if view_mode == 'month' and selected_month:
        start_date, end_date = _parse_month_range(selected_month)
        if start_date and end_date:
            trades_query = trades_query.filter(
                Trade.trade_date >= start_date,
                Trade.trade_date < end_date
            )
        else:
            view_mode = 'all'
            selected_month = ''
            flash('月份格式无效，已切换到全部记录。', 'warning')

    if sort_mode == 'stock_name':
        trades_query = trades_query.join(Stock).order_by(Stock.name.asc(), Trade.trade_date.desc(), Trade.id.desc())
    else:
        trades_query = trades_query.order_by(Trade.trade_date.desc(), Trade.id.desc())
    trades = trades_query.paginate(page=page, per_page=per_page, error_out=False)

    return render_template(
        'trade.html',
        trades=trades,
        view_mode=view_mode,
        selected_month=selected_month,
        available_months=available_months,
        sort_mode=sort_mode
    )

@views_bp.route('/trade/add', methods=['GET', 'POST'])
def add_trade():
    if request.method == 'POST':
        code = request.form.get('code')
        name = request.form.get('name')
        trade_type = request.form.get('trade_type')
        price = float(request.form.get('price'))
        quantity = int(request.form.get('quantity'))
        commission = float(request.form.get('commission', 0))
        trade_date = datetime.strptime(request.form.get('trade_date'), '%Y-%m-%d').date()
        notes = request.form.get('notes', '')
        buy_reason = request.form.get('buy_reason', '').strip()

        stock = Stock.query.filter_by(code=code).first()
        if not stock:
            stock = Stock(code=code, name=name)
            db.session.add(stock)
            db.session.flush()

        trade = Trade(
            stock_id=stock.id,
            trade_type=trade_type,
            price=price,
            quantity=quantity,
            commission=commission,
            trade_date=trade_date,
            notes=notes,
            buy_reason=buy_reason or None
        )
        db.session.add(trade)
        db.session.commit()

        flash('交易记录添加成功!', 'success')
        return redirect(url_for('views.trades'))

    return render_template('add_trade.html')

@views_bp.route('/trade/delete/<int:trade_id>', methods=['POST'])
def delete_trade(trade_id):
    trade = Trade.query.get_or_404(trade_id)
    db.session.delete(trade)
    db.session.commit()
    flash('交易记录已删除', 'success')
    return redirect(url_for('views.trades'))

@views_bp.route('/analysis')
def analysis():
    view_mode = request.args.get('view', 'all')
    selected_month = request.args.get('month', '').strip()
    available_months = _available_trade_months()

    if view_mode not in {'all', 'month'}:
        view_mode = 'all'

    if view_mode == 'month' and not selected_month and available_months:
        selected_month = available_months[0]

    month_start = None
    month_end = None
    if view_mode == 'month' and selected_month:
        month_start, month_end = _parse_month_range(selected_month)
        if not (month_start and month_end):
            view_mode = 'all'
            selected_month = ''
            flash('月份格式无效，已切换到全部分析。', 'warning')

    stocks = Stock.query.all()

    analysis_data = []
    for stock in stocks:
        stock_trades_query = Trade.query.filter_by(stock_id=stock.id)
        if view_mode == 'month' and month_start and month_end:
            stock_trades_query = stock_trades_query.filter(
                Trade.trade_date >= month_start,
                Trade.trade_date < month_end
            )
        trades = stock_trades_query.order_by(Trade.trade_date).all()

        if not trades:
            continue

        total_buy = 0
        total_sell = 0
        buy_quantity = 0
        sell_quantity = 0

        for t in trades:
            if t.trade_type == 'buy':
                total_buy += t.total_amount
                buy_quantity += t.quantity
            else:
                total_sell += t.total_amount
                sell_quantity += t.quantity

        current_qty = buy_quantity - sell_quantity
        avg_cost = (total_buy / buy_quantity) if buy_quantity > 0 else 0

        last_price = trades[-1].price if trades else 0
        current_value = current_qty * last_price
        profit_loss = total_sell - total_buy + current_value - (total_sell * 0.001)
        return_rate = (profit_loss / total_buy * 100) if total_buy > 0 else 0

        analysis_data.append({
            'code': stock.code,
            'name': stock.name,
            'total_trades': len(trades),
            'current_qty': current_qty,
            'avg_cost': avg_cost,
            'total_invested': total_buy,
            'total_return': profit_loss,
            'return_rate': return_rate
        })

    return render_template(
        'analysis.html',
        analysis_data=analysis_data,
        view_mode=view_mode,
        selected_month=selected_month,
        available_months=available_months
    )

@views_bp.route('/stock/<int:stock_id>')
def stock_detail(stock_id):
    stock = Stock.query.get_or_404(stock_id)
    trades = Trade.query.filter_by(stock_id=stock_id).order_by(Trade.trade_date).all()
    return render_template('stock_detail.html', stock=stock, trades=trades)
