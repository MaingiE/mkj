"""
MKJ SUPA CUP — M-Pesa Daraja API Integration (STK Push / Lipa Na M-Pesa Online)
Sends a payment prompt to the user's phone. Funds go to the configured
business shortcode which can be linked to a bank account via Safaricom.
"""
import base64
import logging
from datetime import datetime

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

# Daraja API endpoints
SANDBOX_BASE = "https://sandbox.safaricom.co.ke"
PRODUCTION_BASE = "https://api.safaricom.co.ke"


def _get_base_url():
    if getattr(settings, "MPESA_ENVIRONMENT", "sandbox") == "production":
        return PRODUCTION_BASE
    return SANDBOX_BASE


def _get_access_token():
    """Fetch OAuth access token from Daraja API."""
    url = f"{_get_base_url()}/oauth/v1/generate?grant_type=client_credentials"
    key = getattr(settings, "MPESA_CONSUMER_KEY", "")
    secret = getattr(settings, "MPESA_CONSUMER_SECRET", "")
    if not key or not secret:
        raise ValueError("M-Pesa consumer key/secret not configured in settings.")
    resp = requests.get(url, auth=(key, secret), timeout=30)
    resp.raise_for_status()
    return resp.json()["access_token"]


def _generate_password(shortcode, passkey, timestamp):
    """Base64-encode(shortcode + passkey + timestamp)."""
    data = f"{shortcode}{passkey}{timestamp}"
    return base64.b64encode(data.encode("utf-8")).decode("utf-8")


def initiate_stk_push(phone_number, amount, account_reference=None, description=None):
    """
    Send an STK push (Lipa Na M-Pesa Online) to the given phone number.

    Args:
        phone_number: Kenyan phone in +254XXXXXXXXX or 254XXXXXXXXX format.
        amount: Amount in KSh (integer).
        account_reference: Reference shown on M-Pesa receipt.
        description: Transaction description.

    Returns:
        dict with keys: success (bool), data (API response dict or error string).
    """
    shortcode = getattr(settings, "MPESA_SHORTCODE", "")
    passkey = getattr(settings, "MPESA_PASSKEY", "")
    callback_url = getattr(settings, "MPESA_CALLBACK_URL", "")

    if not all([shortcode, passkey, callback_url]):
        return {
            "success": False,
            "data": "M-Pesa is not fully configured. Please contact MKJ SUPA CUP admin.",
        }

    # Normalise phone: strip +, ensure starts with 254
    phone = phone_number.replace("+", "").replace(" ", "")
    if phone.startswith("0"):
        phone = "254" + phone[1:]
    elif not phone.startswith("254"):
        phone = "254" + phone

    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    password = _generate_password(shortcode, passkey, timestamp)

    if not account_reference:
        account_reference = getattr(settings, "MPESA_ACCOUNT_REF", "MKJ SUPA CUP2026")
    if not description:
        description = "MKJ SUPA CUP County Registration Fee"

    payload = {
        "BusinessShortCode": shortcode,
        "Password": password,
        "Timestamp": timestamp,
        "TransactionType": "CustomerPayBillOnline",
        "Amount": int(amount),
        "PartyA": phone,
        "PartyB": shortcode,
        "PhoneNumber": phone,
        "CallBackURL": callback_url,
        "AccountReference": account_reference[:12],
        "TransactionDesc": description[:13],
    }

    try:
        token = _get_access_token()
        url = f"{_get_base_url()}/mpesa/stkpush/v1/processrequest"
        headers = {"Authorization": f"Bearer {token}"}
        resp = requests.post(url, json=payload, headers=headers, timeout=30)
        resp.raise_for_status()
        result = resp.json()

        if result.get("ResponseCode") == "0":
            logger.info("STK push sent to %s — CheckoutRequestID: %s",
                        phone, result.get("CheckoutRequestID"))
            return {"success": True, "data": result}
        else:
            logger.warning("STK push failed: %s", result)
            return {"success": False, "data": result.get("ResponseDescription", "STK push failed.")}

    except requests.RequestException as e:
        logger.error("M-Pesa API error: %s", e)
        return {"success": False, "data": f"Network error contacting M-Pesa: {e}"}
    except Exception as e:
        logger.error("M-Pesa unexpected error: %s", e)
        return {"success": False, "data": str(e)}


def query_stk_push_status(checkout_request_id):
    """
    Query the status of a previously initiated STK push.

    Returns:
        dict with keys: success (bool), data (API response dict or error string).
    """
    shortcode = getattr(settings, "MPESA_SHORTCODE", "")
    passkey = getattr(settings, "MPESA_PASSKEY", "")

    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    password = _generate_password(shortcode, passkey, timestamp)

    payload = {
        "BusinessShortCode": shortcode,
        "Password": password,
        "Timestamp": timestamp,
        "CheckoutRequestID": checkout_request_id,
    }

    try:
        token = _get_access_token()
        url = f"{_get_base_url()}/mpesa/stkpushquery/v1/query"
        headers = {"Authorization": f"Bearer {token}"}
        resp = requests.post(url, json=payload, headers=headers, timeout=30)
        resp.raise_for_status()
        return {"success": True, "data": resp.json()}
    except Exception as e:
        logger.error("STK query error: %s", e)
        return {"success": False, "data": str(e)}
