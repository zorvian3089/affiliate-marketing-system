"""
One-time Google OAuth setup for Blogger auto-publishing.

Run this script once:
    python setup_blogger_auth.py

It will:
1. Ask for your Google OAuth Client ID and Secret
2. Open your browser to authorize access
3. Print your refresh token to paste into .env
"""
import json
import urllib.parse
import urllib.request
from http.server import HTTPServer, BaseHTTPRequestHandler

REDIRECT_URI = "http://localhost:8080"
SCOPE = "https://www.googleapis.com/auth/blogger"

print("=" * 60)
print("  Blogger OAuth Setup")
print("=" * 60)
print()
print("Steps before running this script:")
print("1. Go to https://console.cloud.google.com")
print("2. Create a new project (or use existing)")
print("3. Enable 'Blogger API v3'")
print("4. Go to APIs & Services → Credentials")
print("5. Create OAuth 2.0 Client ID (Desktop app type)")
print("6. Copy Client ID and Client Secret below")
print()

CLIENT_ID = input("Paste your Google OAuth Client ID: ").strip()
CLIENT_SECRET = input("Paste your Google OAuth Client Secret: ").strip()

if not CLIENT_ID or not CLIENT_SECRET:
    print("ERROR: Client ID and Secret are required.")
    exit(1)

auth_url = (
    "https://accounts.google.com/o/oauth2/auth"
    f"?client_id={urllib.parse.quote(CLIENT_ID)}"
    f"&redirect_uri={urllib.parse.quote(REDIRECT_URI)}"
    f"&scope={urllib.parse.quote(SCOPE)}"
    "&response_type=code"
    "&access_type=offline"
    "&prompt=consent"
)

print()
print("Opening browser for Google authorization...")
print(f"If browser doesn't open, visit:\n{auth_url}")
print()

import webbrowser
webbrowser.open(auth_url)

auth_code = None


class CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global auth_code
        params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        auth_code = params.get("code", [None])[0]
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(
            b"<h1 style='font-family:sans-serif;color:green'>Authorization successful!</h1>"
            b"<p>You can close this tab and return to the terminal.</p>"
        )

    def log_message(self, format, *args):
        pass  # suppress HTTP log noise


print("Waiting for Google authorization (listening on localhost:8080)...")
server = HTTPServer(("localhost", 8080), CallbackHandler)
server.handle_request()

if not auth_code:
    print("ERROR: Did not receive authorization code.")
    exit(1)

print("Authorization received. Exchanging for refresh token...")

post_data = urllib.parse.urlencode({
    "code": auth_code,
    "client_id": CLIENT_ID,
    "client_secret": CLIENT_SECRET,
    "redirect_uri": REDIRECT_URI,
    "grant_type": "authorization_code",
}).encode()

req = urllib.request.Request(
    "https://oauth2.googleapis.com/token",
    data=post_data,
    headers={"Content-Type": "application/x-www-form-urlencoded"},
)

try:
    with urllib.request.urlopen(req) as resp:
        tokens = json.loads(resp.read())
except urllib.error.HTTPError as e:
    print(f"ERROR: Token exchange failed: {e.read().decode()}")
    exit(1)

refresh_token = tokens.get("refresh_token")
if not refresh_token:
    print("ERROR: No refresh token received. Make sure you clicked 'Allow' and didn't skip consent.")
    exit(1)

print()
print("=" * 60)
print("  SUCCESS! Add these lines to your .env file:")
print("=" * 60)
print()
print(f"GOOGLE_CLIENT_ID={CLIENT_ID}")
print(f"GOOGLE_CLIENT_SECRET={CLIENT_SECRET}")
print(f"GOOGLE_REFRESH_TOKEN={refresh_token}")
print(f"BLOGGER_BLOG_ID=7795913841638669795")
print(f"BLOGGER_BLOG_URL=https://producttrustreview.blogspot.com")
print()
print("After adding to .env, the system will auto-publish articles to your blog!")
