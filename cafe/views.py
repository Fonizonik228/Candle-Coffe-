from datetime import date, timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.contrib.auth.hashers import make_password
from django.db import models
from django.db.models import Sum
from django.http import JsonResponse, HttpResponseRedirect
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import (
    RegisterForm, LoginForm, ProfileForm, AvatarForm, BookingForm,
    ProductForm, EmployeeForm, ReviewForm, NewCardForm, SavedCardCvcForm, ChatMessageForm, detect_brand,
)
from .models import Product, ProductImage, Order, OrderItem, Booking, ChatMessage, Profile, Employee, Review, TABLES


def is_admin(user):
    return user.is_authenticated and user.is_staff


# --------------------------------------------------------------------------
# Public pages
# --------------------------------------------------------------------------

def home(request):
    reviews = Review.objects.select_related('user').all()[:24]
    review_count = Review.objects.count()
    return render(request, 'cafe/home.html', {
        'reviews': reviews,
        'review_count': review_count,
        'review_form': ReviewForm(),
    })


@login_required
@require_POST
def add_review(request):
    if request.user.is_staff:
        messages.error(request, 'Отзывы оставляют покупатели, а не администратор')
        return redirect('home')
    form = ReviewForm(request.POST)
    if form.is_valid():
        review = form.save(commit=False)
        review.user = request.user
        review.save()
        messages.success(request, 'Спасибо за отзыв!')
    else:
        messages.error(request, 'Не удалось сохранить отзыв — проверьте текст')
    return redirect(reverse('home') + '#reviews')


def menu_view(request):
    products = Product.objects.filter(is_active=True).prefetch_related('images')
    category = request.GET.get('category', 'Все')
    categories = ['Все'] + sorted(set(products.values_list('category', flat=True)))
    if category != 'Все':
        products = products.filter(category=category)

    query = request.GET.get('q', '').strip()
    if query:
        # SQLite's icontains only case-folds ASCII, so "Латте" would not match
        # "латте". Filtering in Python with str.lower() handles Cyrillic (and
        # any Unicode) correctly, and the menu is small enough for this to be cheap.
        q_lower = query.lower()
        products = [
            p for p in products
            if q_lower in p.name.lower() or q_lower in (p.description or '').lower()
        ]

    return render(request, 'cafe/menu.html', {
        'products': products,
        'categories': categories,
        'active_category': category,
        'query': query,
    })


# --------------------------------------------------------------------------
# Auth
# --------------------------------------------------------------------------

def register_view(request):
    if request.user.is_authenticated:
        return redirect('home')
    form = RegisterForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        data = form.cleaned_data
        user = User.objects.create(
            username=data['username'],
            first_name=data['name'],
            email=data['email'],
            password=make_password(data['password']),
        )
        user.profile.phone = data['phone']
        user.profile.save()
        login(request, user)
        messages.success(request, f'Добро пожаловать, {data["name"]}!')
        return redirect('home')
    return render(request, 'cafe/register.html', {'form': form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect('admin_products' if request.user.is_staff else 'home')
    form = LoginForm(request.POST or None)
    error = None
    if request.method == 'POST' and form.is_valid():
        username = form.cleaned_data['username'].strip().lower()
        password = form.cleaned_data['password']
        user = authenticate(request, username=username, password=password)
        if user is None:
            error = 'Неверный логин или пароль'
        else:
            login(request, user)
            if user.is_staff:
                messages.success(request, 'Добро пожаловать в панель администратора')
                return redirect('admin_products')
            messages.success(request, f'С возвращением, {user.first_name or user.username}!')
            return redirect('home')
    return render(request, 'cafe/login.html', {'form': form, 'error': error})


def logout_view(request):
    logout(request)
    messages.info(request, 'Вы вышли из аккаунта')
    return redirect('home')


# --------------------------------------------------------------------------
# Cart (kept in the session) + checkout / payment
# --------------------------------------------------------------------------

def _get_cart(request):
    return request.session.setdefault('cart', {})


def _cart_items(request):
    cart = _get_cart(request)
    items = []
    total = 0
    for pid, qty in cart.items():
        try:
            product = Product.objects.get(pk=pid)
        except Product.DoesNotExist:
            continue
        line_total = product.price * qty
        total += line_total
        items.append({'product': product, 'qty': qty, 'line_total': line_total})
    return items, total


@require_POST
def cart_add(request, product_id):
    cart = _get_cart(request)
    key = str(product_id)
    cart[key] = cart.get(key, 0) + 1
    request.session.modified = True
    messages.success(request, 'Добавлено в заказ')
    return redirect(request.POST.get('next') or 'menu')


@require_POST
def cart_update(request, product_id):
    cart = _get_cart(request)
    key = str(product_id)
    action = request.POST.get('action')
    if key in cart:
        if action == 'inc':
            cart[key] += 1
        elif action == 'dec':
            cart[key] -= 1
            if cart[key] <= 0:
                del cart[key]
    request.session.modified = True
    return redirect('cart')


def cart_view(request):
    items, total = _cart_items(request)
    return render(request, 'cafe/cart.html', {'items': items, 'total': total})


@login_required
def checkout_view(request):
    items, total = _cart_items(request)
    if not items:
        messages.info(request, 'Ваша корзина пуста')
        return redirect('menu')
    profile = request.user.profile

    if request.method == 'POST':
        delivery_type = request.POST.get('delivery_type', 'courier')
        address = request.POST.get('address', '').strip()
        if delivery_type == 'courier' and not address:
            messages.error(request, 'Укажите адрес доставки')
            return redirect('checkout')

        use_saved = request.POST.get('use_saved') == '1' and profile.has_card
        card_form = SavedCardCvcForm(request.POST) if use_saved else NewCardForm(request.POST)

        if card_form.is_valid():
            if not use_saved:
                data = card_form.cleaned_data
                profile.card_brand = detect_brand(data['card_number'])
                profile.card_last4 = data['card_number'][-4:]
                profile.card_exp_month, profile.card_exp_year = data['expiry'].split('/')
                profile.card_holder = data['holder']
                profile.save()

            order = Order.objects.create(
                user=request.user,
                delivery_type=delivery_type,
                address=address if delivery_type == 'courier' else 'Самовывоз в кофейне',
                total=total,
                status='paid',
                card_used=profile.card_display,
            )
            for it in items:
                OrderItem.objects.create(
                    order=order, product=it['product'], name=it['product'].name,
                    price=it['product'].price, qty=it['qty'],
                )
            request.session['cart'] = {}
            request.session.modified = True
            messages.success(request, 'Оплата прошла успешно — заказ оформлен!')
            return redirect('profile_orders')
        else:
            return render(request, 'cafe/checkout.html', {
                'items': items, 'total': total, 'profile': profile,
                'card_form': card_form, 'use_saved': use_saved,
                'delivery_type': delivery_type, 'address': address,
            })

    new_card_form = NewCardForm()
    saved_card_form = SavedCardCvcForm()
    force_new = request.session.pop('force_new_card', False)
    use_saved = profile.has_card and not force_new
    return render(request, 'cafe/checkout.html', {
        'items': items, 'total': total, 'profile': profile,
        'card_form': saved_card_form if use_saved else new_card_form,
        'use_saved': use_saved,
        'delivery_type': 'courier', 'address': profile.address,
    })


@login_required
@require_POST
def use_other_card(request):
    request.session['force_new_card'] = True
    return redirect('checkout')


# --------------------------------------------------------------------------
# Booking
# --------------------------------------------------------------------------

@login_required
def booking_view(request):
    form = BookingForm(request.POST or None, initial={'date': date.today() + timedelta(days=1), 'guests': 2})
    if request.method == 'POST' and form.is_valid():
        booking = form.save(commit=False)
        booking.user = request.user
        booking.save()
        messages.success(request, f'Столик {booking.table} забронирован на {booking.date} в {booking.time}')
        return redirect('booking')
    return render(request, 'cafe/booking.html', {'form': form, 'tables': TABLES})


def booked_tables_api(request):
    booking_date = request.GET.get('date', '')
    booking_time = request.GET.get('time', '')
    if not booking_date or not booking_time:
        return JsonResponse({'booked': []})
    booked = list(
        Booking.objects.filter(date=booking_date, time=booking_time, status='confirmed')
        .values_list('table', flat=True)
    )
    return JsonResponse({'booked': booked})


# --------------------------------------------------------------------------
# Profile (separate pages: data / orders / bookings)
# --------------------------------------------------------------------------

@login_required
def profile_view(request):
    profile = request.user.profile
    if request.method == 'POST':
        if 'avatar' in request.FILES:
            avatar_form = AvatarForm(request.POST, request.FILES, instance=profile)
            if avatar_form.is_valid():
                avatar_form.save()
                messages.success(request, 'Аватар обновлён')
            return redirect('profile')
        form = ProfileForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            request.user.first_name = form.cleaned_data['name']
            request.user.email = form.cleaned_data['email']
            request.user.save()
            messages.success(request, 'Профиль обновлён')
            return redirect('profile')
    else:
        form = ProfileForm(instance=profile, initial={
            'name': request.user.first_name, 'email': request.user.email,
        })
    return render(request, 'cafe/profile.html', {'form': form, 'profile': profile})


@login_required
def profile_orders(request):
    orders = request.user.orders.all().prefetch_related('items')
    return render(request, 'cafe/profile_orders.html', {'orders': orders})


@login_required
@require_POST
def repeat_order(request, pk):
    order = get_object_or_404(Order, pk=pk, user=request.user)
    cart = _get_cart(request)
    added, skipped = 0, 0
    for item in order.items.all():
        if item.product and item.product.is_active:
            key = str(item.product_id)
            cart[key] = cart.get(key, 0) + item.qty
            added += 1
        else:
            skipped += 1
    request.session.modified = True
    if added:
        msg = f'Добавили {added} поз. из заказа ORD-{order.id} в корзину.'
        if skipped:
            msg += f' {skipped} поз. больше нет в меню и пропущены.'
        messages.success(request, msg)
        return redirect('cart')
    messages.error(request, 'Ни одной позиции из этого заказа больше нет в меню')
    return redirect('profile_orders')


@login_required
def order_status_api(request, pk):
    order = get_object_or_404(Order, pk=pk, user=request.user)
    return JsonResponse({
        'status': order.status,
        'status_display': order.get_status_display(),
        'css': order.status_css,
    })


@login_required
def profile_bookings(request):
    bookings = request.user.bookings.all()
    return render(request, 'cafe/profile_bookings.html', {'bookings': bookings})


# --------------------------------------------------------------------------
# Customer support chat
# --------------------------------------------------------------------------

@login_required
def support_view(request):
    if request.user.is_staff:
        return redirect('admin_support')
    form = ChatMessageForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        ChatMessage.objects.create(
            customer=request.user, sender='user',
            text=form.cleaned_data['text'],
        )
        return redirect('support')
    ChatMessage.objects.filter(customer=request.user, sender='admin', read_by_user=False).update(read_by_user=True)
    thread = request.user.chat_messages.all()
    return render(request, 'cafe/support.html', {'thread': thread, 'form': form})


@login_required
def unread_count_api(request):
    if request.user.is_staff:
        count = ChatMessage.objects.filter(sender='user', read_by_admin=False).count()
    else:
        count = ChatMessage.objects.filter(customer=request.user, sender='admin', read_by_user=False).count()
    return JsonResponse({'count': count})


# --------------------------------------------------------------------------
# Admin dashboard — completely separate template set, staff-only
# --------------------------------------------------------------------------

@user_passes_test(is_admin, login_url='login')
def admin_products(request):
    products = Product.objects.all().prefetch_related('images')
    return render(request, 'cafe/admin_products.html', {'products': products})


@user_passes_test(is_admin, login_url='login')
def admin_product_form(request, pk=None):
    product = get_object_or_404(Product, pk=pk) if pk else None
    form = ProductForm(request.POST or None, request.FILES or None, instance=product)
    if request.method == 'POST':
        if 'delete' in request.POST and product:
            product.delete()
            messages.success(request, 'Товар удалён')
            return redirect('admin_products')

        for image_id in request.POST.getlist('delete_image'):
            ProductImage.objects.filter(pk=image_id, product=product).delete()

        if form.is_valid():
            product = form.save()
            uploaded = form.cleaned_data.get('images') or []
            start_order = product.images.count()
            for i, f in enumerate(uploaded):
                ProductImage.objects.create(product=product, image=f, order=start_order + i)
            messages.success(request, 'Товар сохранён')
            return redirect('admin_products')
        elif product:
            # image deletion happened but the rest of the form was invalid — reload cleanly
            return redirect('admin_product_edit', pk=product.pk)
    categories = sorted(set(Product.objects.values_list('category', flat=True)))
    return render(request, 'cafe/admin_product_form.html', {
        'form': form, 'product': product, 'categories': categories,
    })


@user_passes_test(is_admin, login_url='login')
def admin_employees(request):
    employees = list(Employee.objects.all())
    total_revenue = Order.objects.exclude(status='cancelled').aggregate(total=Sum('total'))['total'] or 0
    total_revenue = Decimal(total_revenue)
    for e in employees:
        safe_percent = max(Decimal(0), min(e.commission_percent, Decimal(100)))
        e.earned = (safe_percent / Decimal(100)) * total_revenue
    return render(request, 'cafe/admin_employees.html', {
        'employees': employees, 'total_revenue': total_revenue,
    })


@user_passes_test(is_admin, login_url='login')
def admin_employee_form(request, pk=None):
    employee = get_object_or_404(Employee, pk=pk) if pk else None
    form = EmployeeForm(request.POST or None, instance=employee)
    if request.method == 'POST':
        if 'delete' in request.POST and employee:
            employee.delete()
            messages.success(request, 'Сотрудник удалён')
            return redirect('admin_employees')
        if form.is_valid():
            form.save()
            messages.success(request, 'Сотрудник сохранён')
            return redirect('admin_employees')
    return render(request, 'cafe/admin_employee_form.html', {'form': form, 'employee': employee})


@user_passes_test(is_admin, login_url='login')
def admin_orders(request):
    orders = Order.objects.select_related('user').prefetch_related('items').all()
    return render(request, 'cafe/admin_orders.html', {
        'orders': orders, 'statuses': Order._meta.get_field('status').choices,
    })


@user_passes_test(is_admin, login_url='login')
@require_POST
def admin_order_status(request, pk):
    order = get_object_or_404(Order, pk=pk)
    new_status = request.POST.get('status')
    if new_status in dict(Order._meta.get_field('status').choices):
        order.status = new_status
        order.save()
        messages.success(request, 'Статус обновлён')
    return redirect('admin_orders')


@user_passes_test(is_admin, login_url='login')
def admin_bookings(request):
    bookings = Booking.objects.select_related('user').all()
    return render(request, 'cafe/admin_bookings.html', {
        'bookings': bookings, 'statuses': Booking._meta.get_field('status').choices,
    })


@user_passes_test(is_admin, login_url='login')
@require_POST
def admin_booking_status(request, pk):
    booking = get_object_or_404(Booking, pk=pk)
    new_status = request.POST.get('status')
    if new_status in dict(Booking._meta.get_field('status').choices):
        booking.status = new_status
        booking.save()
        messages.success(request, 'Статус брони обновлён')
    return redirect('admin_bookings')


@user_passes_test(is_admin, login_url='login')
def admin_reviews(request):
    reviews = Review.objects.select_related('user').all()
    return render(request, 'cafe/admin_reviews.html', {'reviews': reviews})


@user_passes_test(is_admin, login_url='login')
@require_POST
def admin_review_reply(request, pk):
    review = get_object_or_404(Review, pk=pk)
    reply = request.POST.get('reply', '').strip()
    review.admin_reply = reply
    review.replied_at = timezone.now() if reply else None
    review.save()
    messages.success(request, 'Ответ сохранён')
    return redirect('admin_reviews')


@user_passes_test(is_admin, login_url='login')
def admin_support(request):
    customers = User.objects.filter(chat_messages__isnull=False).distinct()
    conversations = []
    for customer in customers:
        last = customer.chat_messages.last()
        unread = customer.chat_messages.filter(sender='user', read_by_admin=False).count()
        conversations.append({'user': customer, 'last': last, 'unread': unread})
    conversations.sort(key=lambda c: c['last'].created_at, reverse=True)
    return render(request, 'cafe/admin_support.html', {'conversations': conversations})


@user_passes_test(is_admin, login_url='login')
def admin_support_thread(request, username):
    customer = get_object_or_404(User, username=username)
    if request.method == 'POST':
        text = request.POST.get('text', '').strip()
        if text:
            ChatMessage.objects.create(customer=customer, sender='admin', text=text)
        return redirect('admin_support_thread', username=username)
    ChatMessage.objects.filter(customer=customer, sender='user', read_by_admin=False).update(read_by_admin=True)
    customers = User.objects.filter(chat_messages__isnull=False).distinct()
    conversations = []
    for c in customers:
        last = c.chat_messages.last()
        unread = c.chat_messages.filter(sender='user', read_by_admin=False).count()
        conversations.append({'user': c, 'last': last, 'unread': unread})
    conversations.sort(key=lambda c: c['last'].created_at, reverse=True)
    thread = customer.chat_messages.all()
    return render(request, 'cafe/admin_support.html', {
        'conversations': conversations, 'thread': thread, 'active_customer': customer,
    })
