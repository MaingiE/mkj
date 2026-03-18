from django.db import models
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone


class ActivityLog(models.Model):
    """
    Store all user activity/actions in the system for audit trail
    """
    ACTION_CHOICES = [
        # Authentication
        ('LOGIN', 'Login'),
        ('LOGOUT', 'Logout'),
        ('PASSWORD_CHANGE', 'Password Change'),
        
        # Team Management
        ('TEAM_CREATE', 'Team Created'),
        ('TEAM_UPDATE', 'Team Updated'),
        ('TEAM_DELETE', 'Team Deleted'),
        ('TEAM_APPROVE', 'Team Approved'),
        ('TEAM_REJECT', 'Team Rejected'),
        ('TEAM_SUSPEND', 'Team Suspended'),
        
        # Player Management
        ('PLAYER_CREATE', 'Player Created'),
        ('PLAYER_UPDATE', 'Player Updated'),
        ('PLAYER_DELETE', 'Player Deleted'),
        ('PLAYER_TRANSFER', 'Player Transfer'),
        
        # Match Management
        ('MATCH_CREATE', 'Match Created'),
        ('MATCH_UPDATE', 'Match Updated'),
        ('MATCH_DELETE', 'Match Deleted'),
        ('MATCH_RESCHEDULE', 'Match Rescheduled'),
        ('MATCH_REPORT', 'Match Report Submitted'),
        ('MATCH_REPORT_APPROVE', 'Match Report Approved'),
        ('RESULT_OVERRIDE', 'Result Override'),
        ('STANDINGS_OVERRIDE', 'Standings Override'),
        ('SG_OVERRIDE_ACK', 'SG Override Acknowledged'),
        ('SG_OVERRIDE_REJECT', 'SG Override Rejected'),
        
        # Fixture Management
        ('FIXTURE_GENERATE', 'Fixtures Generated'),
        ('FIXTURE_REGENERATE', 'Fixtures Regenerated'),
        
        # Zone Management
        ('ZONE_ASSIGN', 'Zone Assigned'),
        ('ZONE_UPDATE', 'Zone Updated'),
        
        # Payment
        ('PAYMENT_RECEIVED', 'Payment Received'),
        ('PAYMENT_VERIFIED', 'Payment Verified'),
        
        # Suspension
        ('SUSPENSION_CREATE', 'Suspension Created'),
        ('SUSPENSION_LIFT', 'Suspension Lifted'),
        
        # Matchday Squad Management
        ('MATCHDAY_SQUAD_SUBMIT', 'Matchday Squad Submitted'),
        ('SQUAD_APPROVE', 'Squad Approved'),
        ('SQUAD_REJECT', 'Squad Rejected'),
        
        # Referee Management
        ('REFEREE_REGISTER', 'Referee Registered'),
        ('REFEREE_APPROVE', 'Referee Approved'),
        ('REFEREE_ACTION', 'Referee Action'),
        
        # User Management
        ('USER_CREATE', 'User Created'),
        ('USER_UPDATE', 'User Updated'),
        ('USER_DELETE', 'User Deleted'),
        ('USER_ROLE_CHANGE', 'User Role Changed'),
        
        # System
        ('CONFIG_CHANGE', 'Configuration Changed'),
        ('REGISTRATION_TOGGLE', 'Registration Window Toggled'),
        ('ADMIN_ACTION', 'Admin Action'),
        ('PAYMENT_ACTION', 'Payment Action'),
        
        # Other
        ('OTHER', 'Other Action'),
    ]
    
    # Who performed the action
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='activity_logs'
    )
    
    # What action was performed
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    description = models.TextField()
    
    # When it happened
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)
    
    # Related object (generic foreign key)
    content_type = models.ForeignKey(ContentType, on_delete=models.SET_NULL, null=True, blank=True)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    content_object = GenericForeignKey('content_type', 'object_id')
    object_repr = models.CharField(max_length=200, blank=True)  # String representation
    
    # Request metadata
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=500, blank=True)
    
    # Additional data (JSON field for flexibility)
    extra_data = models.JSONField(default=dict, blank=True)
    changes_json = models.TextField(blank=True, default='{}', help_text="JSON representation of changes")
    
    # Undo functionality
    previous_state = models.JSONField(null=True, blank=True, help_text="State before action for undo")
    new_state = models.JSONField(null=True, blank=True, help_text="State after action")
    can_undo = models.BooleanField(default=False, help_text="Whether this action can be undone")
    is_undone = models.BooleanField(default=False, help_text="Whether this action has been undone")
    undone_at = models.DateTimeField(null=True, blank=True)
    undone_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='undone_actions'
    )
    undo_reason = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['-timestamp']),
            models.Index(fields=['user', '-timestamp']),
            models.Index(fields=['action', '-timestamp']),
        ]
        verbose_name = 'Activity Log'
        verbose_name_plural = 'Activity Logs'
    
    def __str__(self):
        return f"{self.user} - {self.get_action_display()} - {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"
    
    @property
    def action_class(self):
        """Return CSS class based on action type"""
        critical_actions = ['DELETE', 'SUSPEND', 'REJECT', 'REGENERATE']
        warning_actions = ['UPDATE', 'RESCHEDULE', 'TRANSFER']
        success_actions = ['CREATE', 'APPROVE', 'GENERATE']
        
        action_upper = self.action.upper()
        
        if any(word in action_upper for word in critical_actions):
            return 'danger'
        elif any(word in action_upper for word in warning_actions):
            return 'warning'
        elif any(word in action_upper for word in success_actions):
            return 'success'
        elif 'LOGIN' in action_upper or 'LOGOUT' in action_upper:
            return 'info'
        else:
            return 'secondary'
    
    @property
    def action_icon(self):
        """Return Bootstrap Icon name based on action type"""
        icon_map = {
            'LOGIN': 'box-arrow-in-right',
            'LOGOUT': 'box-arrow-right',
            'CREATE': 'plus-circle',
            'UPDATE': 'pencil-square',
            'DELETE': 'trash',
            'APPROVE': 'check-circle',
            'REJECT': 'x-circle',
            'SUSPEND': 'slash-circle',
            'TRANSFER': 'arrow-left-right',
            'GENERATE': 'shuffle',
            'PAYMENT': 'cash-stack',
        }
        
        for key, icon in icon_map.items():
            if key in self.action.upper():
                return icon
        return 'info-circle'
    
    def can_be_undone(self):
        """Check if this action can be undone"""
        if self.is_undone:
            return False
        if not self.can_undo:
            return False
        # Don't allow undo of very old actions (optional - 7 days)
        days_old = (timezone.now() - self.timestamp).days
        if days_old > 7:
            return False
        return True
