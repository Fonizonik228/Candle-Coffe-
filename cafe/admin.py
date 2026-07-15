from django.contrib import admin

from .models import Product, ProductImage, Order, OrderItem, Booking, ChatMessage, Profile, Employee, Review


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'price', 'roast_level', 'is_active')
    list_filter = ('category', 'is_active')
    search_fields = ('name',)
    inlines = [ProductImageInline]


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'total', 'status', 'delivery_type', 'created_at')
    list_filter = ('status', 'delivery_type')
    inlines = [OrderItemInline]


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'position', 'commission_percent')
    list_filter = ('position',)
    search_fields = ('full_name',)


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ('table', 'user', 'date', 'time', 'guests', 'status')
    list_filter = ('status', 'date')


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('user', 'rating', 'text', 'admin_reply', 'created_at')
    list_filter = ('rating',)


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ('customer', 'sender', 'text', 'created_at', 'read_by_admin', 'read_by_user')
    list_filter = ('sender',)


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'phone', 'card_display')
