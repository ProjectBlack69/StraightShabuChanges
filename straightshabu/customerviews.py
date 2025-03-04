from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.urls import reverse
from django.contrib.auth import login, authenticate
from django.contrib import messages
from core.models import UserModule, Customer, SpecialRequest, Cruise, Feedback, Booking, OnboardService, Passenger, CustomerBooking, LoyaltyProgram, Payment, Invoice, Notification, RefundRequest, ContactMessage
from django.http import HttpResponse, HttpResponseRedirect
from django.template.loader import get_template
from customer.forms import CustomerSignupForm, LoginForm, CustomerProfileForm, CustomPasswordChangeForm, UserProfileForm, SpecialRequestForm, FeedbackForm, PassengerFormSet, PassengerForm
from django.views.decorators.http import require_POST
from django.contrib.auth import logout, update_session_auth_hash, get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm
from django.shortcuts import render, redirect
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth import get_user_model 
import json
from django.forms import modelformset_factory
from django.views.decorators.csrf import csrf_exempt, csrf_protect
import logging
import random, string
from decimal import Decimal
from django.core.exceptions import ObjectDoesNotExist
import uuid
import io
import qrcode
from io import BytesIO
from django.template.loader import render_to_string
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import tempfile
from PIL import Image
import os
import base64
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor
import qrcode
from io import BytesIO
import tempfile
import os
from decimal import Decimal
from datetime import date


def customer_homepage(request):
    return render(request, 'customer/homepage.html')

def customer_about(request):
    return render(request, 'customer/custabout.html')

def services(request):
    return render(request, 'customer/service.html')

def destinations(request):
    return render(request, 'customer/destination.html')

def explore_cruises(request):
    cruises = Cruise.objects.all()  # Get all cruises
    context = {
        'cruises': cruises,
    }
    return render(request, 'customer/explore_cruises.html', context )

def restaurant_access_denied(request):
    return render(request, 'customer/rest-denied.html')

@login_required
def booking_confirmed(request):
    return render(request, 'customer/booking_confirmed.html')

def book_now(request):
    if request.user.is_authenticated:
        if request.user.role != "customer":  
            logout(request)  # Log out non-customer users
            return redirect('book_now')  # Redirect to the booking page after logout
        
        return HttpResponseRedirect('/customer/')  # Allow customers to proceed

    return render(request, 'customer/book_now.html')


def get_login_status(request):
    if request.user.is_authenticated:
        role = request.user.role if hasattr(request.user, 'role') else 'customer'  # Assuming default is 'customer'
        return JsonResponse({
            'is_logged_in': True,
            'role': role
        })
    else:
        return JsonResponse({
            'is_logged_in': False,
            'role': None
        })

@require_POST
def customer_signup(request):
    form = CustomerSignupForm(request.POST)
    
    if form.is_valid():
        customer = form.save(commit=False)
        user = customer.user  # Assuming customer.user is correctly set up to reference UserModule
        user.save()  # Save the User instance
        customer.save()  # Save the Customer instance

        return JsonResponse({'status': 'success', 'message': 'Signup successful!'})
    
    else:
        # Extract error messages for each field
        error_messages = {field: error.get_json_data() for field, error in form.errors.items()}

        return JsonResponse({
            'status': 'error',
            'message': 'Signup failed. Please check the errors.',
            'errors': error_messages  # Send structured error messages
        }, status=400)
    
    
@csrf_exempt
@require_POST
def submit_contact_form(request):
    try:
        data = json.loads(request.body)
        contact_message = ContactMessage.objects.create(
            name=data.get('name'),
            email=data.get('email'),
            message=data.get('message')
        )
        return JsonResponse({'success': True, 'message': 'Form submitted successfully!'}, status=200)
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=400)

                        
@require_POST
def login_view(request):
    try:
        data = json.loads(request.body)  # Parse JSON data from request body
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON.'}, status=400)

    form = LoginForm(data)

    if form.is_valid():
        email = form.cleaned_data['username']  # Assuming 'username' is the email field
        password = form.cleaned_data['password']

        user = authenticate(request, username=email, password=password)

        if user is not None and user.is_active:
            if user.role == 'customer':  # Only allow customers to log in
                login(request, user)
                return JsonResponse({'status': 'success', 'message': "Login successful!"})
            else:
                return JsonResponse({'status': 'error', 'message': "Access denied. Only customers can log in."}, status=403)
        else:
            return JsonResponse({'status': 'error', 'message': "Login failed. Check your email and password."})

    # Form is not valid
    errors = {field: error[0] for field, error in form.errors.items()}  # Extract specific error messages
    return JsonResponse({'status': 'error', 'message': "Validation error", 'errors': errors})

# Render the forgot password page
def forgot_password(request):
    return render(request, 'customer/forgot_password.html')

# Send password reset email
@csrf_exempt
def send_reset_email(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            email = data.get("email")

            if not email:
                return JsonResponse({"success": False, "message": "Email is required."})

            user = get_object_or_404(UserModule, email=email)
            customer = Customer.objects.filter(user=user).first()

            if not customer:
                return JsonResponse({"success": False, "message": "No associated customer account found."})

            token = default_token_generator.make_token(user)
            reset_link = f"http://127.0.0.1:8000/customer/reset-password/{customer.pk}/{token}/"

            send_mail(
                "Password Reset Request",
                f"Click the link to reset your password: {reset_link}",
                "bscproject3rd@gmail.com",
                [user.email],
            )

            return JsonResponse({"success": True, "message": "Password reset email sent."})

        except json.JSONDecodeError:
            return JsonResponse({"success": False, "message": "Invalid JSON format."})

    return JsonResponse({"success": False, "message": "Invalid request method."})

# Handle password reset
@csrf_exempt
def reset_password(request, customer_id, token):
    customer = get_object_or_404(Customer, pk=customer_id)

    if request.method == "GET":
        return render(request, "customer/reset_password_form.html", {"customer_id": customer_id, "token": token})

    elif request.method == "POST":
        data = json.loads(request.body)
        new_password = data.get("new_password")
        confirm_password = data.get("confirm_password")

        if not new_password or not confirm_password:
            return JsonResponse({"success": False, "message": "Both password fields are required."})

        if new_password != confirm_password:
            return JsonResponse({"success": False, "message": "Passwords do not match."})

        if not default_token_generator.check_token(customer.user, token):
            return JsonResponse({"success": False, "message": "Invalid or expired reset link."})

        # Update the password in `UserModule`
        customer.user.set_password(new_password)
        customer.user.save()

        return JsonResponse({"success": True, "message": "Password reset successful. You can now log in."})

    return JsonResponse({"success": False, "message": "Invalid request method."})

@require_POST
def logout_view(request):
    logout(request)  # Log out the user
    return JsonResponse({'status': 'success', 'message': "Logged out successfully."})

MEMBERSHIP_TIERS = [
    {
        'id': 1,
        'name': 'Bronze',
        'price': 19.99,
        'description': 'Start your journey with basic perks and discounts.',
    },
    {
        'id': 2,
        'name': 'Silver',
        'price': 49.99,
        'description': 'Enjoy Bronze benefits plus faster support and bonuses.',
    },
    {
        'id': 3,
        'name': 'Gold',
        'price': 99.99,
        'description': 'Access VIP events, premium upgrades, and Silver perks.',
    },
    {
        'id': 4,
        'name': 'Diamond',
        'price': 199.99,
        'description': 'Experience ultimate luxury, exclusive perks, and top-tier access.',
    },
]



def generate_card_number():
    """Generates a random 12-digit card number."""
    return ''.join(random.choices(string.digits, k=12))

def generate_passcode(username):
    """Generates a passcode based on the username with numbers and symbols."""
    return f"{username}{random.randint(1000, 9999)}@!%"

def purchase_membership(request):
    customer = Customer.objects.get(user=request.user)

    if request.method == 'POST':
        membership_id = request.POST.get('membership')
        membership = next(m for m in MEMBERSHIP_TIERS if m['id'] == int(membership_id))

        # Generate card number and passcode
        card_number = generate_card_number()
        passcode = generate_passcode(request.user.username)
        
        if not customer.loyalty_program:
            # Create a new LoyaltyProgram instance
            loyalty_program = LoyaltyProgram.objects.create(
                customer=customer,
                points=0,  # Initialize points
                level=membership['name'],  # Assign the selected membership level
                loyalty_card_number=card_number,
                password=passcode
            )

            # Link the loyalty program to the customer and set them as a loyalty member
            customer.loyalty_program = loyalty_program
            customer.loyalty_member = True
            customer.save()
        else:
            # If the customer already has a loyalty program, update the level and card
            loyalty_program = customer.loyalty_program
            loyalty_program.level = membership['name']
            loyalty_program.loyalty_card_number = card_number
            loyalty_program.password = passcode
            loyalty_program.save()

        # Return success message with card details in JSON format for modal
        return JsonResponse({
            'status': 'success',
            'message': 'Membership purchased successfully!',
            'card_number': card_number,
            'passcode': passcode,
            'tier': membership['name'],
        })

    return render(request, 'customer/purchase_loyalty_membership.html', {
        'memberships': MEMBERSHIP_TIERS,
        'customer': customer,
    })

@login_required
def loyalty_program_details(request):
    try:
        # Retrieve the customer from the Customer model using the logged-in user's ID
        customer = Customer.objects.get(user=request.user)
    except Customer.DoesNotExist:
        messages.error(request, "Customer profile not found.")
        return redirect('profile')  # Redirect to the profile page if customer is not found

    # Fetch the customer's associated loyalty program
    try:
        loyalty_program = LoyaltyProgram.objects.get(customer=customer)
    except LoyaltyProgram.DoesNotExist:
        loyalty_program = None

    # Render the loyalty program details page
    return render(request, 'customer/loyalty_program.html', {
        'loyalty_program': loyalty_program,
        'customer': customer,
    })

@login_required
def cancel_loyalty_program(request):
    try:
        customer = request.user.customer_profile
        if customer.loyalty_program:
            loyalty_program = customer.loyalty_program
            customer.loyalty_program = None
            customer.loyalty_member = False
            customer.save()

            loyalty_program.delete()

            # Return a JSON response with a success message and redirect URL
            redirect_url = reverse('profile')  # Redirect to the profile page
            return JsonResponse({
                "status": "success",
                "message": "Your loyalty program has been successfully canceled.",
                "redirect_url": redirect_url  # Send the redirect URL to the frontend
            })
        else:
            return JsonResponse({"status": "error", "message": "You are not a member of the loyalty program."})
    except Customer.DoesNotExist:
        return JsonResponse({"status": "error", "message": "Customer profile not found."})


@login_required
def resume_booking(request, booking_id):
    customer = get_object_or_404(Customer, user=request.user)

    # Fetch the booking or return a 404 if not found
    booking = get_object_or_404(Booking, id=booking_id, customer=customer)

    if booking.status == 'Paused':
        # Change the booking status to 'Restarted' when resuming from 'Paused'
        booking.status = 'Restarted'
        booking.save()
        messages.success(request, "Booking resumed! You can now continue your booking process.")
    elif booking.status == 'Pending':
        # If the booking status is already 'Pending', just inform the user
        messages.info(request, "You're already in the process of booking.")
        return redirect('start_booking')  # Redirect to the user's dashboard or any appropriate page
    else:
        # If the booking is in any other state, notify the user
        messages.warning(request, "This booking cannot be resumed at the moment.")
        return redirect('start_booking')  # Redirect to the user's dashboard or any appropriate page

    # Proceed with the next steps ONLY if the status is 'Restarted'
    if booking.status == 'Restarted':
        DEFAULT_PAYMENT_METHOD = 'Credit Card'
        DEFAULT_ROOM_TYPE = 'Economy'

        # Determine the next step in the booking process and redirect accordingly
        if booking.cruise is None:
            messages.info(request, "Please select a cruise to continue.")
            return redirect('select_cruise', booking_id=booking.id)
        elif not booking.passengers.exists():
            messages.info(request, "Please add passengers to your booking.")
            return redirect('add_passenger', booking_id=booking.id)
        elif not booking.onboard_services.exists():
            messages.info(request, "Select additional services for your booking.")
            return redirect('select-services', booking_id=booking.id)
        elif booking.payment_method == DEFAULT_PAYMENT_METHOD and booking.room_type == DEFAULT_ROOM_TYPE:
            print("Redirecting to save-other-details due to default values")
            messages.info(request, "Please provide additional booking details.")
            return redirect('save-other-details', booking_id=booking.id)
        elif booking.total_price is None or booking.total_price <= 0:
            messages.info(request, "Please review your booking summary.")
            return redirect('booking_summary', booking_id=booking.id)
        elif booking.payment_status == 'Unpaid':
            messages.info(request, "Your booking is pending payment.")
            return redirect('payment_page', booking_id=booking.id)
        else:
            messages.success(request, "Your booking is confirmed.")
            return redirect('payment_success', booking_id=booking.id)

@login_required
def start_booking(request):
    customer = get_object_or_404(Customer, user=request.user)

    # Check if the user has a paused booking
    paused_booking = Booking.objects.filter(customer=customer, status='Paused').first()

    if request.method == 'POST':
        action = request.POST.get('action')  # Get the action from the form (resume or delete)
        
        if action == 'resume' and paused_booking:
            # Resume the booking (change status from 'Paused' to 'Restarted')
            paused_booking.status = 'Restarted'
            paused_booking.save()
            messages.success(request, "Booking resumed! You can now continue your booking process.")
            return redirect('resume-booking', booking_id=paused_booking.id)  # Redirect to resume booking
        elif action == 'delete' and paused_booking:
            # Delete the paused booking and redirect to the cruise selection page
            paused_booking.delete()
            messages.success(request, "Your paused booking has been deleted. You can now start a new booking.")
            return redirect('select-cruise')  # Redirect to select cruise page
        else:
            messages.warning(request, "No paused booking found.")
            return redirect('select-cruise')

    return render(request, 'customer/booking/start_booking.html', {'paused_booking': paused_booking})

@login_required
def select_cruise(request, booking_id=None):
    customer = get_object_or_404(Customer, user=request.user)

    if request.method == 'GET':
        # Retrieve all cruises for display
        cruises = Cruise.objects.all()

        context = {
            'cruises': cruises,
            'booking_id': booking_id,
        }
        return render(request, 'customer/booking/select_cruise.html', context)

    elif request.method == 'POST':
        # Handle cruise selection
        try:
            data = json.loads(request.body)
            cruise_id = data.get('cruise_id')

            if not cruise_id:
                return JsonResponse({'error': 'No cruise ID provided'}, status=400)

            cruise = get_object_or_404(Cruise, id=cruise_id)

            # If booking_id exists, resume the booking (if it was paused)
            if booking_id:
                booking = get_object_or_404(Booking, id=booking_id, customer=customer)
                if booking.status == 'Paused':
                    booking.status = 'Restarted'  # Resume the paused booking
                booking.cruise = cruise
                booking.save()
            else:
                # If no booking_id, create a new booking (standard flow)
                # Create a new booking and assign the cruise
                booking = Booking.objects.create(
                    customer=customer,
                    cruise=cruise,  # Ensure cruise is assigned to the booking
                    status='Pending',  # Booking status is 'Pending' initially
                )

            return JsonResponse({
                'cruise_name': cruise.name,
                'status': 'Cruise Selected',
                'booking_id': booking.id,  # Return the booking ID
                'message': 'Your cruise selection has been saved successfully.',
            })

        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    
@csrf_exempt
def update_booking_status(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        booking_id = data.get('booking_id')
        status = data.get('status')

        if booking_id and status:
            try:
                booking = Booking.objects.get(id=booking_id)
                booking.status = status
                booking.save()
                return JsonResponse({'status': 'success'})
            except Booking.DoesNotExist:
                return JsonResponse({'error': 'Booking not found'}, status=404)
        return JsonResponse({'error': 'Invalid data'}, status=400)

@csrf_exempt
def add_passenger(request, booking_id):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'User is not authenticated'}, status=401)

    # Retrieve the customer object linked to the authenticated user
    customer = get_object_or_404(Customer, user=request.user)
    
    # Retrieve the booking object using the booking_id passed in the URL
    booking = get_object_or_404(Booking, id=booking_id)

    # Retrieve all bookings for the customer
    bookings = Booking.objects.filter(customer=customer)

    if booking.status == 'Paused':
        # If the booking is paused, inform the user and prompt them to resume it
        messages.info(request, "Your booking is paused. Please resume your booking.")
        return redirect('resume_booking', booking_id=booking.id)

    if request.method == 'POST':
        formset = PassengerFormSet(request.POST)

        if formset.is_valid():
            passengers = formset.save(commit=False)
            for passenger in passengers:
                passenger.booking = booking
                passenger.save()

            # Update the number of passengers in the booking
            booking.number_of_passengers = booking.passengers.count()
            booking.save()

            return JsonResponse({
                'status': 'success',
                'message': 'Passengers added successfully!',
            })
        else:
            # Collect and return all validation errors from the formset
            errors = formset.errors
            return JsonResponse({
                'status': 'error',
                'message': 'Form validation failed. Please check the details entered.',
                'errors': errors,
            }, status=400)

    # Calculate age from date of birth
    def calculate_age(dob):
        if dob:
            today = date.today()
            return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
        return ''

    # Pre-fill the first passenger form with the authenticated user's details
    customer_data = {
        'first_name': customer.first_name,
        'last_name': customer.last_name,
        'age': calculate_age(customer.date_of_birth),
        'gender': customer.gender,
        'passport_number': '',
        'nationality': customer.nationality,
    }

    formset = PassengerFormSet(
        queryset=Passenger.objects.none(),
        initial=[customer_data]  # Pre-fill the first form
    )

    return render(request, 'customer/booking/add_passenger.html', {
        'formset': formset,
        'bookings': bookings,
        'booking_id': booking_id,
    })

@csrf_exempt
@login_required
def select_services(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id, customer__user=request.user)
    onboard_services = OnboardService.objects.all()

    if booking.status == 'Paused':
        # If booking is paused, prompt the user to resume
        messages.info(request, "Your booking is paused. Please resume your booking.")
        return redirect('resume_booking', booking_id=booking.id)

    if request.method == 'POST':
        try:
            # Parse JSON data
            import json
            data = json.loads(request.body)
            selected_service_ids = data.get('services', [])
            
            # Retrieve selected services
            selected_services = OnboardService.objects.filter(id__in=selected_service_ids)
            
            # Update the booking with the selected services
            booking.onboard_services.set(selected_services)
            booking.save()

            return JsonResponse({
                'status': 'success',
                'message': 'Services selected successfully!',
                'selected_services': selected_service_ids,
                'booking_id': booking.id
            }, status=200)
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    
    # For GET requests, render the template with services
    return render(request, 'customer/booking/select_services.html', {
        'onboard_services': onboard_services,
        'booking_id': booking_id
    })

@login_required
def save_other_details(request, booking_id):
    # Fetch the booking by its ID and ensure the user is the customer
    booking = get_object_or_404(Booking, id=booking_id, customer__user=request.user)

    # Check if the booking status is 'Paused'
    if booking.status == 'Paused':
        # If booking is paused, prompt the user to resume
        messages.info(request, "Your booking is paused. Please resume your booking.")
        return redirect('resume_booking', booking_id=booking.id)

    if request.method == 'POST':
        try:
            data = json.loads(request.body)  # Parse JSON body
        except json.JSONDecodeError:
            return JsonResponse({'status': 'error', 'message': 'Invalid JSON data'}, status=400)

        # Extract fields from the request
        payment_method = data.get('payment_method', 'Credit Card')  # Default to 'Credit Card'
        travel_insurance = data.get('travel_insurance', 'off') == 'on'  # Convert "on" to True
        room_type = data.get('room_type', booking.room_type)
        special_request = data.get('special_request', '').strip() or None

        # Loyalty program details
        loyalty_program_member = data.get('loyalty_program_member', 'off') == 'on'
        loyalty_card_number = data.get('loyalty_card_number', '').strip()
        loyalty_pass = data.get('loyalty_pass', '').strip()
        loyalty_level = data.get('loyalty_level', '').strip()  # Assume it is a dropdown field

        # Validate loyalty program details if loyalty program is selected
        if loyalty_program_member:
            loyalty_program = getattr(booking.customer, 'loyalty_program', None)
            if not loyalty_program:
                return JsonResponse({
                    'status': 'error',
                    'message': 'You are not enrolled in any loyalty program.'
                }, status=400)

            if not (
                loyalty_program.loyalty_card_number == loyalty_card_number and
                loyalty_program.password == loyalty_pass and
                loyalty_program.level == loyalty_level
            ):
                return JsonResponse({
                    'status': 'error',
                    'message': 'Loyalty program details do not match our records.'
                }, status=400)

        # Update booking details
        booking.payment_method = payment_method
        booking.travel_insurance = travel_insurance
        booking.room_type = room_type
        booking.special_request = special_request
        booking.loyalty_program_member = loyalty_program_member
        booking.loyalty_card_number = loyalty_card_number if loyalty_program_member else None
        booking.loyalty_pass = loyalty_pass if loyalty_program_member else None
        booking.loyalty_level = loyalty_level if loyalty_program_member else None
        booking.save()

        return JsonResponse({
            'status': 'success',
            'message': 'Other details updated successfully!',
            'redirect_url': reverse('booking_summary', args=[booking_id])
        }, status=200)

    # For GET requests, render the 'other_details.html' template
    return render(request, 'customer/booking/other_details.html', {
        'booking': booking,
        'booking_id': booking_id,
    })


def get_passengers(request, booking_id):
    try:
        # Retrieve the passengers for the specified booking
        passengers = Passenger.objects.filter(booking_id=booking_id)
        
        # Prepare the data to return as JSON
        passengers_data = [{
            'id': passenger.id,
            'first_name': passenger.first_name,
            'last_name': passenger.last_name
        } for passenger in passengers]
        
        return JsonResponse({'passengers': passengers_data})
    
    except Passenger.DoesNotExist:
        return JsonResponse({'error': 'No passengers found for this booking'}, status=404)

def get_passenger_details(request, passenger_id):
    try:
        # Retrieve the passenger object by ID
        passenger = Passenger.objects.get(id=passenger_id)
        
        # Prepare the passenger details to return as JSON
        passenger_data = {
            'first_name': passenger.first_name,
            'last_name': passenger.last_name,
            'age': passenger.age,
            'gender': passenger.gender,
            'passport_number': passenger.passport_number,
            'nationality': passenger.nationality,
        }
        
        return JsonResponse(passenger_data)
    
    except Passenger.DoesNotExist:
        return JsonResponse({'error': 'Passenger not found'}, status=404)

def update_passenger(request, passenger_id):
    passenger = get_object_or_404(Passenger, id=passenger_id)

    if request.method == 'POST':
        form = PassengerForm(request.POST, instance=passenger)
        
        if form.is_valid():
            form.save()  # Save the updated passenger details to the database
            return JsonResponse({'success': True, 'message': 'Passenger details updated successfully!'})
        else:
            return JsonResponse({'success': False, 'errors': form.errors})
    
    return JsonResponse({'success': False, 'message': 'Invalid request.'})


def booking_summary(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id)
    passengers = Passenger.objects.filter(booking=booking)
    form = PassengerForm()

    if booking.status == 'Paused':
        booking.status = 'Restarted'
        booking.save()
        messages.success(request, "Booking resumed! You can now continue your booking process.")

    if booking.status == 'Restarted':
        DEFAULT_PAYMENT_METHOD = 'Credit Card'
        DEFAULT_ROOM_TYPE = 'Economy'

        if booking.cruise is None:
            messages.info(request, "Please select a cruise to continue.")
            return redirect('select_cruise', booking_id=booking.id)
        elif not booking.passengers.exists():
            messages.info(request, "Please add passengers to your booking.")
            return redirect('add_passenger', booking_id=booking.id)
        elif not booking.onboard_services.exists():
            messages.info(request, "Select additional services for your booking.")
            return redirect('select-services', booking_id=booking.id)
        elif booking.payment_method == DEFAULT_PAYMENT_METHOD and booking.room_type == DEFAULT_ROOM_TYPE:
            messages.info(request, "Please provide additional booking details.")
            return redirect('save-other-details', booking_id=booking.id)

    # **Calculate Prices Dynamically**
    num_passengers = booking.passengers.count()
    base_price = Decimal(booking.cruise.price_per_person) * Decimal(num_passengers)

    room_price = Decimal(booking.cruise.price_per_room_type.get(booking.room_type, 100))  # Default room price = 100
    services_total_price = sum(Decimal(service.price) for service in booking.onboard_services.all())

    travel_insurance_price = (base_price + room_price + services_total_price) * Decimal(0.05) if booking.travel_insurance else Decimal(0)
    tax = (base_price + room_price + services_total_price + travel_insurance_price) * Decimal(0.10)

    loyalty_discount = Decimal(0)
    if booking.loyalty_program_member and hasattr(booking.customer, 'loyalty_program'):
        loyalty_discount = Decimal(booking.customer.loyalty_program.points) * Decimal(0.25)

    discount = Decimal(0)
    for passenger in booking.passengers.all():
        if passenger.age <= 12:  
            discount += base_price * Decimal(0.15)  # Child discount
        elif passenger.age >= 60:  
            discount += base_price * Decimal(0.10)  # Elderly discount

    total_price = base_price + room_price + services_total_price + travel_insurance_price + tax - loyalty_discount - discount

    if request.method == 'POST':
        booking.status = 'Confirmed'
        booking.payment_status = 'Pending'
        booking.save()
        return redirect('payment_page', booking_id=booking.id)

    context = {
        'passengers': passengers,
        'booking': booking,
        'form': form,
        'total_price': total_price.quantize(Decimal('0.001')),
        'base_price': base_price.quantize(Decimal('0.001')),
        'room_price': room_price.quantize(Decimal('0.001')),
        'services_total_price': services_total_price.quantize(Decimal('0.001')),
        'travel_insurance_price': travel_insurance_price.quantize(Decimal('0.001')),
        'tax': tax.quantize(Decimal('0.001')),
        'loyalty_discount': loyalty_discount.quantize(Decimal('0.001')),
        'discount': discount.quantize(Decimal('0.001')),
    }
    return render(request, 'customer/booking/booking_summary.html', context)

@csrf_exempt
def passenger(request, booking_id):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'User is not authenticated'}, status=401)

    # Retrieve the customer object linked to the authenticated user
    customer = get_object_or_404(Customer, user=request.user)

    # Retrieve the booking object using the booking_id passed in the URL
    booking = get_object_or_404(Booking, id=booking_id)

    # Retrieve all bookings for the customer
    bookings = Booking.objects.filter(customer=customer)

    if request.method == 'POST':
        formset = PassengerFormSet(request.POST)

        if formset.is_valid():
            passengers = formset.save(commit=False)
            for passenger in passengers:
                passenger.booking = booking
                passenger.save()

            # Update the number of passengers in the booking
            booking.number_of_passengers = booking.passengers.count()
            booking.save()

            return JsonResponse({
                'status': 'success',
                'message': 'Passengers added successfully!',
            })
        else:
            # Collect and return all validation errors from the formset
            errors = formset.errors
            return JsonResponse({
                'status': 'error',
                'message': 'Form validation failed. Please check the details entered.',
                'errors': errors,
            }, status=400)

    # No prefilled data in forms
    formset = PassengerFormSet(queryset=Passenger.objects.none())

    return render(request, 'customer/redirect/passenger.html', {
        'formset': formset,
        'bookings': bookings,
        'booking_id': booking_id,
    })

@login_required
def update_booking_details(request, booking_id):
    """
    Updates existing booking details.
    """
    # Fetch the booking by its ID and ensure the user is the customer
    booking = get_object_or_404(Booking, id=booking_id, customer__user=request.user)

    if request.method == 'POST':
        try:
            data = json.loads(request.body)  # Parse JSON body
        except json.JSONDecodeError:
            return JsonResponse({'status': 'error', 'message': 'Invalid JSON data'}, status=400)

        # Update only provided fields; leave others unchanged
        if 'payment_method' in data:
            booking.payment_method = data['payment_method']
        if 'travel_insurance' in data:
            booking.travel_insurance = data['travel_insurance'] == 'on'  # Convert "on" to True
        if 'room_type' in data:
            booking.room_type = data['room_type']
        if 'special_request' in data:
            booking.special_request = data['special_request'].strip() or None
        if 'loyalty_program_member' in data:
            booking.loyalty_program_member = data['loyalty_program_member'] == 'on'

            # Handle loyalty program details if applicable
            if booking.loyalty_program_member:
                loyalty_program = getattr(booking.customer, 'loyalty_program', None)
                if not loyalty_program:
                    return JsonResponse({
                        'status': 'error',
                        'message': 'You are not enrolled in any loyalty program.'
                    }, status=400)

                if 'loyalty_card_number' in data:
                    booking.loyalty_card_number = data['loyalty_card_number'].strip()
                if 'loyalty_pass' in data:
                    booking.loyalty_pass = data['loyalty_pass'].strip()
                if 'loyalty_level' in data:
                    booking.loyalty_level = data['loyalty_level'].strip()
            else:
                # Clear loyalty details if not a member
                booking.loyalty_card_number = None
                booking.loyalty_pass = None
                booking.loyalty_level = None

        # Save updated booking details
        booking.save()

        return JsonResponse({
            'status': 'success',
            'message': 'Booking details updated successfully!',
            'redirect_url': reverse('booking_summary', args=[booking_id])
        }, status=200)

    # For GET requests, render the 'save_details.html' template
    return render(request, 'customer/redirect/save_details.html', {
        'booking': booking,
        'booking_id': booking_id,
    })

login_required
def payment_page(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id, customer__user=request.user)

    if booking.status == 'Paused':
        messages.info(request, "Your booking is paused. Please resume your booking.")
        return redirect('resume_booking', booking_id=booking.id)

    if booking.payment_status == 'Paid':
        return redirect('payment_success', booking_id=booking.id)

    # **Use the same total price calculation logic**
    total_price = calculate_total_price(booking)

    if request.method == 'POST':
        payment_method = request.POST.get('payment_method')
        if payment_method not in ['Credit Card', 'PayPal', 'Bank Transfer']:
            return redirect('payment_success', booking_id=booking.id)  # Handle payment method failure gracefully

        payment = Payment.objects.create(
            booking=booking,
            amount=total_price,
            payment_method=payment_method,
            transaction_id=str(uuid.uuid4()),
        )

        booking.payment_status = 'Paid'
        booking.status = 'Confirmed'
        booking.save()

        return redirect('payment_success', booking_id=booking.id)

    return render(request, 'customer/booking/payment.html', {'booking': booking, 'total_price': total_price})

from decimal import Decimal

def calculate_total_price(booking):
    num_passengers = booking.passengers.count()
    base_price = Decimal(booking.cruise.price_per_person) * Decimal(num_passengers)

    room_price = Decimal(booking.cruise.price_per_room_type.get(booking.room_type, 100))  # Default room price = 100
    services_total_price = sum(Decimal(service.price) for service in booking.onboard_services.all())

    travel_insurance_price = (base_price + room_price + services_total_price) * Decimal(0.05) if booking.travel_insurance else Decimal(0)
    tax = (base_price + room_price + services_total_price + travel_insurance_price) * Decimal(0.10)

    loyalty_discount = Decimal(0)
    if booking.loyalty_program_member and hasattr(booking.customer, 'loyalty_program'):
        loyalty_discount = Decimal(booking.customer.loyalty_program.points) * Decimal(0.25)

    discount = Decimal(0)
    for passenger in booking.passengers.all():
        if passenger.age <= 12:  
            discount += base_price * Decimal(0.15)  # Child discount
        elif passenger.age >= 60:  
            discount += base_price * Decimal(0.10)  # Elderly discount

    total_price = base_price + room_price + services_total_price + travel_insurance_price + tax - loyalty_discount - discount
    return total_price.quantize(Decimal('0.001'))


from django.core.mail import send_mail, EmailMessage
from django.template.loader import render_to_string
from django.conf import settings
from django.utils.html import strip_tags
from django.http import JsonResponse
from io import BytesIO
from django.core.mail import EmailMultiAlternatives

@login_required
def payment_success(request, booking_id):
    # Get the booking object by ID
    booking = get_object_or_404(Booking, id=booking_id, customer__user=request.user)

    # Check if the booking has a payment associated with it
    if not booking.payment_booking:
        messages.error(request, "Payment not completed. Please try again.")
        return redirect('payment_page', booking_id=booking.id)

    # Check if cabin and deck are already assigned, if not, assign them
    if not booking.cabin_number or not booking.deck_number:
        booking.assign_cabin_and_deck()  # Automatically assigns cabin and deck
        booking.save()  # Save the changes to the database
        messages.success(request, f"Cabin {booking.cabin_number} and Deck {booking.deck_number} have been successfully assigned.")
    else:
        messages.info(request, f"Booking already has Cabin {booking.cabin_number} and Deck {booking.deck_number} assigned.")

    # Send notification to customer
    Notification.objects.create(
        recipient=booking.customer.user,
        title="Booking Confirmed",
        message=f"Your booking with ID {booking.id} has been confirmed.",
    )

    # Send notification to all admins
    admin_users = UserModule.objects.filter(is_staff=True)
    for admin in admin_users:
        Notification.objects.create(
            recipient=admin,
            title="New Booking Added",
            message=f"A new booking with ID {booking.id} has been added.",
        )

    # Prepare email content
    subject = f"Booking Confirmed - {booking.id}"
    customer_email = booking.customer.user.email

    # Create email body content using template (HTML and plain text)
    html_message = render_to_string('customer/booking/email/booking_confirmation.html', {'booking': booking})
    plain_message = strip_tags(html_message)

    # Generate ticket PDF
    ticket_pdf_buffer = generate_ticket_pdf(booking)

    # Generate invoice PDF
    invoice_pdf_buffer = generate_invoice(booking)

    # Create email with attachments
    email = EmailMultiAlternatives(
        subject,
        plain_message,
        settings.DEFAULT_FROM_EMAIL,
        [customer_email],
    )
    email.attach_alternative(html_message, "text/html")

    # Attach ticket PDF
    ticket_pdf_data = ticket_pdf_buffer.getvalue()
    email.attach(f"{booking.customer.get_full_name()}_ticket.pdf", ticket_pdf_data, "application/pdf")

    # Attach invoice PDF
    invoice_pdf_data = invoice_pdf_buffer.getvalue()
    email.attach(f"invoice_{booking.id}.pdf", invoice_pdf_data, "application/pdf")

    # Send the email
    email.send()

    # Render the success page with booking details
    return render(request, 'customer/booking/paymentsuccess.html', {'booking': booking})


@login_required
def notifications(request):
    user = request.user
    customer = Customer.objects.get(user=request.user)
    # Fetch all notifications for the user (read and unread)
    all_notifications = Notification.objects.filter(recipient=user).order_by('-created_at')

    # Fetch only unread notifications for the dropdown
    unread_notifications = all_notifications.filter(is_read=False)
    unread_count = unread_notifications.count()

    # Fetch the latest 5 notifications for the "View All" page
    latest_notifications = all_notifications[:5]

    return render(request, 'customer/notifications.html', {
        'customer': customer,
        'notifications': all_notifications,  # Show all notifications on "View All" page
        'unread_notifications': unread_notifications,  # For dropdown
        'latest_notifications': latest_notifications,  # Optional, for "View All" preview
        'unread_count': unread_count,
    })


@csrf_exempt
@login_required
def mark_all_notifications_read(request):
    if request.method == 'POST':
        try:
            # Mark all unread notifications as read
            notifications = Notification.objects.filter(recipient=request.user, is_read=False)
            notifications.update(is_read=True)

            # Recalculate unread count
            unread_count = Notification.objects.filter(recipient=request.user, is_read=False).count()
            return JsonResponse({'success': True, 'unread_count': unread_count})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=500)

    return JsonResponse({'success': False, 'message': 'Invalid request method'}, status=405)



@login_required
def ticket_info(request):
    customer = get_object_or_404(Customer, user=request.user)
    # Get the latest confirmed booking for the logged-in user
    try:
        booking = Booking.objects.filter(customer__user=request.user, status='Confirmed').latest('booking_date')
    except Booking.DoesNotExist:
        messages.error(request, "No confirmed bookings found.")
        return redirect('profile')

    # Generate a QR code for the ticket
    qr_data = f"Booking ID: {booking.id}\nCustomer: {booking.customer.user.username}\nCabin: {booking.cabin_number}\nDeck: {booking.deck_number}"
    qr = qrcode.make(qr_data)
    
    # Save the QR code image to a BytesIO object
    buffer = BytesIO()
    qr.save(buffer)
    buffer.seek(0)
    
    # Encode the image as base64
    qr_image = base64.b64encode(buffer.getvalue()).decode('utf-8')

    # Render the ticket page with the QR code
    context = {
        'customer': customer,
        'booking': booking,
        'qr_image': qr_image,
    }
    return render(request, 'customer/ticket.html', context)

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.colors import HexColor
from io import BytesIO
import qrcode
from django.shortcuts import get_object_or_404
from django.http import HttpResponse
from reportlab.lib.utils import ImageReader


def generate_ticket_pdf(booking):
    # File setup
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)

    # Background color
    c.setFillColor(HexColor("#FFFFFF"))
    c.rect(0, 0, 612, 792, fill=True, stroke=False)

    # Draw Border
    c.setStrokeColor(HexColor("#000000"))  # Border color (black)
    c.setLineWidth(3)  # Border thickness
    c.rect(20, 20, 572, 752)

    # Draw Header
    c.setFillColor(HexColor("#0066cc"))  # Blue background
    c.rect(0, 630, 612, 162, fill=True, stroke=False)

    c.setFont("Helvetica-Bold", 80)
    c.setFillColor(HexColor("#FFFFFF"))
    c.drawString(40, 690, "Luxury Cruise")

    # Passenger and Booking Details
    c.setFillColor(HexColor("#000000"))
    c.setFont("Helvetica-Bold", 14)
    c.drawString(30, 600, "Customer Name:")
    c.setFont("Helvetica", 14)
    c.drawString(150, 600, booking.customer.get_full_name() or "N/A")

    c.setFont("Helvetica-Bold", 14)
    c.drawString(30, 570, "Destination:")
    c.setFont("Helvetica", 14)
    c.drawString(150, 570, str(booking.cruise.destination) or "N/A")

    c.setFont("Helvetica-Bold", 14)
    c.drawString(30, 540, "Date:")
    c.setFont("Helvetica", 14)
    c.drawString(150, 540, booking.cruise.start_date.strftime("%d %b %Y") if booking.cruise.start_date else "N/A")

    c.setFont("Helvetica-Bold", 14)
    c.drawString(30, 510, "Cabin Number:")
    c.setFont("Helvetica", 14)
    c.drawString(150, 510, booking.cabin_number or "Not Assigned")

    c.setFont("Helvetica-Bold", 14)
    c.drawString(30, 480, "Deck Number:")
    c.setFont("Helvetica", 14)
    c.drawString(150, 480, str(booking.deck_number) if booking.deck_number else "Not Assigned")

    # Passenger details section
    c.setFont("Helvetica-Bold", 12)
    c.drawString(450, 420, "Passenger(s)")
    c.setFont("Helvetica", 10)
    y_pos = 400
    for passenger in booking.passengers.all():
        c.drawString(450, y_pos, f"- {passenger.first_name} {passenger.last_name}")
        y_pos -= 20

    # QR Code Generation (In-Memory)
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(f"Booking Info: {booking.customer.get_full_name()}, {booking.cruise.name}, {booking.cruise.start_date}, Cabin {booking.cabin_number}, Deck {booking.deck_number}")
    qr.make(fit=True)

    qr_img = qr.make_image(fill_color="black", back_color="white")
    qr_buffer = BytesIO()
    qr_img.save(qr_buffer, format="PNG")
    qr_buffer.seek(0)

    # Use ImageReader to handle BytesIO buffer and insert into PDF
    qr_image = ImageReader(qr_buffer)
    c.drawImage(qr_image, 450, 450, width=100, height=100)

    qr_buffer.close()

    # Onboard Services
    c.setFont("Helvetica-Bold", 14)
    c.drawString(30, 450, "Onboard Services:")
    c.setFont("Helvetica", 12)
    y = 420
    onboard_services = booking.onboard_services.all()
    if onboard_services.exists():
        for service in onboard_services:
            c.drawString(30, y, f"- {service.service_name}")
            y -= 20
    else:
        c.drawString(30, y, "None")

    # Save PDF
    c.save()
    buffer.seek(0)
    return buffer


def ticket_view(request, booking_id):
    # Fetch the Booking object using the provided booking_id
    booking = get_object_or_404(Booking, id=booking_id)

    # Generate PDF
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{booking.customer.get_full_name()}_ticket.pdf"'

    # Generate the PDF buffer
    pdf_buffer = generate_ticket_pdf(booking)

    # Ensure you get the raw content from the BytesIO buffer
    pdf_data = pdf_buffer.getvalue()

    # Write the PDF data to the response
    response.write(pdf_data)

    # Close the buffer after use
    pdf_buffer.close()

    return response

def generate_invoice(booking):
    # Create or get the invoice
    invoice, created = Invoice.objects.get_or_create(
        booking=booking,
        defaults={
            'amount': booking.total_price,
            'transaction_id': booking.payment_booking.transaction_id,
            'status': 'Issued',
        }
    )

    # Mark the invoice as paid if it was just created
    if created:
        invoice.paid = True
        invoice.save()

    # Create the PDF in memory (without writing to disk)
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    p.drawString(100, 750, f"Invoice for Booking ID: {booking.id}")
    p.drawString(100, 730, f"Cruise Name: {booking.cruise.name}")
    p.drawString(100, 710, f"Room Type: {booking.room_type}")
    p.drawString(100, 690, f"Total Price: ${booking.total_price:.2f}")
    p.drawString(100, 670, f"Transaction ID: {invoice.transaction_id}")
    p.drawString(100, 650, f"Issued Date: {invoice.issued_date}")
    p.drawString(100, 630, f"Status: {invoice.status}")
    p.drawString(100, 610, f"Paid: {'Yes' if invoice.paid else 'No'}")
    p.showPage()
    p.save()

    # Return the in-memory PDF buffer
    buffer.seek(0)
    return buffer


def cancel_booking(request, booking_id):
    """
    Handles booking cancellation. Removes booking, updates customer booking status, and increments cruise available seats.
    """
    booking = get_object_or_404(Booking, id=booking_id, customer__user=request.user)

    if request.method == 'POST':
        cancellation_reason = request.POST.get('cancellation_reason', 'No reason provided')

        # Update the CustomerBooking status
        try:
            customer_booking = CustomerBooking.objects.get(booking=booking)
            customer_booking.cancel_booking(reason=cancellation_reason)
        except CustomerBooking.DoesNotExist:
            messages.error(request, "Customer booking record not found.")
            return redirect('profile')  

        # Increment available seats in the Cruise model
        cruise = booking.cruise
        cruise.update_seat_availability(increment=True)

        # Remove the Booking object
        booking.delete()
        messages.success(request, "Booking canceled successfully. Seat availability updated.")

        return redirect('profile')  # Redirect to the user's dashboard after cancellation

    return render(request, 'customer/cancel_booking.html', {
        'booking': booking,
        'booking_id': booking.id,
        })

@csrf_exempt
@login_required
def refund_request(request, booking_id):
    user = request.user
    customer = get_object_or_404(Customer, user=user)
    booking = get_object_or_404(Booking, id=booking_id, customer=customer)

    if request.method == "POST" and request.headers.get('x-requested-with') == 'XMLHttpRequest':
        print("Received POST request")
        try:
            final_price = request.POST.get('final_price', '').replace('$', '').strip()
            notes = request.POST.get('notes', '')
            
            if not final_price or not notes:
                return JsonResponse({'status': 'error', 'message': 'All fields are required.'})

            try:
                final_price = float(final_price)
            except ValueError:
                return JsonResponse({'status': 'error', 'message': 'Invalid price format.'})

            # Create the refund request
            print(f"Creating refund for booking {booking.id}")  # Debugging log
            refund = RefundRequest.objects.create(
                booking=booking,
                final_price=final_price,
                notes=notes,
                name=user.username,
                is_approved=False
            )
            print(f"Refund created: {refund}")  # Debugging log
            
            # Send notifications to all admins
            admin_users = UserModule.objects.filter(is_staff=True)
            for admin in admin_users:
                Notification.objects.create(
                    recipient=admin,
                    title="New Refund Request Submitted",
                    message=f"A new refund request for Booking ID {booking.id} has been submitted by {user.username}.",
                )

            cancel_booking_url = reverse('cancel_booking', kwargs={'booking_id': booking.id})
            return JsonResponse({'status': 'success', 'redirect_url': cancel_booking_url})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)})

    context = {
        'name': user.username,
        'email': user.email,
        'booking_id': booking.id,
        'total_price': booking.total_price,
        'booking': booking,
        'customer': customer,
    }
    return render(request, 'customer/refund.html', context)


@login_required
def check_refund_status(request, booking_id):
    customer = get_object_or_404(Customer, user=request.user)
    booking = get_object_or_404(Booking, id=booking_id, customer=customer)

    refund_requested = RefundRequest.objects.filter(booking=booking).exists()

    return JsonResponse({'refund_requested': refund_requested})


@login_required
def profile(request):
    if not request.user.is_authenticated:
        return JsonResponse({'status': 'error', 'message': 'User not authenticated'}, status=401)

    try:
        customer = Customer.objects.get(user=request.user)
    except Customer.DoesNotExist:
        customer = None

    # Fetch bookings associated with the customer's profile if they exist
    bookings = Booking.objects.filter(customer=customer) if customer else []

    if request.method == 'POST':
        user_form = UserProfileForm(request.POST, instance=request.user)
        profile_form = CustomerProfileForm(request.POST, request.FILES, instance=customer)
        password_form = CustomPasswordChangeForm(user=request.user, data=request.POST)

        if 'update_profile' in request.POST:
            if user_form.is_valid() and profile_form.is_valid():
                user_form.save()
                profile_form.save()
                return JsonResponse({'status': 'success', 'message': 'Profile updated successfully.'})
            else:
                return JsonResponse({
                    'status': 'error',
                    'message': {
                        'profile_errors': profile_form.errors.as_json(),
                        'user_errors': user_form.errors.as_json(),
                    }
                })

        elif 'change_password' in request.POST:
            if password_form.is_valid():
                password_form.save()
                update_session_auth_hash(request, password_form.user)
                return JsonResponse({'status': 'success', 'message': 'Password changed successfully.'})
            else:
                return JsonResponse({
                    'status': 'error', 'message': {'password_errors': password_form.errors.as_json()}
                })

        return JsonResponse({'status': 'error', 'message': 'Invalid form submission'})

    user_form = UserProfileForm(instance=request.user)
    profile_form = CustomerProfileForm(instance=customer) if customer else CustomerProfileForm()
    password_form = CustomPasswordChangeForm(user=request.user)

    return render(request, 'customer/profile.html', {
        'user': request.user,
        'customer': customer,
        'bookings': bookings,
        'user_form': user_form,
        'profile_form': profile_form,
        'password_form': password_form,
    })

@csrf_exempt 
@login_required
def update_profile_picture(request):
    if request.method == 'POST' and request.FILES.get('profile_picture'):
        try:
            customer = Customer.objects.get(user=request.user)  # Fetch the related Customer
            profile_picture = request.FILES['profile_picture']

            # Update the profile picture field
            customer.profile_picture = profile_picture
            customer.save()

            return JsonResponse({'status': 'success', 'url': customer.profile_picture.url})
        except Customer.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Customer profile not found'}, status=404)
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request'}, status=400)


@login_required
def booking_history(request):
    try:
        # Get the logged-in user's corresponding Customer object
        customer = Customer.objects.get(user=request.user)
        # Fetch all booking history for the customer, including canceled ones
        bookings = CustomerBooking.objects.filter(customer=customer).select_related('booking', 'cruise')
    except Customer.DoesNotExist:
        bookings = []  # If no customer object exists for the user, return an empty list

    context = {
        'bookings': bookings,
        'customer': customer,
    }
    return render(request, 'customer/booking_history.html', context)

@login_required
def loyalty_program(request):
    customer = Customer.objects.get(user=request.user)
    context = {
        'customer': customer,
    }
    return render(request, 'customer/loyalty_program.html', context)

@csrf_exempt
@login_required
def feedback_view(request):
    try:
        customer = Customer.objects.get(user=request.user)
    except Customer.DoesNotExist:
        return JsonResponse({"message": "Customer profile not found."}, status=400)

    if request.method == 'POST':
        form = FeedbackForm(request.POST)
        if form.is_valid():
            feedback = form.save(commit=False)
            feedback.customer = customer
            feedback.save()

            feedback_data = {
                'customer': feedback.customer.user.username,
                'cruise': feedback.cruise.name,
                'comments': feedback.comments,
                'rating': feedback.rating
            }

            return JsonResponse({
                "message": "Feedback submitted successfully!",
                "feedback": feedback_data
            }, status=200)

        return JsonResponse({
            "message": "Invalid form submission.",
            "errors": form.errors
        }, status=400)

    cruises = Cruise.objects.all()
    all_feedback = Feedback.objects.all()
    top_feedbacks = Feedback.objects.order_by('-rating')[:3]

    return render(request, 'customer/feedback.html', {
        'form': FeedbackForm(),
        'feedbacks': top_feedbacks,
        'customer': customer,
        'cruises': cruises,
        'allfeedback': all_feedback,
    })

@login_required
def itinerary(request):
    customer = Customer.objects.get(user=request.user)
    return render(request, 'customer/itinerary.html', {"customer": customer})

def special_request_view(request):
    try:
        # Get the currently logged-in user's customer instance
        customer = Customer.objects.get(user=request.user)
    except Customer.DoesNotExist:
        messages.error(request, "No associated customer profile found.")
        return redirect('profile')  # Redirect to a relevant page, e.g., profile page

    if request.method == "POST":
        form = SpecialRequestForm(request.POST)
        if form.is_valid():
            special_request = form.save(commit=False)  # Create object but don't save to DB yet
            special_request.customer = customer  # Link to the customer instance
            special_request.save()  # Save to the database
            messages.success(request, "Special request submitted successfully!")
            return redirect('profile')  # Redirect to a success page
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = SpecialRequestForm()

    return render(request, 'customer/special_request.html', {
        'form': form,
        'customer': customer
        })

def redirect_ticket(request):
    return render(request, "customer/redirect_ticket.html")