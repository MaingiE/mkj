# admin_dashboard/activity_views.py
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import user_passes_test
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Count
from django.contrib.auth import get_user_model
from datetime import datetime, timedelta
from django.utils import timezone
from .models import ActivityLog
from .undo_handlers import perform_undo

User = get_user_model()


def superadmin_required(user):
    return user.is_superuser or user.role in ('admin', 'secretary_general')


@staff_member_required
def activity_logs(request):
    """Display and filter activity logs"""
    
    # Get filter parameters
    action_filter = request.GET.get('action', '')
    user_filter = request.GET.get('user', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    search_query = request.GET.get('search', '')
    
    # Base queryset
    logs = ActivityLog.objects.select_related('user', 'content_type').all()
    
    # Apply filters
    if action_filter:
        logs = logs.filter(action=action_filter)
    
    if user_filter:
        logs = logs.filter(user_id=user_filter)
    
    if date_from:
        try:
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d')
            logs = logs.filter(timestamp__gte=date_from_obj)
        except ValueError:
            pass
    
    if date_to:
        try:
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d')
            # Add one day to include the entire end date
            date_to_obj = date_to_obj + timedelta(days=1)
            logs = logs.filter(timestamp__lt=date_to_obj)
        except ValueError:
            pass
    
    if search_query:
        logs = logs.filter(
            Q(description__icontains=search_query) |
            Q(object_repr__icontains=search_query) |
            Q(user__email__icontains=search_query)
        )
    
    # Statistics
    total_logs = logs.count()
    today_logs = logs.filter(timestamp__date=timezone.now().date()).count()
    
    # Action statistics
    action_stats = logs.values('action').annotate(
        count=Count('action')
    ).order_by('-count')[:10]
    
    # User activity statistics
    user_stats = logs.values('user__email', 'user__id').annotate(
        count=Count('user')
    ).order_by('-count')[:10]
    
    # Pagination
    paginator = Paginator(logs, 50)  # Show 50 logs per page
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    # Get unique actions and users for filter dropdowns
    all_actions = ActivityLog.objects.values_list('action', flat=True).distinct()
    all_users = User.objects.filter(activity_logs__isnull=False).distinct()
    
    context = {
        'page_obj': page_obj,
        'total_logs': total_logs,
        'today_logs': today_logs,
        'action_stats': action_stats,
        'user_stats': user_stats,
        'all_actions': all_actions,
        'all_users': all_users,
        # Current filters
        'action_filter': action_filter,
        'user_filter': user_filter,
        'date_from': date_from,
        'date_to': date_to,
        'search_query': search_query,
    }
    
    return render(request, 'admin_dashboard/activity_logs.html', context)


@staff_member_required
def activity_log_detail(request, log_id):
    """Display detailed information about a specific log entry"""
    log = ActivityLog.objects.select_related('user', 'content_type').get(id=log_id)
    
    context = {
        'log': log,
    }
    
    return render(request, 'admin_dashboard/activity_log_detail.html', context)


@user_passes_test(superadmin_required)
def undo_action(request, log_id):
    """
    Undo a specific action (Super Admin only)
    """
    log = get_object_or_404(ActivityLog, id=log_id)
    
    if request.method == 'POST':
        reason = request.POST.get('reason', '').strip()
        
        if not reason:
            messages.error(request, "❌ Please provide a reason for undoing this action")
            return redirect('activity_logs')
        
        if not log.can_be_undone():
            messages.error(request, "❌ This action cannot be undone (already undone, too old, or not undoable)")
            return redirect('activity_logs')
        
        # Perform undo
        success, message = perform_undo(log, request.user, reason)
        
        if success:
            messages.success(request, f"✅ Action undone successfully: {message}")
        else:
            messages.error(request, f"❌ Failed to undo action: {message}")
        
        return redirect('activity_logs')
    
    context = {
        'log': log,
    }
    
    return render(request, 'admin_dashboard/undo_confirmation.html', context)
