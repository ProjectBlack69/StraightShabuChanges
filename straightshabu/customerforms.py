from django.contrib.auth import get_user_model
from django import forms
from django.contrib.auth.forms import UserCreationForm, PasswordChangeForm
from core.models import UserModule, Customer, SpecialRequest, Feedback, Booking, OnboardService, Passenger, Payment
from django.contrib.auth.hashers import make_password
from django.forms import modelformset_factory
from core.models import Passenger
from django.utils.timezone import now
from datetime import timedelta
from django.core.exceptions import ValidationError

class CustomerSignupForm(forms.ModelForm):
    username = forms.CharField(required=True)
    email = forms.EmailField(required=True)
    password1 = forms.CharField(widget=forms.PasswordInput, required=True)
    password2 = forms.CharField(widget=forms.PasswordInput, required=True)
    date_of_birth = forms.DateField(required=True)

    class Meta:
        model = Customer
        fields = ['phone_number', 'address', 'date_of_birth', 'gender']

    def clean_password2(self):
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        if password1 != password2:
            raise forms.ValidationError("Passwords do not match")
        return password2

    def clean_date_of_birth(self):
        dob = self.cleaned_data.get("date_of_birth")
        today = now().date()
        min_age = today - timedelta(days=80*365)  # Max 80 years old
        max_age = today - timedelta(days=18*365)  # Min 18 years old

        if dob > max_age:
            raise ValidationError("You must be at least 18 years old to sign up.")
        if dob < min_age:
            raise ValidationError("Age cannot be more than 80 years.")

        return dob

    def save(self, commit=True):
        user_data = {
            'username': self.cleaned_data.get('username'),
            'email': self.cleaned_data.get('email'),
            'password': make_password(self.cleaned_data.get('password1')),
            'role': 'customer',
        }
        user = UserModule.objects.create(**user_data)
        customer = super().save(commit=False)
        customer.user = user

        if commit:
            user.save()
            customer.save()
        return customer


# Login Form for User
class LoginForm(forms.Form):
    username = forms.EmailField(label='Email')
    password = forms.CharField(widget=forms.PasswordInput)

# Customer Profile Form

User = get_user_model()

class CustomerProfileForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = ['first_name','last_name','phone_number', 'address', 'date_of_birth', 'gender', 'nationality', 'emergency_contact', 'preferred_language', 'preferred_currency']
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
        }

class UserProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['email', 'username']

class CustomPasswordChangeForm(PasswordChangeForm):
    old_password = forms.CharField(widget=forms.PasswordInput, label='Old Password')
    new_password1 = forms.CharField(widget=forms.PasswordInput, label='New Password')
    new_password2 = forms.CharField(widget=forms.PasswordInput, label='Confirm New Password')

class SpecialRequestForm(forms.ModelForm):
    class Meta:
        model = SpecialRequest
        fields = ['request_type', 'details', 'priority_level']  # Include fields user can edit

class FeedbackForm(forms.ModelForm):
    class Meta:
        model = Feedback
        fields = ['cruise', 'rating', 'comments']
        
        labels = {
            'cruise': 'Select a Cruise',
            'rating': 'Rating (1-5)',
            'comments': 'Your Comments',
        }
        widgets = {
            'cruise': forms.Select(attrs={'class': 'form-control'}),
            'rating': forms.HiddenInput(),  # Hidden input for JavaScript to update
            'comments': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
        }
    
    def clean_rating(self):
        rating = self.cleaned_data.get('rating')
        if rating is None or not (0.5 <= rating <= 5):  # Allow half-star ratings
            raise forms.ValidationError("Rating must be between 0.5 and 5.")
        return rating

class BookingForm(forms.ModelForm):
    LOYALTY_LEVEL_CHOICES = [
        ('Gold', 'Gold'),
        ('Silver', 'Silver'),
        ('Bronze', 'Bronze'),
    ]

    loyalty_level = forms.ChoiceField(choices=LOYALTY_LEVEL_CHOICES, required=False)

    class Meta:
        model = Booking
        fields = [
            'cruise', 'room_type', 'travel_insurance', 
            'loyalty_program_member', 'loyalty_card_number', 
            'loyalty_pass', 'loyalty_level', 'number_of_passengers',
            'onboard_services'
        ]
        widgets = {
            'cruise': forms.Select(attrs={'class': 'booking-select'}),
            'room_type': forms.Select(attrs={'class': 'booking-select'}),
            'travel_insurance': forms.CheckboxInput(attrs={'class': 'booking-checkbox'}),
            'loyalty_program_member': forms.CheckboxInput(attrs={'class': 'booking-checkbox'}),
            'loyalty_card_number': forms.TextInput(attrs={'class': 'booking-input'}),
            'loyalty_pass': forms.TextInput(attrs={'class': 'booking-input'}),
            'loyalty_level': forms.Select(attrs={'class': 'booking-select'}),
            'number_of_passengers': forms.NumberInput(attrs={
                'class': 'booking-input', 
                'min': 1, 
                'id': 'number-of-passengers'
            }),
            'onboard_services': forms.CheckboxSelectMultiple(attrs={'class': 'booking-multiselect'}),
        }


class PassengerForm(forms.ModelForm):
    class Meta:
        model = Passenger
        fields = ['first_name', 'last_name', 'age', 'gender', 'passport_number', 'nationality']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-field-input', 'placeholder': 'Enter first name'}),
            'last_name': forms.TextInput(attrs={'class': 'form-field-input', 'placeholder': 'Enter last name'}),
            'age': forms.NumberInput(attrs={'class': 'form-field-input', 'placeholder': 'Enter age'}),
            'gender': forms.Select(attrs={'class': 'form-field-select'}),
            'passport_number': forms.TextInput(attrs={'class': 'form-field-input', 'placeholder': 'Enter passport number'}),
             'nationality': forms.Select(attrs={'class': 'form-field-select'})
        }

    def clean(self):
        cleaned_data = super().clean()
        errors = {}

        # Check if all fields are filled
        for field in self.Meta.fields:
            if not cleaned_data.get(field):
                errors[field] = f"{field.replace('_', ' ').capitalize()} is required."

        if errors:
            raise forms.ValidationError(errors)
        
        return cleaned_data

PassengerFormSet = modelformset_factory(
    Passenger,
    form=PassengerForm,
    extra=1  # Number of extra blank forms
)