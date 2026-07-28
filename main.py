"""
Affiliate Marketing System — Entry Point
Run: python main.py
"""
import sys
import logging
from pathlib import Path

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).parent))

import uvicorn
from config.settings import APP_HOST, APP_PORT

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    print("""
╔══════════════════════════════════════════════════════╗
║       AFFILIATE MARKETING SYSTEM — AI Powered        ║
║                                                      ║
║  Dashboard:  http://localhost:8000                   ║
║  API Docs:   http://localhost:8000/docs              ║
║                                                      ║
║  9 agents running 24/7 to generate income:           ║
║  • Niche Research  • Product Discovery               ║
║  • Content Creation • SEO • Social Media             ║
║  • Email Marketing • Link Manager                    ║
║  • Analytics • A/B Testing                           ║
╚══════════════════════════════════════════════════════╝
""")
    uvicorn.run(
        "api.main:app",
        host=APP_HOST,
        port=APP_PORT,
        reload=False,
        log_level="info",
    )
