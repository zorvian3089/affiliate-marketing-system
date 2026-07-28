"""Push About, Privacy Policy, Disclaimer pages and add disclaimers to posts."""
import sys, urllib.parse, urllib.request, json, os
sys.path.insert(0, '.')
from dotenv import load_dotenv
load_dotenv()

BLOG_ID = '7795913841638669795'

def get_token():
    data = urllib.parse.urlencode({
        'client_id': os.getenv('GOOGLE_CLIENT_ID'),
        'client_secret': os.getenv('GOOGLE_CLIENT_SECRET'),
        'refresh_token': os.getenv('GOOGLE_REFRESH_TOKEN'),
        'grant_type': 'refresh_token'
    }).encode()
    with urllib.request.urlopen(urllib.request.Request(
        'https://oauth2.googleapis.com/token', data=data,
        headers={'Content-Type': 'application/x-www-form-urlencoded'})) as r:
        return json.loads(r.read())['access_token']

def blogger_api(method, path, token, body=None):
    url = f'https://www.googleapis.com/blogger/v3{path}'
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, method=method,
        headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read()) if r.length else {}
    except urllib.error.HTTPError as e:
        err = e.read().decode()
        print(f"  ERROR {e.code}: {err[:200]}")
        return {'error': err}

DISCLAIMER_BANNER = """<div style="background:#fff3cd;border-left:4px solid #f0a500;padding:12px 16px;margin-bottom:24px;border-radius:4px;font-size:14px;">
⚠️ <strong>Affiliate Disclosure:</strong> This article contains affiliate links. We may earn a commission if you purchase through our links, at no extra cost to you. We only recommend products we believe can genuinely help.
</div>"""

PAGES = [
    {
        "title": "About Us",
        "content": """<h2>About Health Reviews Hub</h2>
<p>Health Reviews Hub is an independent health and wellness review website. We research, test, and analyze popular health supplements and wellness programs to help you make informed buying decisions.</p>
<h3>Our Mission</h3>
<p>We believe everyone deserves honest, unbiased information before spending money on health products. We dig deep into ingredients, clinical studies, and real customer experiences — so you get the full picture, not just marketing claims.</p>
<h3>What We Cover</h3>
<ul>
<li>Weight loss supplements</li>
<li>Blood sugar support</li>
<li>Joint health &amp; mobility</li>
<li>Sleep and stress relief</li>
<li>Brain health and memory</li>
</ul>
<h3>Our Review Process</h3>
<p>Every product we review goes through thorough analysis:</p>
<ul>
<li>✓ Ingredient research and scientific backing</li>
<li>✓ Customer feedback analysis</li>
<li>✓ Pricing and value assessment</li>
<li>✓ Company reputation check</li>
</ul>
<h3>Affiliate Disclosure</h3>
<p>Some links on this site are affiliate links. If you click and make a purchase, we may earn a small commission at no extra cost to you. This helps us keep the site running and free. We only recommend products we genuinely believe can help.</p>"""
    },
    {
        "title": "Privacy Policy",
        "content": """<h2>Privacy Policy — Health Reviews Hub</h2>
<p><em>Last updated: June 2026</em></p>
<p>This Privacy Policy describes how Health Reviews Hub collects and uses information when you visit our website.</p>
<h3>Information We Collect</h3>
<p>We do not collect personal information unless you voluntarily contact us. We may use Google Analytics to track anonymous visitor statistics such as pages visited, time on site, and country of origin.</p>
<h3>Cookies</h3>
<p>This site uses cookies through the Google Blogger platform and Google Analytics. You can disable cookies in your browser settings at any time.</p>
<h3>Affiliate Links</h3>
<p>This site contains affiliate links to products on third-party websites including ClickBank. When you click these links and make a purchase, we may receive a commission. This does not affect the price you pay.</p>
<h3>Third Party Links</h3>
<p>Our articles may link to third-party websites. We are not responsible for the privacy practices or content of those sites.</p>
<h3>Children's Privacy</h3>
<p>This website is not directed at children under 13. We do not knowingly collect information from children.</p>
<h3>Contact</h3>
<p>For privacy questions, contact us at: <strong>healthreviewshub@gmail.com</strong></p>"""
    },
    {
        "title": "Disclaimer",
        "content": """<h2>Disclaimer — Health Reviews Hub</h2>
<h3>Affiliate Disclaimer</h3>
<p>Health Reviews Hub participates in affiliate marketing programs including the ClickBank affiliate program. We earn commissions on qualifying purchases made through our links, at no additional cost to you. This helps support our independent research and review work.</p>
<h3>Medical Disclaimer</h3>
<p><strong>The content on this website is for informational purposes only and does not constitute medical advice.</strong> Always consult a qualified healthcare professional before starting any supplement, diet program, or health regimen. Individual results mentioned in product reviews are not typical and may vary from person to person.</p>
<h3>FTC Disclosure</h3>
<p>In accordance with the Federal Trade Commission (FTC) guidelines, we disclose that this website receives compensation through affiliate marketing partnerships. All opinions and reviews expressed on this site are our own honest assessments.</p>
<h3>Accuracy</h3>
<p>We strive to ensure all information is accurate at the time of publishing. Product formulations, prices, and availability may change. Always verify current information on the product's official website.</p>"""
    }
]

token = get_token()
print("Token obtained OK\n")

# 1. Create pages
print("Creating trust pages...")
for page in PAGES:
    result = blogger_api('POST', f'/blogs/{BLOG_ID}/pages', token, {
        "kind": "blogger#page",
        "title": page["title"],
        "content": page["content"]
    })
    if 'error' not in result:
        print(f"  ✓ Created: {page['title']} → {result.get('url', 'ok')}")
    else:
        print(f"  ✗ Failed: {page['title']}")

# 2. Add disclaimer to existing posts
print("\nAdding disclaimer to existing posts...")
posts = blogger_api('GET', f'/blogs/{BLOG_ID}/posts?maxResults=20', token)
for post in posts.get('items', []):
    content = post.get('content', '')
    if '⚠️' not in content and 'Affiliate Disclosure' not in content:
        updated_content = DISCLAIMER_BANNER + content
        result = blogger_api('PUT', f'/blogs/{BLOG_ID}/posts/{post["id"]}', token, {
            "kind": "blogger#post",
            "id": post["id"],
            "title": post["title"],
            "content": updated_content
        })
        if 'error' not in result:
            print(f"  ✓ Disclaimer added: {post['title'][:50]}")
        else:
            print(f"  ✗ Failed: {post['title'][:50]}")

print("\nDone! Check https://producttrustreview.blogspot.com")
