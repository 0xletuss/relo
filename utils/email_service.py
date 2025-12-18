import sib_api_v3_sdk
from sib_api_v3_sdk.rest import ApiException
import os

# Global variable to store the configured API instance
api_instance = None

def init_email_service(api_key: str = None):
    """Initialize Brevo (Sendinblue) email service"""
    global api_instance
    
    # Use provided API key or get from environment
    brevo_key = api_key or os.getenv("BREVO_API_KEY")
    
    if not brevo_key:
        print("⚠️  Warning: BREVO_API_KEY not found!")
        return None
    
    # Configure API key
    configuration = sib_api_v3_sdk.Configuration()
    configuration.api_key['api-key'] = brevo_key
    
    # Create API instance
    api_instance = sib_api_v3_sdk.TransactionalEmailsApi(
        sib_api_v3_sdk.ApiClient(configuration)
    )
    
    print("✅ Brevo Email Service initialized successfully")
    return api_instance


def send_otp_email(to_email: str, otp_code: str, user_name: str = None):
    """Send OTP verification email"""
    global api_instance
    
    if not api_instance:
        init_email_service()
    
    if not api_instance:
        raise Exception("Email service not initialized. Please set BREVO_API_KEY.")
    
    # Create email content
    subject = "Your Verification Code - Rolex Store"
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{
                font-family: Arial, sans-serif;
                line-height: 1.6;
                color: #333;
            }}
            .container {{
                max-width: 600px;
                margin: 0 auto;
                padding: 20px;
                background-color: #f9f9f9;
            }}
            .header {{
                background-color: #1a1a1a;
                color: white;
                padding: 30px;
                text-align: center;
            }}
            .content {{
                background-color: white;
                padding: 40px;
                border-radius: 5px;
                margin-top: 20px;
            }}
            .otp-code {{
                font-size: 32px;
                font-weight: bold;
                color: #1a1a1a;
                text-align: center;
                padding: 20px;
                background-color: #f0f0f0;
                border-radius: 5px;
                margin: 20px 0;
                letter-spacing: 8px;
            }}
            .footer {{
                text-align: center;
                padding: 20px;
                color: #666;
                font-size: 12px;
            }}
            .warning {{
                color: #d9534f;
                font-size: 14px;
                margin-top: 20px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🔐 Rolex Store</h1>
                <p>Verification Code</p>
            </div>
            <div class="content">
                <h2>Hello{' ' + user_name if user_name else ''}!</h2>
                <p>Your verification code is:</p>
                <div class="otp-code">{otp_code}</div>
                <p>This code will expire in <strong>10 minutes</strong>.</p>
                <p>If you didn't request this code, please ignore this email.</p>
                <div class="warning">
                    ⚠️ Never share this code with anyone. Rolex Store will never ask for your verification code.
                </div>
            </div>
            <div class="footer">
                <p>© 2024 Rolex Store. All rights reserved.</p>
                <p>This is an automated email, please do not reply.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    # Create email object
    send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(
        to=[{"email": to_email, "name": user_name or "User"}],
        sender={"email": "noreply@rolexstore.com", "name": "Rolex Store"},
        subject=subject,
        html_content=html_content
    )
    
    try:
        # Send email
        api_response = api_instance.send_transac_email(send_smtp_email)
        print(f"✅ OTP email sent to {to_email}")
        return True
    except ApiException as e:
        print(f"❌ Error sending email: {e}")
        raise Exception(f"Failed to send email: {str(e)}")


def send_welcome_email(to_email: str, user_name: str):
    """Send welcome email to new users"""
    global api_instance
    
    if not api_instance:
        init_email_service()
    
    if not api_instance:
        raise Exception("Email service not initialized")
    
    subject = "Welcome to Rolex Store! 🎉"
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{
                font-family: Arial, sans-serif;
                line-height: 1.6;
                color: #333;
            }}
            .container {{
                max-width: 600px;
                margin: 0 auto;
                padding: 20px;
            }}
            .header {{
                background: linear-gradient(135deg, #1a1a1a 0%, #333 100%);
                color: white;
                padding: 40px;
                text-align: center;
                border-radius: 10px 10px 0 0;
            }}
            .content {{
                background-color: white;
                padding: 40px;
                border: 1px solid #ddd;
                border-top: none;
            }}
            .button {{
                display: inline-block;
                padding: 12px 30px;
                background-color: #1a1a1a;
                color: white;
                text-decoration: none;
                border-radius: 5px;
                margin: 20px 0;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Welcome to Rolex Store! 🎉</h1>
            </div>
            <div class="content">
                <h2>Hello {user_name}!</h2>
                <p>Thank you for joining Rolex Store. We're excited to have you with us!</p>
                <p>You can now:</p>
                <ul>
                    <li>Browse our exclusive collection</li>
                    <li>Add items to your cart</li>
                    <li>Track your orders</li>
                    <li>Manage your profile</li>
                </ul>
                <p>If you have any questions, feel free to reach out to our support team.</p>
                <p>Happy shopping!</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(
        to=[{"email": to_email, "name": user_name}],
        sender={"email": "noreply@rolexstore.com", "name": "Rolex Store"},
        subject=subject,
        html_content=html_content
    )
    
    try:
        api_response = api_instance.send_transac_email(send_smtp_email)
        print(f"✅ Welcome email sent to {to_email}")
        return True
    except ApiException as e:
        print(f"❌ Error sending welcome email: {e}")
        return False