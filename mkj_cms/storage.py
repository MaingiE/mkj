from urllib.parse import urlparse


def resolve_cloudinary_config(cloudinary_url="", cloud_name="", api_key="", api_secret=""):
    """Resolve Cloudinary credentials from either a full CLOUDINARY_URL or individual env vars."""
    config = {
        "CLOUD_NAME": cloud_name or "",
        "API_KEY": api_key or "",
        "API_SECRET": api_secret or "",
    }

    if cloudinary_url:
        parsed = urlparse(cloudinary_url)
        config["CLOUD_NAME"] = parsed.hostname or config["CLOUD_NAME"]
        config["API_KEY"] = parsed.username or config["API_KEY"]
        config["API_SECRET"] = parsed.password or config["API_SECRET"]

    return config


def should_use_cloudinary_storage(debug=False, cloudinary_url="", cloud_name="", api_key="", api_secret=""):
    config = resolve_cloudinary_config(
        cloudinary_url=cloudinary_url,
        cloud_name=cloud_name,
        api_key=api_key,
        api_secret=api_secret,
    )
    has_credentials = bool(config["CLOUD_NAME"] and config["API_KEY"] and config["API_SECRET"])
    return (not debug and has_credentials) or has_credentials
