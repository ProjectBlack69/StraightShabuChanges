from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from core.models import MenuItem, MenuCategory, Table, Reservation, Order, OrderItem, Customer, Booking, Notification, UserModule
from django.utils.timezone import now
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json

def restaurant_home(request):
    if request.user.is_authenticated:
        try:
            customer = Customer.objects.get(user=request.user)
            has_confirmed_booking = Booking.objects.filter(
                customer=customer, status='Confirmed'
            ).exists()

            if has_confirmed_booking:
                categories = MenuCategory.objects.prefetch_related("menuitem_set").all()
                return render(request, 'restaurant/home.html', {'categories': categories})

        except Customer.DoesNotExist:
            pass

    return redirect('restaurant_access_denied')

def about(request):
    return render(request, 'restaurant/about.html')

def contact(request):
    return render(request, 'restaurant/contact.html')

def service(request):
    return render(request, 'restaurant/service.html')

def team(request):
    return render(request, 'restaurant/team.html')

def reservation(request):
    return render(request, 'restaurant/reservation.html')

@csrf_exempt
def submit_reservation(request):
    """Handle form submission for table reservation."""
    if request.method == "POST":
        name = request.POST.get('name')
        email = request.POST.get('email')
        num_people = int(request.POST.get('num_people'))
        seating = request.POST.get('seating')
        meal = request.POST.get('meal')
        special_request = request.POST.get('message')

        # Fetch or create customer
        customer, created = Customer.objects.get_or_create(user__email=email, defaults={'name': name})

        # Find an available table based on preferences
        table = Table.objects.filter(capacity__gte=num_people, location=seating, is_reserved=False).first()

        if table:
            # Create reservation and mark table as reserved
            reservation = Reservation.objects.create(
                customer=customer,
                table=table,
                meal=meal,
                special_request=special_request,
                status='Pending'
            )
            table.is_reserved = True
            table.save()

            # Send a notification to the admin
            admin_users = UserModule.objects.filter(is_staff=True)  # Assuming is_staff identifies admins
            for admin in admin_users:
                Notification.objects.create(
                    recipient=admin,
                    title="New Reservation Request",
                    message=f"A new reservation has been made by {customer.get_full_name()} for {meal} at {table.name}.",
                )

            return JsonResponse({"status": "success"})

        return JsonResponse({"status": "error"})

    return JsonResponse({"status": "error"})

@csrf_exempt
def track_order(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    return JsonResponse({"status": order.status})

def testimonial(request):
    return render(request, 'restaurant/testimonial.html')

def room_service(request):
    customer = get_object_or_404(Customer, user=request.user)
    booking = Booking.objects.filter(customer__user=request.user).order_by('-id').first()  # Get latest booking
    cabin_number = booking.cabin_number if booking and booking.cabin_number else ""
    order = Order.objects.filter(customer=customer).last()
    return render(request, 'restaurant/order.html', {"order": order, "cabin_number": cabin_number})

def discover(request):
    return render(request, 'restaurant/discover.html')

def menu_list(request):
    categories = MenuCategory.objects.prefetch_related('menuitem_set').all()
    return render(request, 'restaurant/menu.html', {'categories': categories})

def order_success(request):
    return render(request, 'restaurant/status/order_success.html')

def food_selection(request):
    categories = MenuCategory.objects.prefetch_related('menuitem_set').all()
    return render(request, "restaurant/food_selection.html", {'categories': categories})

from django.db import transaction
from django.contrib import messages
from django.shortcuts import get_object_or_404

@login_required
def place_order(request):
    if request.method == "POST":
        try:
            cabin_number = request.POST.get("cabin_number")
            selected_items = json.loads(request.POST.get("selected_items", "{}"))
            total_price = float(request.POST.get("total_price", 0))
            special_requests = request.POST.get("special_requests", "")

            customer = request.user.customer_profile

            # Ensure the customer has a valid booking
            booking = customer.booking_list.filter(status="Confirmed").first()
            if not booking:
                messages.error(request, "No valid booking found.")
                return redirect("order_failed")

            # Prevent duplicate orders
            existing_order = Order.objects.filter(customer=customer, booking=booking, cabin_number=cabin_number).first()
            if existing_order:
                messages.warning(request, "An order for this cabin already exists.")
                return redirect("order_already_exists")

            with transaction.atomic():  # Ensures all queries succeed or none are saved
                # Create the order
                order = Order.objects.create(
                    customer=customer,
                    booking=booking,
                    cabin_number=cabin_number,
                    total_price=total_price,
                    special_requests=special_requests
                )

                # Track missing items
                missing_items = []

                # Create order items
                for item_name, item_data in selected_items.items():
                    try:
                        menu_item = get_object_or_404(MenuItem, name=item_name)
                        OrderItem.objects.create(
                            order=order,
                            menu_item=menu_item,
                            quantity=item_data["quantity"],
                            price=menu_item.price  # Capture price at time of order
                        )
                    except MenuItem.DoesNotExist:
                        missing_items.append(item_name)

                if missing_items:
                    messages.warning(request, f"Some items were not found: {', '.join(missing_items)}")

                # Send notification to all admin users
                admin_users = UserModule.objects.filter(is_staff=True)
                for admin in admin_users:
                    Notification.objects.create(
                        recipient=admin,
                        title="New Room Service Order",
                        message=f"A new room service order has been placed for Cabin {cabin_number} by {customer.get_full_name()}."
                    )

            return redirect("order_success")

        except Exception as e:
            messages.error(request, f"An error occurred: {str(e)}")
            return redirect("order_failed")

    return redirect("order")

@login_required
def order_list(request):
    orders = Order.objects.filter(customer=request.user.customer)
    return render(request, 'restaurant/order_list.html', {'orders': orders})

@login_required
def order_failed(request):
    """Render the order failed page when no valid booking is found."""
    return render(request, "restaurant/status/order_failed.html")

@login_required
def order_already_exists(request):
    """Render the order already exists page when a duplicate order is detected."""
    return render(request, "restaurant/status/order_already_exists.html")

@login_required
def booking(request):
    """View for displaying current orders, order history, current reservations, and reservation history."""
    
    # Ensure user is a customer
    customer = get_object_or_404(Customer, user=request.user)

    # Fetch data
    current_reservations = Reservation.objects.filter(customer=customer, status="Pending")
    reservation_history = Reservation.objects.filter(customer=customer).exclude(status="Pending")

    current_orders = Order.objects.filter(customer=customer, status__in=["Pending", "Preparing"])
    order_history = Order.objects.filter(customer=customer).exclude(status__in=["Pending", "Preparing"])

    context = {
        "current_reservations": current_reservations,
        "reservation_history": reservation_history,
        "current_orders": current_orders,
        "order_history": order_history,
    }

    return render(request, "restaurant/booking.html", context)

