import re

from django import forms
from django.contrib.auth.models import User

from .models import Product, Booking, Profile, Employee, Review


class RegisterForm(forms.Form):
    name = forms.CharField(label='Имя', max_length=120)
    username = forms.CharField(label='Логин', max_length=60)
    email = forms.EmailField(label='Email')
    phone = forms.CharField(label='Телефон', max_length=32, required=False)
    password = forms.CharField(label='Пароль', widget=forms.PasswordInput, min_length=4)

    def clean_username(self):
        username = self.cleaned_data['username'].strip().lower()
        if username == 'admin':
            raise forms.ValidationError('Этот логин зарезервирован.')
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError('Такой логин уже занят.')
        return username

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError('Этот email уже используется другим аккаунтом.')
        return email


class LoginForm(forms.Form):
    username = forms.CharField(label='Логин', max_length=60)
    password = forms.CharField(label='Пароль', widget=forms.PasswordInput)


class ProfileForm(forms.ModelForm):
    name = forms.CharField(label='Имя', max_length=150)
    email = forms.EmailField(label='Email', required=False)

    class Meta:
        model = Profile
        fields = ['phone', 'address']
        widgets = {
            'phone': forms.TextInput(attrs={'placeholder': '+7 900 000-00-00'}),
            'address': forms.TextInput(attrs={'placeholder': 'Улица, дом, квартира'}),
        }


class AvatarForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['avatar']


class BookingForm(forms.ModelForm):
    class Meta:
        model = Booking
        fields = ['date', 'time', 'guests', 'phone', 'comment', 'table']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'time': forms.TimeInput(attrs={'type': 'time'}),
            'comment': forms.Textarea(attrs={'rows': 3, 'placeholder': 'У окна, детский стул, день рождения…'}),
            'phone': forms.TextInput(attrs={'placeholder': '+7 900 000-00-00'}),
            'table': forms.HiddenInput(),
        }

    def clean_table(self):
        table = self.cleaned_data['table']
        if not table:
            raise forms.ValidationError('Выберите столик.')
        return table

    def clean(self):
        cleaned_data = super().clean()
        table = cleaned_data.get('table')
        booking_date = cleaned_data.get('date')
        booking_time = cleaned_data.get('time')
        if table and booking_date and booking_time:
            clash = Booking.objects.filter(
                table=table, date=booking_date, time=booking_time, status='confirmed',
            )
            if self.instance.pk:
                clash = clash.exclude(pk=self.instance.pk)
            if clash.exists():
                raise forms.ValidationError(
                    f'Столик {table} уже забронирован на {booking_date.strftime("%d.%m.%Y")} '
                    f'в {booking_time.strftime("%H:%M")}. Выберите другой столик, дату или время.'
                )
        return cleaned_data


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('widget', MultipleFileInput(attrs={'accept': 'image/*', 'multiple': True}))
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            return [single_file_clean(d, initial) for d in data]
        return single_file_clean(data, initial)


class ProductForm(forms.ModelForm):
    images = MultipleFileField(label='Добавить фотографии', required=False)

    class Meta:
        model = Product
        fields = ['name', 'category', 'price', 'description', 'roast_level']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }


class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = ['rating', 'text']
        widgets = {
            'rating': forms.Select(choices=[(5, '★★★★★ Отлично'), (4, '★★★★☆ Хорошо'), (3, '★★★☆☆ Нормально'), (2, '★★☆☆☆ Так себе'), (1, '★☆☆☆☆ Плохо')]),
            'text': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Расскажите, как вам у нас понравилось…'}),
        }


class EmployeeForm(forms.ModelForm):
    class Meta:
        model = Employee
        fields = ['full_name', 'position', 'commission_percent']
        widgets = {
            'full_name': forms.TextInput(attrs={'placeholder': 'Иванова Анна Сергеевна'}),
            'position': forms.TextInput(attrs={'placeholder': 'Бариста'}),
            'commission_percent': forms.NumberInput(attrs={'min': 0, 'max': 100, 'step': '0.01'}),
        }


def luhn_valid(number):
    total = 0
    reversed_digits = [int(d) for d in number[::-1]]
    for i, d in enumerate(reversed_digits):
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def detect_brand(number):
    if number.startswith('4'):
        return 'Visa'
    if re.match(r'^5[1-5]', number) or re.match(r'^2(2[2-9]\d|2[3-9]\d|[3-6]\d\d|7[01]\d|720)', number):
        return 'Mastercard'
    if number.startswith('2'):
        return 'МИР'
    return 'Карта'


class NewCardForm(forms.Form):
    card_number = forms.CharField(label='Номер карты', max_length=23)
    expiry = forms.CharField(label='Срок действия (ММ/ГГ)', max_length=5)
    cvc = forms.CharField(label='CVC', max_length=4, widget=forms.PasswordInput)
    holder = forms.CharField(label='Имя держателя карты', max_length=120)

    def clean_card_number(self):
        raw = re.sub(r'\s+', '', self.cleaned_data['card_number'])
        if not re.match(r'^\d{13,19}$', raw) or not luhn_valid(raw):
            raise forms.ValidationError('Проверьте номер карты.')
        return raw

    def clean_expiry(self):
        expiry = self.cleaned_data['expiry'].strip()
        if not re.match(r'^(0[1-9]|1[0-2])/\d{2}$', expiry):
            raise forms.ValidationError('Срок действия в формате ММ/ГГ.')
        return expiry

    def clean_cvc(self):
        cvc = self.cleaned_data['cvc'].strip()
        if not re.match(r'^\d{3,4}$', cvc):
            raise forms.ValidationError('Проверьте CVC.')
        return cvc


class SavedCardCvcForm(forms.Form):
    cvc = forms.CharField(label='CVC', max_length=4, widget=forms.PasswordInput)

    def clean_cvc(self):
        cvc = self.cleaned_data['cvc'].strip()
        if not re.match(r'^\d{3,4}$', cvc):
            raise forms.ValidationError('Проверьте CVC.')
        return cvc


class ChatMessageForm(forms.Form):
    text = forms.CharField(label='', widget=forms.TextInput(attrs={'placeholder': 'Напишите сообщение…'}))
