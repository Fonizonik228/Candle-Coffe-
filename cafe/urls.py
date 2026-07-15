from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy

from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('reviews/add/', views.add_review, name='add_review'),
    path('menu/', views.menu_view, name='menu'),

    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    path('password-reset/', auth_views.PasswordResetView.as_view(
        template_name='cafe/password_reset_form.html',
        email_template_name='cafe/password_reset_email.html',
        subject_template_name='cafe/password_reset_subject.txt',
        success_url=reverse_lazy('password_reset_done'),
    ), name='password_reset'),
    path('password-reset/done/', auth_views.PasswordResetDoneView.as_view(
        template_name='cafe/password_reset_done.html',
    ), name='password_reset_done'),
    path('password-reset/confirm/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(
        template_name='cafe/password_reset_confirm.html',
        success_url=reverse_lazy('password_reset_complete'),
    ), name='password_reset_confirm'),
    path('password-reset/complete/', auth_views.PasswordResetCompleteView.as_view(
        template_name='cafe/password_reset_complete.html',
    ), name='password_reset_complete'),

    path('cart/', views.cart_view, name='cart'),
    path('cart/add/<int:product_id>/', views.cart_add, name='cart_add'),
    path('cart/update/<int:product_id>/', views.cart_update, name='cart_update'),
    path('checkout/', views.checkout_view, name='checkout'),
    path('checkout/use-other-card/', views.use_other_card, name='use_other_card'),

    path('booking/', views.booking_view, name='booking'),
    path('api/booked-tables/', views.booked_tables_api, name='booked_tables_api'),

    path('profile/', views.profile_view, name='profile'),
    path('profile/orders/', views.profile_orders, name='profile_orders'),
    path('profile/orders/<int:pk>/repeat/', views.repeat_order, name='repeat_order'),
    path('profile/bookings/', views.profile_bookings, name='profile_bookings'),

    path('support/', views.support_view, name='support'),
    path('api/unread-count/', views.unread_count_api, name='unread_count_api'),
    path('api/order-status/<int:pk>/', views.order_status_api, name='order_status_api'),

    path('admin-panel/', views.admin_products, name='admin_products'),
    path('admin-panel/products/new/', views.admin_product_form, name='admin_product_add'),
    path('admin-panel/products/<int:pk>/', views.admin_product_form, name='admin_product_edit'),
    path('admin-panel/orders/', views.admin_orders, name='admin_orders'),
    path('admin-panel/orders/<int:pk>/status/', views.admin_order_status, name='admin_order_status'),
    path('admin-panel/bookings/', views.admin_bookings, name='admin_bookings'),
    path('admin-panel/bookings/<int:pk>/status/', views.admin_booking_status, name='admin_booking_status'),
    path('admin-panel/employees/', views.admin_employees, name='admin_employees'),
    path('admin-panel/employees/new/', views.admin_employee_form, name='admin_employee_add'),
    path('admin-panel/employees/<int:pk>/', views.admin_employee_form, name='admin_employee_edit'),
    path('admin-panel/reviews/', views.admin_reviews, name='admin_reviews'),
    path('admin-panel/reviews/<int:pk>/reply/', views.admin_review_reply, name='admin_review_reply'),
    path('admin-panel/support/', views.admin_support, name='admin_support'),
    path('admin-panel/support/<str:username>/', views.admin_support_thread, name='admin_support_thread'),
]
