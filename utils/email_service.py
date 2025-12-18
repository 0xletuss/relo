# utils/email_service.py - FIXED VERSION
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
    print(f"   API Key: {brevo_key[:20]}...{brevo_key[-10:]}")
    return api_instance


def send_otp_email(to_email: str, otp_code: str, user_name: str = None):
    """Send OTP verification email"""
    global api_instance
    
    if not api_instance:
        init_email_service()
    
    if not api_instance:
        raise Exception("Email service not initialized. Please set BREVO_API_KEY.")
    
    # IMPORTANT: Use your verified Brevo sender email
    # You need to verify this email in your Brevo dashboard first!
    sender_email = os.getenv("SENDER_EMAIL", "yamiyuhiko@gmail.com")  # Change this to YOUR verified email
    sender_name = os.getenv("SENDER_NAME", "Rolex Store")
    
    print(f"📧 Attempting to send OTP email...")
    print(f"   From: {sender_email}")
    print(f"   To: {to_email}")
    print(f"   OTP: {otp_code}")
    
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
                margin: 0;
                padding: 0;
                background-color: #f4f4f4;
            }}
            .container {{
                max-width: 600px;
                margin: 20px auto;
                background-color: white;
                border-radius: 10px;
                overflow: hidden;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            }}
            .header {{
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 40px;
                text-align: center;
            }}
            .content {{
                padding: 40px;
            }}
            .otp-box {{
                background-color: #f8f9fa;
                border: 2px dashed #667eea;
                border-radius: 10px;
                padding: 30px;
                text-align: center;
                margin: 30px 0;
            }}
            .otp-code {{
                font-size: 42px;
                font-weight: bold;
                color: #667eea;
                letter-spacing: 10px;
                font-family: 'Courier New', monospace;
                margin: 20px 0;
            }}
            .footer {{
                background-color: #f8f9fa;
                padding: 20px;
                text-align: center;
                color: #666;
                font-size: 12px;
            }}
            .warning {{
                background-color: #fff3cd;
                border-left: 4px solid #ffc107;
                padding: 15px;
                margin: 20px 0;
                color: #856404;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1 style="margin: 0;">🔐 Rolex Store</h1>
                <p style="margin: 10px 0 0 0; opacity: 0.9;">Verification Code</p>
            </div>
            
            <div class="content">
                <h2>Hello{' ' + user_name if user_name else ''}!</h2>
                <p>You requested a verification code. Here it is:</p>
                
                <div class="otp-box">
                    <p style="margin: 0; color: #666; font-size: 14px;">Your OTP Code</p>
                    <div class="otp-code">{otp_code}</div>
                    <p style="margin: 0; color: #999; font-size: 12px;">
                        ⏰ Valid for 10 minutes
                    </p>
                </div>
                
                <p>Enter this code to complete your verification.</p>
                
                <div class="warning">
                    <strong>⚠️ Security Notice:</strong><br>
                    • Never share this code with anyone<br>
                    • Rolex Store will never ask for your verification code<br>
                    • If you didn't request this, please ignore this email
                </div>
            </div>
            
            <div class="footer">
                <p><strong>© 2024 Rolex Store</strong></p>
                <p>This is an automated email, please do not reply.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    # Create email object
    send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(
        to=[{"email": to_email, "name": user_name or "User"}],
        sender={"email": sender_email, "name": sender_name},
        subject=subject,
        html_content=html_content
    )
    
    try:
        # Send email
        print("   Sending email via Brevo API...")
        api_response = api_instance.send_transac_email(send_smtp_email)
        print(f"✅ OTP email sent successfully to {to_email}")
        print(f"   Message ID: {api_response.message_id}")
        return True
        
    except ApiException as e:
        error_body = e.body if hasattr(e, 'body') else str(e)
        print(f"❌ Brevo API Error: {error_body}")
        
        # Check for common errors
        if "not a verified sender" in str(error_body).lower():
            print("⚠️  ERROR: Sender email is not verified in Brevo!")
            print(f"   Please verify '{sender_email}' in your Brevo dashboard:")
            print("   https://app.brevo.com/settings/senders")
        elif "invalid api key" in str(error_body).lower():
            print("⚠️  ERROR: Invalid Brevo API key!")
        
        raise Exception(f"Failed to send email: {error_body}")
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")
        raise


def send_welcome_email(to_email: str, user_name: str):
    """Send welcome email to new users"""
    global api_instance
    
    if not api_instance:
        init_email_service()
    
    if not api_instance:
        raise Exception("Email service not initialized")
    
    sender_email = os.getenv("SENDER_EMAIL", "yamiyuhiko@gmail.com")
    sender_name = os.getenv("SENDER_NAME", "Rolex Store")
    
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
                margin: 0;
                padding: 0;
                background-color: #f4f4f4;
            }}
            .container {{
                max-width: 600px;
                margin: 20px auto;
                background-color: white;
                border-radius: 10px;
                overflow: hidden;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            }}
            .header {{
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 50px 40px;
                text-align: center;
            }}
            .content {{
                padding: 40px;
            }}
            .button {{
                display: inline-block;
                padding: 15px 40px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                text-decoration: none;
                border-radius: 25px;
                margin: 20px 0;
                font-weight: bold;
            }}
            ul {{
                background-color: #f8f9fa;
                padding: 20px 40px;
                border-radius: 10px;
            }}
            li {{
                margin: 10px 0;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1 style="margin: 0; font-size: 36px;">Welcome! 🎉</h1>
                <p style="margin: 10px 0 0 0; opacity: 0.9;">You're now part of Rolex Store</p>
            </div>
            
            <div class="content">
                <h2>Hello {user_name}!</h2>
                <p>Thank you for joining <strong>Rolex Store</strong>. We're thrilled to have you with us!</p>
                
                <p><strong>What you can do now:</strong></p>
                <ul>
                    <li>🛍️ Browse our exclusive collection of luxury watches</li>
                    <li>🛒 Add items to your cart</li>
                    <li>📦 Track your orders in real-time</li>
                    <li>👤 Manage your profile and preferences</li>
                    <li>⭐ Save your favorite items</li>
                </ul>
                
                <p>If you have any questions, our support team is always here to help.</p>
                
                <p style="margin-top: 30px;"><strong>Happy Shopping!</strong><br>
                The Rolex Store Team</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(
        to=[{"email": to_email, "name": user_name}],
        sender={"email": sender_email, "name": sender_name},
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