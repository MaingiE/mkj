"""
MKJ SUPA CUP Teams — Payment Receipt Notifications

Sends email receipts when payments are confirmed by the treasurer.
Recipients:Z
1. Sports officer for the respective county
2. The person who registered (team contact email)
"""
import logging
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.utils import timezone

logger = logging.getLogger(__name__)


def _safe_send(subject, html_message, recipient_list, fail_silently=True):
    """Send an email, logging errors instead of crashing."""
    plain_message = strip_tags(html_message)
    recipient_list = [e for e in recipient_list if e]
    if not recipient_list:
        logger.warning("No valid recipients for email: %s", subject)
        return False
    try:
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=recipient_list,
            html_message=html_message,
            fail_silently=fail_silently,
        )
        logger.info("Payment receipt sent: '%s' to %s", subject, recipient_list)
        return True
    except Exception as exc:
        logger.error("Failed to send payment receipt '%s': %s", subject, exc)
        return False


def send_payment_receipt(team, confirmed_by_user):
    """
    Send payment confirmation receipt to:
    1. The sports officer for the team's county (if available)
    2. The team's contact email (person who registered)
    """
    # Prepare receipt data
    payment_date = team.payment_confirmed_at.strftime("%d %b %Y at %H:%M") if team.payment_confirmed_at else "N/A"
    payment_ref = team.payment_reference or "N/A"
    payment_amount = f"KES {team.payment_amount:,.2f}" if team.payment_amount else "N/A"
    
    # Get recipient emails
    recipients = []
    
    # 1. County sports officer email
    if hasattr(team, 'county') and hasattr(team.county, 'primary_contact_email'):
        county_email = team.county.primary_contact_email
        if county_email:
            recipients.append(county_email)
    
    # 2. Team contact email (person who registered)
    if team.contact_email:
        recipients.append(team.contact_email)
    
    if not recipients:
        logger.warning("No recipients found for payment receipt for team %s", team.name)
        return False
    
    subject = f"[MKJ SUPA CUP] Payment Receipt — {team.name} Registration Confirmed"
    
    html_message = f"""
    <div style="font-family: Arial, sans-serif; max-width: 700px; margin: 0 auto; border: 2px solid #004D1A; border-radius: 8px;">
        <!-- Header -->
        <div style="background: linear-gradient(135deg, #004D1A 0%, #006B23 100%); color: #fff; padding: 25px; text-align: center; border-radius: 6px 6px 0 0;">
            <h1 style="margin: 0; font-size: 24px;">⚽ KENYA YOUTH INTERCOUNTY SPORTS ASSOCIATION</h1>
            <p style="color: #666; margin: 5px 0 0 0; font-size: 14px; font-style: italic;">11th Edition</p>
            <p style="margin: 8px 0 0; font-size: 16px; opacity: 0.9;">KENYA YOUTH INTER-SECONDARY SCHOOL ASSOCIATION</p>
        </div>
        
        <!-- Receipt Content -->
        <div style="padding: 30px; background: #fff;">
            <div style="text-align: center; margin-bottom: 25px;">
                <h2 style="margin: 0; color: #004D1A; font-size: 20px;">PAYMENT RECEIPT</h2>
                <p style="margin: 5px 0 0; color: #666; font-size: 14px;">Registration Payment Confirmed</p>
            </div>
            
            <!-- Receipt Details -->
            <div style="background: #f8f9fa; padding: 20px; border-radius: 6px; margin: 20px 0;">
                <table style="width: 100%; border-collapse: collapse;">
                    <tr>
                        <td style="padding: 8px 0; border-bottom: 1px solid #ddd; font-weight: bold; color: #333; width: 40%;">Team Name:</td>
                        <td style="padding: 8px 0; border-bottom: 1px solid #ddd; color: #333;">{team.name}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0; border-bottom: 1px solid #ddd; font-weight: bold; color: #333;">County:</td>
                        <td style="padding: 8px 0; border-bottom: 1px solid #ddd; color: #333;">{team.county.name if hasattr(team, 'county') and team.county else 'N/A'}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0; border-bottom: 1px solid #ddd; font-weight: bold; color: #333;">Sport:</td>
                        <td style="padding: 8px 0; border-bottom: 1px solid #ddd; color: #333;">{team.get_sport_type_display()}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0; border-bottom: 1px solid #ddd; font-weight: bold; color: #333;">Competition:</td>
                        <td style="padding: 8px 0; border-bottom: 1px solid #ddd; color: #333;">{team.competition.name if team.competition else 'N/A'}</td>
                    </tr>
                    <tr style="background: #e8f5e8;">
                        <td style="padding: 8px 0; border-bottom: 1px solid #ddd; font-weight: bold; color: #004D1A;">Payment Amount:</td>
                        <td style="padding: 8px 0; border-bottom: 1px solid #ddd; color: #004D1A; font-weight: bold; font-size: 16px;">{payment_amount}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0; border-bottom: 1px solid #ddd; font-weight: bold; color: #333;">Payment Reference:</td>
                        <td style="padding: 8px 0; border-bottom: 1px solid #ddd; color: #333; font-family: monospace;">{payment_ref}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0; border-bottom: 1px solid #ddd; font-weight: bold; color: #333;">Payment Date:</td>
                        <td style="padding: 8px 0; border-bottom: 1px solid #ddd; color: #333;">{payment_date}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0; font-weight: bold; color: #333;">Confirmed By:</td>
                        <td style="padding: 8px 0; color: #333;">{confirmed_by_user.get_full_name()} (MKJ SUPA CUP Treasurer)</td>
                    </tr>
                </table>
            </div>
            
            <!-- Status Banner -->
            <div style="background: #d4edda; border: 1px solid #c3e6cb; color: #155724; padding: 15px; border-radius: 6px; text-align: center; margin: 20px 0;">
                <strong>✅ PAYMENT CONFIRMED — Team Registration Approved</strong>
            </div>
            
            <!-- Important Notes -->
            <div style="background: #fff3cd; border: 1px solid #ffeaa7; color: #856404; padding: 15px; border-radius: 6px; margin: 20px 0;">
                <h4 style="margin: 0 0 8px; color: #856404;">📋 Important Notes:</h4>
                <ul style="margin: 8px 0 0; padding-left: 20px; line-height: 1.6;">
                    <li>This payment covers the county registration fee for ALL sports for the 2026 season</li>
                    <li>Team manager login credentials will be sent separately</li>
                    <li>Keep this receipt for your records</li>
                    <li>Contact MKJ SUPA CUP support for any questions: support@mkj_supacup.ke</li>
                </ul>
            </div>
            
            <!-- Contact Information -->
            <div style="border-top: 2px solid #f1f1f1; padding-top: 20px; margin-top: 25px;">
                <p style="margin: 0; color: #666; font-size: 12px; text-align: center;">
                    <strong>KENYA YOUTH INTER-SECONDARY SCHOOL ASSOCIATION (MKJ SUPA CUP)</strong><br>
                    11th Edition • 2026 Season<br>
                    Email: info@mkj_supacup.ke | Website: www.mkj_supacup.ke<br>
                    This is an automated receipt generated on {timezone.now().strftime("%d/%m/%Y at %H:%M")}
                </p>
            </div>
        </div>
    </div>
    """
    
    return _safe_send(subject, html_message, recipients)