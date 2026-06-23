#!/usr/bin/env python
"""Pre-deployment sanity check."""
from utils.analytics import ensure_public_user_id, behavior_offer_snapshot, days_since_first_seen
from utils.reporting import render_report_html, build_offer_text, build_meta
from config import settings
import json
from pathlib import Path

print("=" * 60)
print("PRE-DEPLOYMENT CHECKS")
print("=" * 60)

# 1. Analytics module
print("\n1. Testing analytics...")
user_id = ensure_public_user_id(99999, source_tag="deploy_test")
print(f"   ✓ Generated public_user_id: {user_id}")

days = days_since_first_seen(user_id)
print(f"   ✓ Days since first seen: {days}")

snapshot = behavior_offer_snapshot(user_id)
print(f"   ✓ Behavior snapshot loaded: {len(snapshot)} keys")

# 2. Config validation
print("\n2. Testing config...")
try:
    settings.validate()
    print("   ✓ Required env vars (BOT_TOKEN, OPENAI_API_KEY) are set")
except ValueError as e:
    print(f"   ✗ Config error: {e}")
    exit(1)

# 3. Reporting
print("\n3. Testing reporting...")
try:
    offer = build_offer_text()
    assert len(offer) > 50, "Offer should have content"
    print(f"   ✓ Offer text generated ({len(offer)} chars)")
    
    # Check HTML rendering can be called
    test_report = {
        "digital_human": {"current_state": "Test"},
        "career_decision": {"recommended_main_path": "Test"},
        "action_plan": {"today": {"action": "Test"}},
        "closing_message": "Test",
    }
    meta = build_meta(test_report, user_name="TestUser")
    html = render_report_html(test_report, meta)
    assert "Career GPS" in html or "NextYou" in html, "HTML should contain report header"
    print(f"   ✓ HTML rendering works ({len(html)} chars)")
except Exception as e:
    print(f"   ✗ Reporting error: {e}")
    exit(1)

# 4. Check registry file
registry_path = Path(settings.analytics_registry_path)
if registry_path.exists():
    registry = json.loads(registry_path.read_text())
    print(f"\n4. Analytics registry:")
    print(f"   ✓ File exists at {registry_path}")
    print(f"   ✓ Contains {len(registry.get('users', {}))} users")
else:
    print(f"\n4. Analytics registry:")
    print(f"   ✓ Will be created at {registry_path} on first user")

# 5. Check events log
events_path = Path(settings.analytics_events_log_path)
if events_path.exists():
    lines = len(events_path.read_text().strip().split("\n"))
    print(f"\n5. Events log:")
    print(f"   ✓ File exists at {events_path}")
    print(f"   ✓ Contains {lines} events")
else:
    print(f"\n5. Events log:")
    print(f"   ✓ Will be created at {events_path} on first event")

print("\n" + "=" * 60)
print("✓ ALL PRE-DEPLOYMENT CHECKS PASSED")
print("=" * 60)
print("\nReady to deploy to Railway!")
print("\nNew environment variables to add:")
print("  - GOOGLE_SHEETS_WEBHOOK_URL")
print("  - ANALYTICS_REGISTRY_PATH=/data/reports/user_registry.json")
print("  - ANALYTICS_EVENTS_LOG_PATH=/data/reports/behavior_events.jsonl")
