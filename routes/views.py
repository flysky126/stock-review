import re
from datetime import datetime

import sqlalchemy as sa
import yfinance as yf
from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for

from models import Stock, Trade, db

views_bp = Blueprint('views', __name__)

PERIOD_CONFIG = {
    '1m': {'label': '近一月', 'yf_period': '1mo'},
    '6m': {'label': '近半年', 'yf_period': '6mo'},
    '1y': {'label': '近一年', 'yf_period': '1y'},
}


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


def _resolve_period(period_value):
    period_key = (period_value or '').strip().lower()
    if period_key not in PERIOD_CONFIG:
        period_key = '1m'
    period_cfg = PERIOD_CONFIG[period_key]
    return period_key, period_cfg['label'], period_cfg['yf_period']


def _hk_code_to_yf_symbol(code):
    raw = str(code or '').strip()
    if not re.fullmatch(r'\d{1,5}', raw):
        return None
    normalized = raw.zfill(4) if len(raw) <= 4 else raw
    return f'{normalized}.HK'


def _cn_code_to_yf_symbol(code):
    code = str(code or '').strip().zfill(6)
    if not re.fullmatch(r'\d{6}', code):
        return None

    if code.startswith(('6', '9', '5')):
        suffix = 'SS'
    elif code.startswith(('8', '4', '7')):
        suffix = 'BJ'
    else:
        suffix = 'SZ'
    return f'{code}.{suffix}'


def _resolve_stock_symbol(stock_query):
    """
    Resolve query into yfinance symbol.
    Supports:
    - A-share code: 600519 / sh600519 / 000001.SZ
    - US ticker: AAPL / MSFT
    - Existing stock name in local records
    """
    keyword = (stock_query or '').strip()
    if not keyword:
        return None, None, None

    upper_keyword = keyword.upper()

    # sh600519 / sz000001 / bj430047 / hk0700
    prefixed_match = re.fullmatch(r'^(SH|SZ|BJ|HK)(\d{1,6})$', upper_keyword)
    if prefixed_match:
        market, code = prefixed_match.groups()
        if market == 'HK':
            symbol = _hk_code_to_yf_symbol(code)
            if symbol:
                return symbol, code, None
            return None, None, '港股代码格式不正确，请输入如 0700 或 hk0700。'
        if len(code) != 6:
            return None, None, 'A股代码需为 6 位数字。'
        return f'{code}.{market}', code, None

    # 600519 / 000001 / 430047
    if re.fullmatch(r'^\d{6}$', keyword):
        symbol = _cn_code_to_yf_symbol(keyword)
        if symbol:
            return symbol, keyword.zfill(6), None

    # 0700 / 700 / 9988 -> 港股
    if re.fullmatch(r'^\d{1,5}$', keyword):
        hk_symbol = _hk_code_to_yf_symbol(keyword)
        if hk_symbol:
            return hk_symbol, keyword, None

    # Already in yfinance-style market symbol (e.g. 000001.SZ, 600519.SS, 430047.BJ, 0700.HK)
    if re.fullmatch(r'^\d{4,6}\.(SZ|SS|BJ|HK)$', upper_keyword):
        return upper_keyword, upper_keyword, None

    # US / global ticker symbols (e.g. AAPL, BRK-B, 9988.HK)
    if re.fullmatch(r'^[A-Z][A-Z0-9.-]{0,15}$', upper_keyword):
        return upper_keyword, upper_keyword, None

    # Try resolve Chinese name from local saved stocks
    exact_stock = Stock.query.filter(Stock.name == keyword).first()
    if exact_stock:
        symbol = _cn_code_to_yf_symbol(exact_stock.code)
        if symbol:
            return symbol, exact_stock.code, None

    fuzzy_stock = Stock.query.filter(Stock.name.contains(keyword)).order_by(Stock.id.asc()).first()
    if fuzzy_stock:
        symbol = _cn_code_to_yf_symbol(fuzzy_stock.code)
        if symbol:
            return symbol, fuzzy_stock.code, f'未找到完全匹配，已使用本地记录股票：{fuzzy_stock.name}（{fuzzy_stock.code}）'

    return None, None, '未识别输入。请用代码查询（如 600519、000001.SZ、0700.HK、AAPL）；中文名称需先在交易记录里存在。'


def _format_market_cap(market_cap_value, currency):
    try:
        cap = float(market_cap_value)
    except (TypeError, ValueError):
        return ''

    if cap <= 0:
        return ''

    if cap >= 1_000_000_000_000:
        cap_text = f'{cap / 1_000_000_000_000:.2f} 万亿'
    elif cap >= 100_000_000:
        cap_text = f'{cap / 100_000_000:.2f} 亿'
    elif cap >= 10_000:
        cap_text = f'{cap / 10_000:.2f} 万'
    else:
        cap_text = f'{cap:,.0f}'

    if currency:
        return f'{cap_text} {currency}'
    return cap_text


def _build_stock_profile(ticker, symbol, fallback_name):
    info = {}
    fast_info = {}
    profile_error = None

    try:
        info = ticker.get_info() or {}
    except Exception as exc:
        profile_error = f'简介获取失败：{exc}'

    try:
        fast_info = dict(ticker.fast_info) if getattr(ticker, 'fast_info', None) else {}
    except Exception:
        fast_info = {}

    currency = info.get('currency') or fast_info.get('currency') or ''
    market_cap_value = info.get('marketCap') or fast_info.get('marketCap')
    summary = (info.get('longBusinessSummary') or '').strip()

    if len(summary) > 500:
        summary = f'{summary[:500].rstrip()}...'

    profile = {
        'name': info.get('longName') or info.get('shortName') or fallback_name or symbol,
        'symbol': symbol,
        'exchange': info.get('fullExchangeName') or info.get('exchange') or '',
        'currency': currency,
        'market_cap': _format_market_cap(market_cap_value, currency),
        'sector': info.get('sector') or '',
        'industry': info.get('industry') or '',
        'country': info.get('country') or '',
        'website': info.get('website') or '',
        'summary': summary,
        'error': profile_error,
    }

    has_main_content = any(
        profile.get(field)
        for field in ['exchange', 'market_cap', 'sector', 'industry', 'country', 'website', 'summary']
    )
    if not has_main_content and profile_error:
        return {'name': profile['name'], 'symbol': symbol, 'error': profile_error}
    return profile

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
    selected_period, period_text, yf_period = _resolve_period(request.args.get('period', '1m'))
    chart_labels = []
    chart_values = []
    resolved_name = ''
    resolved_code = ''
    stock_profile = None
    info_message = ''
    error_message = ''

    if stock_query:
        try:
            symbol, name, resolve_message = _resolve_stock_symbol(stock_query)
            if resolve_message:
                if symbol:
                    info_message = resolve_message
                else:
                    error_message = resolve_message

            if symbol:
                ticker = yf.Ticker(symbol)

                price_df = yf.download(
                    symbol,
                    period=yf_period,
                    interval='1d',
                    auto_adjust=False,
                    progress=False,
                    threads=False
                )

                if price_df is None or price_df.empty:
                    error_message = f'未查询到{period_text}行情数据。'
                else:
                    close_series = None
                    if 'Close' in price_df.columns:
                        close_series = price_df['Close']
                        if hasattr(close_series, 'columns'):
                            close_series = close_series.iloc[:, 0]
                    else:
                        for column in price_df.columns:
                            if str(column).lower() == 'close':
                                close_series = price_df[column]
                                break

                    if close_series is None or len(close_series) == 0:
                        error_message = '行情数据字段异常，未找到收盘价。'
                    else:
                        close_series = close_series.sort_index()
                        chart_labels = []
                        chart_values = []
                        for date_value, close_value in close_series.items():
                            if hasattr(date_value, 'strftime'):
                                label = date_value.strftime('%Y-%m-%d')
                            else:
                                label = str(date_value)
                            try:
                                price = float(close_value)
                            except (TypeError, ValueError):
                                continue
                            if price != price:  # NaN check
                                continue
                            chart_labels.append(label)
                            chart_values.append(price)

                        if not chart_labels or not chart_values:
                            error_message = f'{period_text}价格数据为空或格式异常。'
                        else:
                            stock_profile = _build_stock_profile(ticker, symbol, name or symbol)
                            resolved_name = stock_profile.get('name') or name or symbol
                            resolved_code = symbol
                            if not info_message:
                                info_message = f'已展示 {resolved_name}（{resolved_code}）{period_text}收盘价走势。'
            elif not error_message:
                error_message = '未找到可用股票代码，请检查输入。'
        except ImportError:
            error_message = '当前环境未安装 yfinance，请先安装依赖后重试。'
        except Exception as exc:
            error_message = f'行情查询失败：{exc}'

    return render_template(
        'market_query.html',
        stock_query=stock_query,
        chart_labels=chart_labels,
        chart_values=chart_values,
        resolved_name=resolved_name,
        resolved_code=resolved_code,
        selected_period=selected_period,
        period_text=period_text,
        period_options=PERIOD_CONFIG,
        stock_profile=stock_profile,
        info_message=info_message,
        error_message=error_message
    )

@views_bp.route('/stock/<int:stock_id>')
def stock_detail(stock_id):
    stock = Stock.query.get_or_404(stock_id)
    trades = Trade.query.filter_by(stock_id=stock_id).order_by(Trade.trade_date).all()
    return render_template('stock_detail.html', stock=stock, trades=trades)
