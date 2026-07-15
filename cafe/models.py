from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models


class Profile(models.Model):
    """Extra data attached to every registered user (customer or admin)."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    phone = models.CharField('Телефон', max_length=32, blank=True)
    address = models.CharField('Адрес доставки', max_length=255, blank=True)
    avatar = models.ImageField('Аватар', upload_to='avatars/', blank=True, null=True)

    # Saved card — only non-sensitive data is ever stored (never the CVC).
    card_brand = models.CharField(max_length=20, blank=True)
    card_last4 = models.CharField(max_length=4, blank=True)
    card_exp_month = models.CharField(max_length=2, blank=True)
    card_exp_year = models.CharField(max_length=2, blank=True)
    card_holder = models.CharField(max_length=120, blank=True)

    def __str__(self):
        return f'Профиль {self.user.username}'

    @property
    def has_card(self):
        return bool(self.card_last4)

    @property
    def card_display(self):
        if not self.has_card:
            return ''
        return f'{self.card_brand} •••• {self.card_last4}'


class Product(models.Model):
    """A single menu item (coffee, dessert, breakfast, etc.)."""
    name = models.CharField('Название', max_length=120)
    category = models.CharField('Категория', max_length=80)
    description = models.TextField('Описание', blank=True)
    price = models.PositiveIntegerField('Цена, ₽')
    roast_level = models.PositiveSmallIntegerField(
        'Уровень обжарки (0 — не показывать)', default=0
    )
    is_active = models.BooleanField('Показывать в меню', default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['category', 'name']
        verbose_name = 'Товар'
        verbose_name_plural = 'Товары'

    def __str__(self):
        return self.name

    @property
    def roast_range(self):
        return range(1, 6)


class ProductImage(models.Model):
    """One photo belonging to a product's rotating gallery."""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField('Фото', upload_to='products/')
    order = models.PositiveIntegerField('Порядок', default=0)

    class Meta:
        ordering = ['order', 'id']
        verbose_name = 'Фото товара'
        verbose_name_plural = 'Фото товара'

    def __str__(self):
        return f'Фото {self.product.name} #{self.order}'


TABLES = [
    {'id': 'T1', 'seats': 2}, {'id': 'T2', 'seats': 2},
    {'id': 'T3', 'seats': 4}, {'id': 'T4', 'seats': 4},
    {'id': 'T5', 'seats': 4}, {'id': 'T6', 'seats': 6},
    {'id': 'T7', 'seats': 2}, {'id': 'T8', 'seats': 8},
]

DELIVERY_CHOICES = [
    ('courier', 'Доставка курьером'),
    ('pickup', 'Самовывоз'),
]

ORDER_STATUSES = [
    ('paid', 'Оплачен'),
    ('cooking', 'Готовится'),
    ('transit', 'В пути'),
    ('ready', 'Готов к выдаче'),
    ('done', 'Выполнен'),
    ('cancelled', 'Отменён'),
]

STATUS_CSS_CLASS = {
    'paid': 'status-new',
    'cooking': 'status-cooking',
    'transit': 'status-transit',
    'ready': 'status-ready',
    'done': 'status-done',
    'cancelled': 'status-cancelled',
}


STEP_LABELS = {
    'paid': 'Оплачен',
    'cooking': 'Готовится',
    'transit': 'В пути',
    'ready': 'Готов к выдаче',
    'done': 'Выполнен',
}


class Order(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders')
    delivery_type = models.CharField(max_length=10, choices=DELIVERY_CHOICES)
    address = models.CharField(max_length=255, blank=True)
    total = models.PositiveIntegerField()
    status = models.CharField(max_length=12, choices=ORDER_STATUSES, default='paid')
    card_used = models.CharField(max_length=40, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Заказ'
        verbose_name_plural = 'Заказы'

    def __str__(self):
        return f'Заказ #{self.pk} — {self.user.username}'

    @property
    def status_css(self):
        return STATUS_CSS_CLASS.get(self.status, 'status-new')

    @property
    def tracking_steps(self):
        keys = ['paid', 'cooking', 'transit', 'done'] if self.delivery_type == 'courier' else ['paid', 'cooking', 'ready', 'done']
        return [(k, STEP_LABELS[k]) for k in keys]

    @property
    def tracking_index(self):
        keys = [k for k, _ in self.tracking_steps]
        try:
            return keys.index(self.status)
        except ValueError:
            return -1

    @property
    def is_active_tracking(self):
        return self.status not in ('done', 'cancelled')


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True, related_name='order_items')
    name = models.CharField(max_length=120)
    price = models.PositiveIntegerField()
    qty = models.PositiveIntegerField(default=1)

    def __str__(self):
        return f'{self.name} ×{self.qty}'

    @property
    def line_total(self):
        return self.price * self.qty


BOOKING_STATUSES = [
    ('confirmed', 'Подтверждено'),
    ('cancelled', 'Отменено'),
]


class Booking(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bookings')
    table = models.CharField('Столик', max_length=8)
    date = models.DateField('Дата')
    time = models.TimeField('Время')
    guests = models.CharField('Гостей', max_length=8)
    phone = models.CharField('Телефон', max_length=32)
    comment = models.TextField('Комментарий', blank=True)
    status = models.CharField(max_length=12, choices=BOOKING_STATUSES, default='confirmed')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Бронь'
        verbose_name_plural = 'Брони'

    def __str__(self):
        return f'{self.table} · {self.date} {self.time} — {self.user.username}'


class Employee(models.Model):
    full_name = models.CharField('ФИО', max_length=150)
    position = models.CharField('Должность', max_length=100)
    commission_percent = models.DecimalField(
        'Процент с продаж, %', max_digits=5, decimal_places=2, default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text='От 0 до 100 — заработок не может превышать общую выручку кафе.',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['full_name']
        verbose_name = 'Сотрудник'
        verbose_name_plural = 'Сотрудники'

    def __str__(self):
        return f'{self.full_name} — {self.position}'


class Review(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reviews')
    rating = models.PositiveSmallIntegerField('Оценка', default=5)
    text = models.TextField('Отзыв')
    admin_reply = models.TextField('Ответ кофейни', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    replied_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Отзыв'
        verbose_name_plural = 'Отзывы'

    def __str__(self):
        return f'{self.user.username} · {self.rating}★'

    @property
    def stars(self):
        rating = max(0, min(5, self.rating))
        return '★' * rating + '☆' * (5 - rating)


class ChatMessage(models.Model):
    """One message in the support conversation between a customer and admin.
    `customer` always identifies which conversation the message belongs to,
    even for messages authored by the admin.
    """
    customer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='chat_messages')
    sender = models.CharField(max_length=10, choices=[('user', 'Покупатель'), ('admin', 'Админ')])
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    read_by_admin = models.BooleanField(default=False)
    read_by_user = models.BooleanField(default=False)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f'{self.sender}: {self.text[:30]}'
