from .models import ChatMessage


def site_context(request):
    cart = request.session.get('cart', {})
    cart_count = sum(cart.values()) if cart else 0

    unread_chat = 0
    unread_support_total = 0
    if request.user.is_authenticated:
        if request.user.is_staff:
            unread_support_total = ChatMessage.objects.filter(sender='user', read_by_admin=False).count()
        else:
            unread_chat = ChatMessage.objects.filter(
                customer=request.user, sender='admin', read_by_user=False
            ).count()

    return {
        'cart_count': cart_count,
        'unread_chat': unread_chat,
        'unread_support_total': unread_support_total,
    }
