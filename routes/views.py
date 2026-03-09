from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from models import db, Stock, Trade
from datetime import datetime, timedelta
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


def _resolve_stock_symbol(stock_query):
    """Resolve stock code by exact name, partial name, or direct code."""
    import akshare as ak

    keyword = (stock_query or '').strip()
    if not keyword:
        return None, None, None

    spot_df = ak.stock_zh_a_spot_em()
    if spot_df is None or spot_df.empty:
        return None, None, '未获取到股票列表，请稍后重试。'

    required_columns = {'代码', '名称'}
    if not required_columns.issubset(set(spot_df.columns)):
        return None, None, '股票列表字段异常，请稍后重试。'

    spot_df = spot_df.copy()
    spot_df['代码'] = spot_df['代码'].astype(str).str.zfill(6)
    spot_df['名称'] = spot_df['名称'].astype(str)

    if keyword.isdigit():
        code = keyword.zfill(6)
        code_match = spot_df[spot_df['代码'] == code]
        if not code_match.empty:
            row = code_match.iloc[0]
            return row['代码'], row['名称'], None

    exact_match = spot_df[spot_df['名称'] == keyword]
    if not exact_match.empty:
        row = exact_match.iloc[0]
        return row['代码'], row['名称'], None

    fuzzy_match = spot_df[spot_df['名称'].str.contains(keyword, na=False, regex=False)]
    if not fuzzy_match.empty:
        row = fuzzy_match.iloc[0]
        return row['代码'], row['名称'], f'未找到完全匹配，已使用最接近股票：{row["名称"]}（{row["代码"]}）'

    return None, None, '未找到对应股票，请检查名称后重试。'

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


@views_bp.route('/market/query')
def market_query():
    stock_query = request.args.get('stock_name', '').strip()
    chart_labels = []
    chart_values = []
    resolved_name = ''
    resolved_code = ''
    info_message = ''
    error_message = ''

    if stock_query:
        try:
            symbol, name, resolve_message = _resolve_stock_symbol(stock_query)
            if resolve_message:
                info_message = resolve_message

            if symbol:
                import akshare as ak

                end_date = datetime.now().date()
                start_date = end_date - timedelta(days=30)
                price_df = ak.stock_zh_a_hist(
                    symbol=symbol,
                    period='daily',
                    start_date=start_date.strftime('%Y%m%d'),
                    end_date=end_date.strftime('%Y%m%d'),
                    adjust='qfq'
                )

                if price_df is None or price_df.empty:
                    error_message = '未查询到近一个月行情数据。'
                elif not {'日期', '收盘'}.issubset(set(price_df.columns)):
                    error_message = '行情数据字段异常，请稍后重试。'
                else:
                    price_df = price_df.sort_values('日期')
                    chart_labels = []
                    chart_values = []
                    for date_value, close_value in zip(price_df['日期'].tolist(), price_df['收盘'].tolist()):
                        if hasattr(date_value, 'strftime'):
                            label = date_value.strftime('%Y-%m-%d')
                        else:
                            label = str(date_value)
                        try:
                            price = float(close_value)
                        except (TypeError, ValueError):
                            continue
                        chart_labels.append(label)
                        chart_values.append(price)

                    if not chart_labels or not chart_values:
                        error_message = '近一个月价格数据为空或格式异常。'
                    else:
                        resolved_name = name
                        resolved_code = symbol
                        if not info_message:
                            info_message = f'已展示 {resolved_name}（{resolved_code}）近一个月收盘价走势。'
            elif not error_message:
                error_message = '未找到可用股票代码，请检查输入。'
        except ImportError:
            error_message = '当前环境未安装 akshare，请先安装依赖后重试。'
        except Exception as exc:
            error_message = f'行情查询失败：{exc}'

    return render_template(
        'market_query.html',
        stock_query=stock_query,
        chart_labels=chart_labels,
        chart_values=chart_values,
        resolved_name=resolved_name,
        resolved_code=resolved_code,
        info_message=info_message,
        error_message=error_message
    )

@views_bp.route('/stock/<int:stock_id>')
def stock_detail(stock_id):
    stock = Stock.query.get_or_404(stock_id)
    trades = Trade.query.filter_by(stock_id=stock_id).order_by(Trade.trade_date).all()
    return render_template('stock_detail.html', stock=stock, trades=trades)
