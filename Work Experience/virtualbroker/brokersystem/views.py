import email
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.urls import reverse_lazy
from django.views.generic import CreateView
from .models import CustomUser, Position, Stock, PriceHistory, Transaction
from .forms import CustomUserCreationForm
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.shortcuts import redirect
from django.http import HttpResponse, JsonResponse
from django.contrib import messages
from django.utils.http import url_has_allowed_host_and_scheme
from django.db.models import Sum, F, DecimalField, Value, ExpressionWrapper, Subquery, OuterRef, Q
from django.db.models.functions import Coalesce, Cast
from decimal import Decimal, ROUND_HALF_UP
from django.utils import timezone
from django.db import transaction

# Create your views here.
def home(request):
    return render(request, 'brokersystem/home.html')

class SignUp(CreateView):
    form_class = CustomUserCreationForm
    template_name = 'brokersystem/signup.html'
    model = CustomUser
    success_url = reverse_lazy('login')

User = get_user_model()

def login_view(request):
    context = {"login_view": "active"}
    next_url = request.GET.get("next") or request.POST.get("next")

    if request.method == "POST":
        email_raw = request.POST.get("email", "")
        password  = request.POST.get("password", "")
        email = email_raw.strip()

        if not email or not password:
            messages.error(request, "Please enter both email and password.")
            return render(request, "brokersystem/login.html", context, status=400)

        user = None

        # TRY 1: If USERNAME_FIELD='email', this is the correct call:
        user = authenticate(request, username=email, password=password)

        if user is not None:
            if not user.is_active:
                messages.error(request, "This account is inactive.")
                return render(request, "brokersystem/login.html", context, status=403)

            login(request, user)

            # Safe redirect to next if provided
            if next_url and url_has_allowed_host_and_scheme(next_url, {request.get_host()}):
                return redirect(next_url)
            return redirect("dashboard")

        messages.error(request, "Invalid credentials.")
        return render(request, "brokersystem/login.html", context, status=401)

    return render(request, "brokersystem/login.html", context)

def logout_view(request):
    logout(request)
    messages.success(request, "You have been logged out successfully.")
    return redirect("home")

def dashboard_view(request):
    qty_dec = Cast(F("quantity"), output_field=DecimalField(max_digits=12, decimal_places=2))

    line_value = ExpressionWrapper(
        qty_dec * F("price"),
        output_field=DecimalField(max_digits=24, decimal_places=2),
    )

    total = (
        Position.objects.filter(user=request.user)
        .aggregate(total=Coalesce(Sum(line_value), Value(Decimal("0.00"))))["total"]
        or Decimal("0.00")
    )

    # Search parameters
    position_search = request.GET.get("position_search", "").strip()
    stock_search = request.GET.get("stock_search", "").strip()
    # Positions list for the tile (symbol/total/qty/price)
    positions_qs = Position.objects.filter(user=request.user)
    
    # Apply position search filter
    if position_search:
        positions_qs = positions_qs.filter(
            Q(stock__symbol__icontains=position_search) | 
            Q(stock__name__icontains=position_search)
        )
    
    positions = (
        positions_qs
        .annotate(total=line_value)
        .values("stock__symbol", "stock__name", "quantity", "price", "total")
        .order_by("stock__symbol")
    )

    # Selected rows via query parameters (no JavaScript)
    selected_symbol = request.GET.get("symbol")  # positions table
    selected_stock_symbol = request.GET.get("stock_symbol")  # stocks table
    
    

    # Stocks with latest price annotated from PriceHistory
    latest_price_subquery = (
        PriceHistory.objects
        .filter(stock=OuterRef("pk"))
        .order_by("-timestamp")
        .values("price")[:1]
    )

    stocks_qs = Stock.objects
    
    # Apply stock search filter
    if stock_search:
        stocks_qs = stocks_qs.filter(
            Q(symbol__icontains=stock_search) | 
            Q(name__icontains=stock_search)
        )
    
    stocks = stocks_qs.annotate(
        latest_price=Coalesce(
            Subquery(latest_price_subquery),
            Value(Decimal("0.00")),
            output_field=DecimalField(max_digits=12, decimal_places=2),
        )
    )
    
    # Auto-select first row if no selection made
    if not selected_symbol and positions.exists():
        first_position = positions.first()
        selected_symbol = first_position["stock__symbol"]
    
    if not selected_stock_symbol and stocks.exists():
        first_stock = stocks.first()
        selected_stock_symbol = first_stock.symbol
    
    # Position graph data
    position_graph_data = None
    if selected_symbol:
        try:
            selected_stock_obj = Stock.objects.get(symbol=selected_symbol)
            position_price_history = PriceHistory.objects.filter(stock=selected_stock_obj).order_by('timestamp')
            
            chart_data = []
            for item in position_price_history:
                chart_data.append({
                    'x': item.timestamp.isoformat(),
                    'y': float(item.price)
                })
            
            position_graph_data = {
                "title": selected_symbol,
                "datasets": [{
                    "label": selected_symbol,
                    "data": chart_data,
                    "borderColor": "rgb(34, 197, 94)",
                    "backgroundColor": "rgba(34, 197, 94, 0.1)",
                    "tension": 0.1
                }]
            }
        except Stock.DoesNotExist:
            position_graph_data = None

    # Stock graph data
    stock_graph_data = None
    if selected_stock_symbol:
        try:
            selected_stock_obj = Stock.objects.get(symbol=selected_stock_symbol)
            stock_price_history = PriceHistory.objects.filter(stock=selected_stock_obj).order_by('timestamp')
            
            chart_data = []
            for item in stock_price_history:
                chart_data.append({
                    'x': item.timestamp.isoformat(),
                    'y': float(item.price)
                })
            
            stock_graph_data = {
                "title": selected_stock_symbol,
                "datasets": [{
                    "label": selected_stock_symbol,
                    "data": chart_data,
                    "borderColor": "rgb(20, 184, 166)",
                    "backgroundColor": "rgba(20, 184, 166, 0.1)",
                    "tension": 0.1
                }]
            }
        except Stock.DoesNotExist:
            stock_graph_data = None

    # Calculate total worth (balance + portfolio)
    total_worth = request.user.balance + total
    
    # Calculate portfolio change (placeholder for now - would need historical data)
    portfolio_change = None  # TODO: Calculate actual daily change when we have historical portfolio values
    
    ctx = {
        "portfolio_amount": total,
        "total_worth": total_worth,
        "portfolio_change": portfolio_change,
        "positions": positions,
        "stocks": stocks,
        "selected_symbol": selected_symbol,
        "selected_stock_symbol": selected_stock_symbol,
        "position_search": position_search,
        "stock_search": stock_search,
        "position_graph_data": position_graph_data,
        "stock_graph_data": stock_graph_data,
    }
    return render(request, "brokersystem/dashboard.html", ctx)


TWO_DP = Decimal("0.01")

def _latest_price_for(stock: Stock):
    price = (
        PriceHistory.objects
        .filter(stock=stock)
        .order_by("-timestamp")
        .values_list("price", flat=True)
        .first()
    )
    return price

def trade_view(request):
    if request.method != "POST":
        return redirect("dashboard")

    # Which button was pressed?
    if "buy" in request.POST:
        side = "buy"
        symbol = request.POST.get("buy")
    elif "sell" in request.POST:
        side = "sell"
        symbol = request.POST.get("sell")
    else:
        messages.error(request, "No action specified.")
        return redirect("dashboard")

    # Quantity
    try:
        qty = int(request.POST.get("quantity", "1"))
        if qty <= 0:
            raise ValueError
    except ValueError:
        messages.error(request, "Quantity must be a positive integer.")
        return redirect("dashboard")

    # Resolve stock
    try:
        stock = Stock.objects.get(symbol=symbol)
    except Stock.DoesNotExist:
        messages.error(request, f"Unknown symbol: {symbol}")
        return redirect("dashboard")

    # Price (use latest from DB; if you pass a hidden input price, prefer/validate it here)
    price = _latest_price_for(stock)
    if price is None:
        messages.error(request, "No price available for this symbol.")
        return redirect("dashboard")

    notional = (price * Decimal(qty)).quantize(TWO_DP, rounding=ROUND_HALF_UP)

    # Apply trade atomically
    with transaction.atomic():
        # Lock user's position row for this stock (if it exists)
        pos = (
            Position.objects
            .select_for_update()
            .filter(user=request.user, stock=stock)
            .first()
        )

        if side == "buy":
            # Create transaction
            Transaction.objects.create(
                user=request.user,
                stock=stock,
                quantity=qty,
                price=price.quantize(TWO_DP, rounding=ROUND_HALF_UP),
                side="buy",
                executed_at=timezone.now(),
            )

            if pos is None:
                # New position at this price
                Position.objects.create(
                    user=request.user,
                    stock=stock,
                    quantity=qty,
                    # Store average cost in Position.price (your schema)
                    price=price.quantize(TWO_DP, rounding=ROUND_HALF_UP),
                )
            else:
                # Weighted average cost update
                old_qty = int(pos.quantity)
                old_cost = Decimal(pos.price)
                new_qty = old_qty + qty
                new_avg = ((old_cost * old_qty) + (price * qty)) / Decimal(new_qty)
                pos.quantity = new_qty
                pos.price = new_avg.quantize(TWO_DP, rounding=ROUND_HALF_UP)
                pos.save(update_fields=["quantity", "price", "last_updated"])

            # Update user balance
            request.user.balance = F('balance') - notional
            request.user.save(update_fields=['balance'])
            messages.success(request, f"Bought {qty} {symbol} @ {price} (notional {notional}).")

        else:  # sell
            if pos is None or pos.quantity < qty:
                messages.error(request, "Insufficient holdings to sell.")
                return redirect("dashboard")

            # Create transaction
            Transaction.objects.create(
                user=request.user,
                stock=stock,
                quantity=qty,
                price=price.quantize(TWO_DP, rounding=ROUND_HALF_UP),
                side="sell",
                executed_at=timezone.now(),
            )

            remaining = pos.quantity - qty
            if remaining <= 0:
                pos.delete()
            else:
                pos.quantity = remaining
                # Keep avg cost unchanged on sell
                pos.save(update_fields=["quantity", "last_updated"])

            # Update user balance
            request.user.balance = F('balance') + notional
            request.user.save(update_fields=['balance'])
            messages.success(request, f"Sold {qty} {symbol} @ {price} (notional {notional}).")

    return redirect("dashboard")
