from django.http import JsonResponse
from django.contrib.auth import authenticate, login
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from core.models import Employee, Position, Department, Notification, ChangeRequest, UserModule, Shift, ShiftSwapRequest, EmployeeActivity, VirtualClock, JobApplication, Task, Payroll, PositionSalary, Training, SupportTicket, LeaveRequest
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
import json
from django.utils import timezone
from django.utils.timezone import datetime, timedelta
from django.contrib.auth import logout
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from .forms import JobApplicationForm, EmployeeProfileUpdateForm, SupportTicketForm
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.urls import reverse
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth.hashers import make_password
from myproject.utils.nationalities import get_nationality_choices
from math import cos, sin, radians
from dateutil.relativedelta import relativedelta

def start(request):
    return render(request, 'employee/start.html')

def apply(request):
    job_roles = JobApplication.job_role_choices 
    nationality_choices = get_nationality_choices()
    return render(request, 'employee/apply.html', {"job_roles": job_roles, "nationality_choices": nationality_choices})

from datetime import datetime, date

@csrf_exempt
def submit_application_step(request, step):
    try:
        if step == '4':  # Handle file uploads in the last step
            data = request.POST
            uploaded_cv = request.FILES.get('uploaded_cv', None)
        else:
            data = json.loads(request.body)

        application_id = data.get('application_id')
        print(f"Received Application ID: {application_id}")  # Debugging

        # Ensure application ID exists for steps after Step 1
        if step != '1' and not application_id:
            return JsonResponse({"success": False, "message": "Application ID is missing. Please restart your application."})

        # Create a new application only for Step 1
        if step == '1' and not application_id:
            application = JobApplication.objects.create()
            application_id = application.id
            print(f"New Application Created: {application_id}")  # Debugging
        else:
            application = get_object_or_404(JobApplication, id=application_id)

        # Step-wise field updates
        if step == '1':  # Personal Details
            application.first_name = data.get('first_name')
            application.last_name = data.get('last_name')
            application.email = data.get('email')
            application.phone = data.get('phone')
            application.date_of_birth = data.get('date_of_birth')
            application.gender = data.get('gender')

            # Validate Age (Must be at least 21)
            dob_str = data.get('date_of_birth')
            if dob_str:
                dob = datetime.strptime(dob_str, "%Y-%m-%d").date()
                today = date.today()
                age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
                
                if age < 21:
                    return JsonResponse({"success": False, "message": "You must be at least 21 years old to apply."})

        elif step == '2':  # Job Preferences
            application.job_role = data.get('job_role')
            application.availability_date = data.get('availability_date')
            application.willingness_to_relocate = data.get('willingness_to_relocate')

        elif step == '3':  # Location Details
            application.address = data.get('address')
            application.city = data.get('city')
            application.pincode = data.get('pincode')
            application.nationality = data.get('nationality')

        elif step == '4':  # Experience & CV
            application.previous_experience = data.get('previous_experience')
            application.status = 'pending'  # Set default status
            if uploaded_cv:
                application.uploaded_cv = uploaded_cv  # Save file if uploaded

        application.save()
        return JsonResponse({"success": True, "application_id": application.id})

    except Exception as e:
        return JsonResponse({"success": False, "message": str(e)})

@csrf_exempt
def upload_cv(request, application_id):
    """Handles file upload separately for better performance"""
    if request.method == "POST":
        application = get_object_or_404(JobApplication, id=application_id)
        if 'uploaded_cv' in request.FILES:
            application.uploaded_cv = request.FILES['uploaded_cv']
            application.save()
            return JsonResponse({"success": True, "message": "CV uploaded successfully"})
        else:
            return JsonResponse({"success": False, "message": "No file uploaded"})
    
    return JsonResponse({"success": False, "message": "Invalid request"})

def application_success(request):
    return render(request, 'employee/application_success.html')

@require_http_methods(["GET", "POST"])
def employee_login(request):
    if request.method == "GET":
        # Render the login page for GET requests
        return render(request, "employee/login.html")

    if request.method == "POST":
        try:
            data = json.loads(request.body)  # Parse JSON data from the request body
        except json.JSONDecodeError:
            return JsonResponse({'status': 'error', 'message': 'Invalid JSON.'}, status=400)

        email = data.get('email')
        password = data.get('password')

        if email and password:
            # Authenticate the user
            user = authenticate(request, username=email, password=password)

            if user is not None and user.is_active:
                # Log in the user
                login(request, user)
                return JsonResponse({'status': 'success', 'message': "Employee login successful!"})
            else:
                return JsonResponse({'status': 'error', 'message': "Invalid credentials or inactive account."})

        return JsonResponse({'status': 'error', 'message': "Email and password are required."}, status=400)
    
def get_virtual_dates():
    """Fetch virtual today and tomorrow separately from VirtualClock."""
    virtual_clock = VirtualClock.objects.first()
    
    if virtual_clock:
        virtual_time = virtual_clock.get_virtual_time()
    else:
        virtual_time = datetime.now()

    virtual_today = virtual_time.date()
    virtual_tomorrow = virtual_today + timedelta(days=1)

    return virtual_today, virtual_tomorrow
    
@login_required
def dashboard(request):
    # Fetch the virtual clock from the core app
    virtual_today, virtual_tomorrow = get_virtual_dates()

    virtual_clock = VirtualClock.objects.first() 
    if virtual_clock:
        virtual_time = virtual_clock.get_virtual_time()
        is_tomorrow = virtual_clock.current_day == 'Tomorrow'
    else:
        virtual_time = datetime.now()
        is_tomorrow = False
    
    # Fetch the logged-in employee
    employee = Employee.objects.filter(user=request.user).first()

    if employee:
        # Count attendance
        attendance_count = EmployeeActivity.objects.filter(employee=employee, attendance_status='Present').count()
    else:
        attendance_count = 0

    # Fetch all notifications
    notifications = Notification.objects.filter(recipient=request.user).order_by('-created_at')
    unread_count = notifications.filter(is_read=False).count()
    recent_notifications = notifications[:5]

    # Get the employee and their supervisor
    employee = request.user.employee
    supervisor = employee.supervisor

    # Determine the date to filter shifts
    shift_date = virtual_time.date()

    # Ensure that the Shift model has a DateField like 'shift_date'. If not, use this approach:
    current_shift = Shift.objects.filter(
        employee=employee,
        status='Scheduled',
        day='Today',
        start_time__gte=virtual_time.replace(hour=0, minute=0, second=0),  # Start of the day
        start_time__lte=virtual_time.replace(hour=23, minute=59, second=59)  # End of the day
    ).order_by('start_time').first()


    # If no current shift and virtual clock is set to 'Tomorrow', fetch tomorrow's shift
    if not current_shift and is_tomorrow:
        tomorrow_date = virtual_time.date() + timedelta(days=1)
        current_shift = Shift.objects.filter(
            employee=employee,
            status='Scheduled',
            start_time__date=tomorrow_date
        ).select_related('employee').first()

    # Ensure the current shift logic resets when virtual clock changes back to 'Today'
    if not is_tomorrow and current_shift and current_shift.start_time and current_shift.start_time != virtual_time.time():
        # Fix the comparison by combining the date and time for current_shift
        current_shift_datetime = datetime.combine(shift_date, current_shift.start_time)
        if current_shift_datetime.date() != virtual_time.date():
            current_shift = Shift.objects.filter(
                employee=employee,
                status='Scheduled',
                start_time__lte=virtual_time,
                end_time__gte=virtual_time
            ).select_related('employee').first()

    # Combine start and end times for current shift
    if current_shift:
        start_datetime = datetime.combine(shift_date, current_shift.start_time)
        end_datetime = datetime.combine(shift_date, current_shift.end_time)

        # Convert to ISO 8601 format
        start_time = start_datetime.isoformat()
        end_time = end_datetime.isoformat()
    else:
        start_time = None
        end_time = None

    # Fetch the first scheduled shift for tomorrow
    upcoming_shift = Shift.objects.filter(
        employee=employee,
        day="Tomorrow",
        status="Scheduled"
    ).order_by("start_time").first()

    # Shift swap candidates
    swap_candidates = Shift.objects.filter(
        status='Scheduled'
    ).exclude(employee=employee).select_related('employee__user')[:10]

    # Recent activity data
    activity_data = EmployeeActivity.objects.filter(
        employee=employee
    ).order_by('-date')[:5]

    # Pending swap requests (Waiting for Employee Approval)
    pending_swap_requests = ShiftSwapRequest.objects.filter(
        employee_to=employee,
        status="Approved by Admin"
    )

    return render(request, 'employee/dashboard.html', {
        'employee': employee,
        'attendance_count': attendance_count,
        'recent_notifications': recent_notifications,
        'unread_count': unread_count,
        'current_shift': current_shift,
        'upcoming_shift': upcoming_shift,
        'supervisor': supervisor,
        'swap_candidates': swap_candidates,
        'activity_data': activity_data,
        'start_time': start_time,
        'end_time': end_time,
        'virtual_today': virtual_today,
        'virtual_tomorrow': virtual_tomorrow,
        'virtual_time': virtual_time.isoformat(),
        'pending_swap_requests': pending_swap_requests,
    })

def profile(request):
    employee = get_object_or_404(Employee, user=request.user)
    return render(request, 'employee/profile.html', {'employee': employee})

@login_required
def notifications(request):
    user = request.user
    all_notifications = Notification.objects.filter(recipient=user).order_by('-created_at')
    unread_notifications = all_notifications.filter(is_read=False)
    unread_count = unread_notifications.count()

    return render(request, 'employee/notification.html', {
        'notifications': all_notifications,  # Show all notifications
        'unread_notifications': unread_notifications,  # For dropdown
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

def get_virtual_dates():
    """Fetch virtual today and tomorrow separately from VirtualClock."""
    virtual_clock = VirtualClock.objects.first()
    
    if virtual_clock:
        virtual_time = virtual_clock.get_virtual_time()
    else:
        virtual_time = datetime.now()

    virtual_today = virtual_time.date()
    virtual_tomorrow = virtual_today + timedelta(days=1)

    return virtual_today, virtual_tomorrow

@login_required
def get_employees_by_shift_date(request):
    """Fetch employees assigned to shifts on a given date."""
    virtual_today, virtual_tomorrow = get_virtual_dates()  # Correct tuple unpacking
    shift_date = request.GET.get('shift_date')

    if not shift_date:
        return JsonResponse({'error': 'Shift date is required'}, status=400)

    try:
        shift_date = datetime.strptime(shift_date, "%Y-%m-%d").date()
    except ValueError:
        return JsonResponse({'error': 'Invalid shift date format'}, status=400)

    # Determine the correct 'day' value
    if shift_date == virtual_today:
        day_value = 'Today'
    elif shift_date == virtual_tomorrow:
        day_value = 'Tomorrow'
    else:
        return JsonResponse({'error': 'Invalid shift date'}, status=400)

    # Fetch employees who have a shift on the selected date
    shifts = Shift.objects.filter(day=day_value, status='Scheduled').select_related('employee__user')

    employees = [
        {'id': shift.employee.id, 'name': shift.employee.get_full_name()}
        for shift in shifts if shift.employee.id != request.user.employee.id  # Exclude logged-in user
    ]

    return JsonResponse({'employees': employees})

def get_shifts_by_employee(request):
    shift_date = request.GET.get('shift_date')  # shift_date from frontend
    employee_id = request.GET.get('employee_id')

    print(f"Raw Employee ID: {employee_id}")  # Debugging

    # Ensure employee_id is an integer
    try:
        employee_id = int(employee_id)
    except ValueError:
        return JsonResponse({'success': False, 'error': 'Invalid Employee ID.'})

    print(f"Converted Employee ID: {employee_id}")  # Debugging

    try:
        employee = Employee.objects.get(id=employee_id)

        # Convert shift_date into "Today" or "Tomorrow"
        virtual_today, virtual_tomorrow = get_virtual_dates()

        if shift_date == str(virtual_today):
            shift_day = "Today"
        elif shift_date == str(virtual_tomorrow):
            shift_day = "Tomorrow"
        else:
            return JsonResponse({'success': False, 'error': 'Invalid shift date.'})

        # Fetch shifts using "day" field instead of "date"
        shifts = Shift.objects.filter(employee=employee, day=shift_day)

        shift_list = [
            {
                'id': shift.id,
                'shift_type': shift.shift_type,
                'start_time': shift.start_time,
                'end_time': shift.end_time
            }
            for shift in shifts
        ]

        return JsonResponse({'success': True, 'shifts': shift_list})

    except Employee.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Employee not found.'})

@login_required
def request_shift_swap(request):
    if request.method == 'POST':
        employee = request.user.employee  # Logged-in user's employee record
        shift_date = request.POST.get('shift_date')  # Selected date
        swap_reason = request.POST.get('swap_reason')  # Swap reason
        employee_to_id = request.POST.get('swap_with')  # ID of selected employee
        shift_id = request.POST.get('shift_id')  # Selected shift ID to swap with

        print(f"POST Data: {request.POST}")

        virtual_today, virtual_tomorrow = get_virtual_dates()

        # Convert `shift_date` to "Today" or "Tomorrow"
        if shift_date == str(virtual_today):
            shift_day = "Today"
        elif shift_date == str(virtual_tomorrow):
            shift_day = "Tomorrow"
        else:
            return JsonResponse({'success': False, 'error': 'Invalid shift date.'})

        try:
            #  Step 1: Find the logged-in user's shift
            user_shift = Shift.objects.get(employee=employee, day=shift_day, status="Scheduled")
            print(f"🔍 Found User Shift: {user_shift}")

            #  Step 2: Find the selected employee's shift (the one we are swapping with)
            swap_shift = Shift.objects.get(id=shift_id, employee_id=employee_to_id, day=shift_day, status="Scheduled")
            print(f"🔍 Found Swap Shift: {swap_shift}")

            # Prevent self-swaps
            if employee_to_id == str(employee.id):
                return JsonResponse({'success': False, 'error': 'You cannot swap a shift with yourself.'})

            #  Step 3: Create the shift swap request
            swap_request = ShiftSwapRequest.objects.create(
                employee_from=employee,  # Logged-in user
                employee_to=swap_shift.employee,  # Employee we are swapping with
                shift_from=user_shift,  # Logged-in user's shift
                shift_to=swap_shift,  # Selected employee's shift
                swap_date=shift_date,
                reason=swap_reason,
                status="Pending"
            )

            #  Step 4: Notify admins (optional)
            admin_users = UserModule.objects.filter(is_staff=True)
            for admin in admin_users:
                Notification.objects.create(
                    recipient=admin,
                    title="Swap Request submitted",
                    message=f"{employee.first_name} {employee.last_name} submitted a swap request."
                )

            return JsonResponse({'success': True, 'message': 'Swap request submitted successfully!'})

        except Shift.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'No valid shift found for the swap.'})

        except Employee.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Selected employee does not exist.'})

    return JsonResponse({'success': False, 'error': 'Invalid request method.'})

@login_required
def respond_shift_swap(request, swap_request_id):
    swap_request = get_object_or_404(ShiftSwapRequest, id=swap_request_id)

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "approve" and swap_request.status == "Approved by Admin":
            # Swap the shifts
            shift_from = swap_request.shift_from
            shift_to = swap_request.shift_to

            # Assign the shifts to the respective employees
            shift_from.employee, shift_to.employee = shift_to.employee, shift_from.employee
            shift_from.save()
            shift_to.save()

            # Update swap request status
            swap_request.status = "Fully Approved"
            swap_request.save()

            # Clear notification from employee model
            swap_request.employee_to.swap_notification = ""
            swap_request.employee_to.save()

            # Send notification to employee_from after employee_to approves
            Notification.objects.create(
                recipient=swap_request.employee_from.user,  # Send to the employee_from's user
                title="Shift Swap Approved by Employee To",
                message=f"Employee {swap_request.employee_to.get_full_name()} has approved the shift swap request. The swap is now fully approved.",
            )

        elif action == "reject":
            swap_request.status = "Rejected"
            swap_request.save()

            # Clear notification as well
            swap_request.employee_to.swap_notification = ""
            swap_request.employee_to.save()

        return redirect('employee-dashboard')  # Redirect to employee dashboard


def get_available_employees(request):
    date = request.GET.get('date')
    if not date:
        return JsonResponse({'success': False, 'error': 'Date not provided.'})

    # Adjust the query as needed to match your models and logic
    shifts = Shift.objects.filter(day=date, status='Scheduled')
    employees = Employee.objects.filter(shift__in=shifts).distinct()

    employee_data = [{'id': emp.id, 'name': f'{emp.first_name} {emp.last_name}'} for emp in employees]

    return JsonResponse({'success': True, 'employees': employee_data})

@csrf_exempt
@login_required
def update_details(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        employee = request.user.employee
        print("Received Data:", data)

        try:
            # Initialize a list to store change requests
            changes = []

            # Check and record changes for each field
            if 'full_name' in data:
                full_name = data['full_name']
                first_name, last_name = full_name.split(' ')[0], full_name.split(' ')[1]
                if employee.first_name != first_name:
                    changes.append(ChangeRequest(
                        employee=employee,
                        field_name='first_name',
                        old_value=employee.first_name,
                        new_value=first_name
                    ))
                if employee.last_name != last_name:
                    changes.append(ChangeRequest(
                        employee=employee,
                        field_name='last_name',
                        old_value=employee.last_name,
                        new_value=last_name
                    ))

            if 'job_title' in data:
                job_title = data['job_title']
                if employee.job_role != job_title:
                    changes.append(ChangeRequest(
                        employee=employee,
                        field_name='job_role',
                        old_value=employee.job_role,
                        new_value=job_title
                    ))

            if 'department' in data:
                department_name = data['department']
                if employee.department and employee.department.name != department_name:
                    changes.append(ChangeRequest(
                        employee=employee,
                        field_name='department',
                        old_value=employee.department.name if employee.department else None,
                        new_value=department_name
                    ))

            for field in ['phone', 'skills', 'address', 'date_of_birth', 'linkedin_url']:
                if field in data:
                    new_value = data[field]
                    old_value = getattr(employee, field, '')

                    if old_value is None:
                        old_value = ""

                    print(f"Processing field: {field}, Old: {old_value}, New: {new_value}")  # Debugging

                    if str(old_value) != str(new_value):
                        changes.append(ChangeRequest(
                            employee=employee,
                            field_name=field,
                            old_value=old_value,
                            new_value=new_value
                        ))

            # Save all changes
            ChangeRequest.objects.bulk_create(changes)

            # Notify admins (optional: add Notification model logic here)
            admin_users = UserModule.objects.filter(is_staff=True)
            for admin in admin_users:
                Notification.objects.create(
                    recipient=admin,
                    title="Pending Employee Change Request",
                    message=f"{employee.first_name} {employee.last_name} submitted changes for approval."
                )

            return JsonResponse({'success': True, 'message': 'Change requests submitted for admin approval.'})

        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})

    return JsonResponse({'success': False, 'message': 'Invalid request method.'})

@login_required
@csrf_exempt
def change_employee_password(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        user = request.user

        if user.role != 'employee':
            return JsonResponse({'success': False, 'message': 'User is not an employee'})

        current_password = data.get('current_password')
        new_password = data.get('new_password')
        confirm_password = data.get('confirm_password')

        if not user.check_password(current_password):
            return JsonResponse({'success': False, 'message': 'Incorrect current password'})
        if new_password != confirm_password:
            return JsonResponse({'success': False, 'message': 'Passwords do not match'})

        # Update the password
        user.set_password(new_password)
        user.save()

        # Re-authenticate and log the user back in
        user = authenticate(request, email=user.email, password=new_password)
        if user is not None:
            login(request, user)

        return JsonResponse({'success': True, 'message': 'Password updated successfully'})

    return JsonResponse({'success': False, 'message': 'Invalid request method'})

@login_required
def submit_change_request(request):
    if request.method == "POST":
        employee = request.user.employee  # Assuming `Employee` is linked to `User`
        changes = request.POST.dict()  # Collect changes from the form
        
        for field, new_value in changes.items():
            old_value = getattr(employee, field, None)
            if str(old_value) != new_value:  # Create requests only for actual changes
                ChangeRequest.objects.create(
                    employee=employee,
                    field_name=field,
                    old_value=old_value,
                    new_value=new_value,
                )
        
        # Notify Admins
        admin_users = UserModule.objects.filter(is_staff=True)  # Assuming admins have `is_staff` as `True`
        for admin in admin_users:
            Notification.objects.create(
                recipient=admin,
                title="Employee Change Request",
                message=f"{employee.first_name} {employee.last_name} requested changes to their profile.",
            )
        
        return JsonResponse({"success": True, "message": "Change request sent for review."})
    
    return JsonResponse({"success": False, "message": "Invalid request method."}, status=400)

@csrf_exempt
def employee_logout(request):
    if request and hasattr(request, 'user') and request.user.is_authenticated:
        logout(request)
        return JsonResponse({'status': 'success', 'redirect_url': '/start-employee/'})  # JSON response

    return JsonResponse({'status': 'error', 'message': 'User not authenticated'}, status=400)

@login_required
def attendance(request):
    # Fetch the virtual clock
    virtual_clock = VirtualClock.objects.first()
    if not virtual_clock:
        return render(request, 'employee/attendance.html', {'error': 'Virtual Clock not configured.'})

    # Get virtual day and time
    virtual_time = virtual_clock.get_virtual_time()
    virtual_date = virtual_time.date()

    # Get logged-in employee
    employee = Employee.objects.get(user=request.user)

    # Fetch today's shift based on virtual day
    shift = Shift.objects.filter(employee=employee, status='Scheduled', day=virtual_clock.current_day).first()

    # Fetch attendance history for the virtual date
    attendance_history = EmployeeActivity.objects.filter(employee=employee).order_by('-date')

    context = {
        'employee': employee,
        'shift': shift,
        'attendance_history': attendance_history,
        'virtual_date': virtual_date,
        'virtual_day': virtual_clock.current_day,
    }
    return render(request, 'employee/attendance.html', context)


@login_required
def mark_attendance(request):
    if request.method == 'POST':
        # Fetch the virtual clock
        virtual_clock = VirtualClock.objects.first()
        if not virtual_clock:
            return redirect('attendance')

        virtual_time = virtual_clock.get_virtual_time()
        virtual_date = virtual_time.date()

        shift_id = request.POST.get('shift_id')
        status = request.POST.get('status')

        # Fetch the shift
        shift = Shift.objects.get(id=shift_id)
        if shift.day != virtual_clock.current_day:
            return redirect('attendance')  # Prevent marking attendance for a different day

        # Create or update the attendance record
        attendance, created = EmployeeActivity.objects.get_or_create(
            shift=shift,
            employee=shift.employee,
            date=virtual_date,
        )
        attendance.mark_attendance(status)

        return redirect('attendance')

    return redirect('attendance')

@login_required
def payroll(request):
    """View for employee to check their payroll details."""
    employee = request.user.employee
    position = employee.position  # Get employee's position
    base_salary = 0

    # Fetch completed tasks assigned to this position
    completed_tasks = Task.objects.filter(assigned_to=position, is_completed=True)

    # Fetch completed trainings for this position
    completed_trainings = Training.objects.filter(position=position, status='Completed')

    # Fetch base salary from PositionSalary model if it exists
    position_salary = PositionSalary.objects.filter(position=position).first()
    if position_salary:
        base_salary = position_salary.base_salary

    # Fetch payroll record for the logged-in employee
    payroll, created = Payroll.objects.get_or_create(
        employee=employee, defaults={"base_salary": base_salary}
    )

    # Ensure base salary is updated in payroll (if changed)
    if payroll.base_salary != base_salary:
        payroll.base_salary = base_salary
        payroll.save()

    # Generate payroll history for the last 5 months
    months = [(datetime.now() - relativedelta(months=i)).strftime("%B %Y") for i in range(5)]
    payroll_history = []

    for i in range(5):
        tasks_completed = max(0, payroll.tasks_completed - i)  # Reduce tasks progressively
        trainings_completed = max(0, payroll.trainings_completed - i)  # Reduce trainings progressively

        # Calculate bonus dynamically
        task_bonus = 0
        if tasks_completed >= 2:
            task_bonus = 1500 + (tasks_completed - 2) * 750
        elif tasks_completed == 1:
            task_bonus = 750

        training_bonus = 0
        if trainings_completed >= 3:
            training_bonus = 1500 + (trainings_completed - 3) * 500
        elif trainings_completed in [1, 2]:
            training_bonus = trainings_completed * 500

        bonus = task_bonus + training_bonus
        total_salary = base_salary + bonus  # Use base salary from PositionSalary model

        payroll_history.append({
            "month": months[i],
            "base_salary": base_salary,
            "tasks_completed": tasks_completed,
            "trainings_completed": trainings_completed,
            "bonus": bonus,
            "total_salary": total_salary,
        })

    return render(request, "employee/payroll.html", {
        "payroll": payroll,
        "payroll_history": payroll_history,
        'tasks': completed_tasks,
        'trainings': completed_trainings,
    })

@login_required
def training(request):
    """View to display and update training records for the employee."""
    employee = get_object_or_404(Employee, user=request.user)
    trainings = Training.objects.filter(position=employee.position)

    completed_count = trainings.filter(status="Completed").count()
    pending_count = trainings.filter(status="Pending").count()
    total = completed_count + pending_count
    completed_percentage = (completed_count / total * 100) if total > 0 else 0
    pending_percentage = (pending_count / total * 100) if total > 0 else 0

    # Convert percentage into angle (360 degrees)
    angle = (completed_percentage / 100) * 360
    radians_angle = radians(angle)

     # Calculate end X and Y coordinates for SVG arc
    end_x = 16 + 16 * cos(radians_angle - radians(90))  # Adjust for SVG coordinates
    end_y = 16 + 16 * sin(radians_angle - radians(90))

    # Set large-arc-flag (1 if greater than 50%, otherwise 0)
    large_arc_flag = 1 if completed_percentage > 50 else 0

    if request.method == "POST":
        training_id = request.POST.get("training_id")
        status = request.POST.get("status")

        if training_id and status:
            training = get_object_or_404(Training, id=training_id)

            if training.position == employee.position:
                training.status = status
                training.completed_on_time = status == "Completed"
                training.save()

                # Update Payroll for completed trainings
                payroll, created = Payroll.objects.get_or_create(employee=employee)
                payroll.trainings_completed = Training.objects.filter(
                    position=employee.position, status="Completed"
                ).count()
                payroll.save()

        return redirect("training")

    return render(request, "employee/training.html", {
        "employee": employee,
        "trainings": trainings,
        "completed_count": completed_count,
        "pending_count": pending_count,
        "completed_percentage": round(completed_percentage, 2),
        "pending_percentage": round(pending_percentage, 2),
        "end_x": round(end_x, 2),
        "end_y": round(end_y, 2),
        "large_arc_flag": large_arc_flag,
    })

@login_required
def task(request):
    """Fetch tasks assigned to the logged-in employee's position with filters."""
    try:
        employee = Employee.objects.get(user=request.user)
        filter_type = request.GET.get('filter', 'all')

        tasks = Task.objects.filter(assigned_to__title=employee.position.title)
        if filter_type == 'completed':
            tasks = tasks.filter(is_completed=True)
        elif filter_type == 'pending':
            tasks = tasks.filter(is_completed=False)

        return render(request, 'employee/task.html', {'tasks': tasks})
    
    except Employee.DoesNotExist:
        return render(request, 'employee/task.html', {'tasks': []})

@login_required
def complete_task(request, task_id):
    """Mark a task as completed and update Payroll accordingly."""
    try:
        task = Task.objects.get(id=task_id)
        employee = Employee.objects.get(user=request.user)

        if task.assigned_to.title == employee.position.title:
            task.is_completed = True
            task.save()

            #  Update Payroll for completed tasks
            payroll, created = Payroll.objects.get_or_create(employee=employee)
            payroll.tasks_completed = Task.objects.filter(
                assigned_to=employee.position, is_completed=True
            ).count()
            payroll.save()

            return JsonResponse({'success': True})
        else:
            return JsonResponse({'success': False, 'error': 'Task is not assigned to you.'})

    except Task.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Task not found.'})
    except Employee.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Employee not found.'})
    
@login_required
def support(request):
    """Render the support page with FAQs, ticket form, and history."""
    employee = request.user.employee  # Fetch the employee instance
    tickets = SupportTicket.objects.filter(employee=employee)

    form = SupportTicketForm()

    if request.method == "POST":
        form = SupportTicketForm(request.POST)
        if form.is_valid():
            ticket = form.save(commit=False)
            ticket.employee = request.user
            ticket.save()

            # Send email notification
            send_mail(
                "Support Ticket Submitted",
                f"Your support ticket '{ticket.subject}' has been submitted successfully.",
                "bscproject3rd@gmail.comc",
                [request.user.email],
                fail_silently=True,
            )

            return redirect("support")

    faqs = [
        {"question": "How do I reset my password?", "answer": "Go to 'Profile' and click 'Reset Password'."},
        {"question": "Whom do I contact for payroll issues?", "answer": "Submit a ticket under 'Payroll Issues'."},
        {"question": "How can I update my personal information?", "answer": "Navigate to 'Profile' and edit your details."},
        {"question": "How do I check my leave balance?", "answer": "Go to the 'Leave Management' section to view your remaining leave days."},
        {"question": "What should I do if my salary is incorrect?", "answer": "Contact HR or submit a payroll discrepancy ticket."},
        {"question": "Where can I download my payslip?", "answer": "Payslips are available under the 'Payroll' section."},
        {"question": "How do I report a technical issue?", "answer": "Submit a support ticket under 'Technical Support'."},
        {"question": "How can I view my work schedule?", "answer": "Check the 'Shifts' tab in your dashboard."},
        {"question": "What are the working hours?", "answer": "Standard working hours are 9 AM - 5 PM, Monday to Friday."},
        {"question": "How do I apply for a promotion?", "answer": "Review available positions under 'Career Growth' and submit an application."},
        {"question": "How do I claim work expenses?", "answer": "Upload your receipts in the 'Expense Claims' section for approval."},
        {"question": "Can I change my assigned tasks?", "answer": "Speak with your manager or submit a task reassignment request."},
        {"question": "How do I access company policies?", "answer": "All company policies are available in the 'Employee Handbook' section."},
        {"question": "What happens if I miss a deadline?", "answer": "Discuss with your supervisor for an extension or alternative solutions."},
    ]


    return render(request, "employee/support.html", {
        "form": form,
        "tickets": tickets,
        "faqs": faqs,
    })

@login_required
def leave_management(request):
    employee = request.user.employee  # Get logged-in employee

    if request.method == "POST":
        leave_type = request.POST.get("leave_type")
        start_date = datetime.strptime(request.POST.get("start_date"), "%Y-%m-%d")
        end_date = datetime.strptime(request.POST.get("end_date"), "%Y-%m-%d")
        reason = request.POST.get("reason")

        leave_days = (end_date - start_date).days + 1  # Calculate leave duration

        # Create the leave request (status remains "pending")
        leave_request = LeaveRequest.objects.create(
            employee=employee,
            leave_type=leave_type.capitalize(),
            start_date=start_date,
            end_date=end_date,
            reason=reason,
            status="pending",
        )

        # Send Notification to Admins
        admin_users = UserModule.objects.filter(is_staff=True)  # Get all admins
        for admin in admin_users:
            Notification.objects.create(
                recipient=admin,
                title="New Leave Request",
                message=f"{employee.user.get_full_name()} has requested {leave_type.capitalize()} leave from {start_date} to {end_date}. Please review it."
            )

        messages.success(request, "Leave request submitted successfully!")
        return redirect("leave_management")

    leaves = LeaveRequest.objects.filter(employee=employee).order_by("-created_at")

    return render(
        request,
        "employee/leave.html",
        {"leaves": leaves, "remaining_leave": employee.remaining_leave_days},
    )

@login_required
def update_ticket_status(request, ticket_id, new_status):
    """Update ticket status and notify employee."""
    ticket = get_object_or_404(SupportTicket, id=ticket_id)

    if request.user.is_staff or ticket.employee == request.user:
        ticket.status = new_status
        ticket.save()

        # Notify employee of status change
        send_mail(
            "Support Ticket Updated",
            f"Your ticket '{ticket.subject}' is now marked as {new_status}.",
            "bscproject3rd@gmail.com",
            [ticket.employee.email],
            fail_silently=True,
        )

    return redirect("support")

@csrf_exempt
@login_required
def update_employee_profile_picture(request):
    if request.method == 'POST' and request.FILES.get('profile_picture'):
        try:
            employee = Employee.objects.get(user=request.user)  # Fetch employee instance
            profile_picture = request.FILES['profile_picture']

            # Save the new profile picture
            employee.profile_picture = profile_picture
            employee.save()

            return JsonResponse({'success': True, 'url': employee.profile_picture.url})
        except Employee.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Employee profile not found'}, status=404)
    return JsonResponse({'success': False, 'error': 'Invalid request'}, status=400)

def forgot_password(request):
    return render(request, 'employee/forgot_password.html')

@csrf_exempt
def send_reset_email(request):
    if request.method == "POST":
        try:
            # Ensure request body is not empty and is valid JSON
            if not request.body:
                return JsonResponse({"success": False, "message": "Empty request body."})

            data = json.loads(request.body)
            email = data.get("email")

            if not email:
                return JsonResponse({"success": False, "message": "Email is required."})

            user = get_object_or_404(UserModule, email=email)
            employee = Employee.objects.filter(user=user).first()

            if not employee:
                return JsonResponse({"success": False, "message": "No associated employee account found."})

            token = default_token_generator.make_token(user)
            reset_link = f"http://127.0.0.1:8000/employee/reset-password/{employee.pk}/{token}/"

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

@csrf_exempt
def reset_password(request, employee_id, token):
    employee = get_object_or_404(Employee, pk=employee_id)

    if request.method == "GET":
        return render(request, "employee/reset_password_form.html", {"employee_id": employee_id, "token": token})

    elif request.method == "POST":
        data = json.loads(request.body)
        new_password = data.get("new_password")
        confirm_password = data.get("confirm_password")

        if not new_password or not confirm_password:
            return JsonResponse({"success": False, "message": "Both password fields are required."})

        if new_password != confirm_password:
            return JsonResponse({"success": False, "message": "Passwords do not match."})

        if not default_token_generator.check_token(employee.user, token):
            return JsonResponse({"success": False, "message": "Invalid or expired reset link."})

        # Update the password in `UserModule`
        employee.user.set_password(new_password)
        employee.user.save()

        return JsonResponse({"success": True, "message": "Password reset successful. You can now log in."})

    return JsonResponse({"success": False, "message": "Invalid request method."})


