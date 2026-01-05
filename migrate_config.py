#!/usr/bin/env python3
"""
Migration script to convert old config.json to new .env + sensors.json format
"""
import json
import os
import shutil
from datetime import datetime


def migrate_config():
    """Migrate old config.json to .env and sensors.json"""

    config_file = 'config.json'
    env_file = '.env'
    sensors_file = 'sensors.json'

    # Check if config.json exists
    if not os.path.exists(config_file):
        print(f"❌ {config_file} not found. Nothing to migrate.")
        return False

    # Check if migration already done
    if os.path.exists(env_file) and os.path.exists(sensors_file):
        response = input(f"⚠️  {env_file} and {sensors_file} already exist. Overwrite? (y/N): ")
        if response.lower() != 'y':
            print("Migration cancelled.")
            return False

    # Load old config
    print(f"📖 Reading {config_file}...")
    try:
        with open(config_file, 'r') as f:
            config = json.load(f)
    except Exception as e:
        print(f"❌ Failed to read {config_file}: {e}")
        return False

    # Create backup
    backup_file = f"{config_file}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    print(f"💾 Creating backup: {backup_file}")
    shutil.copy2(config_file, backup_file)

    # Create .env file
    print(f"📝 Creating {env_file}...")

    # Handle multi-line PUBLIC_KEY properly
    public_key = config.get('public_key', '').replace('\r\n', '\\n').replace('\n', '\\n')

    env_content = f"""TOKEN_ID={config.get('token_id', '')}
DEVICE_ID={config.get('device_id', '')}
STATION_ID={config.get('station_id', '')}
PUBLIC_KEY="{public_key}"
DATAPAGE_URL={config.get('datapage_url', '')}
ENDPOINT={config.get('endpoint', 'https://cems.cpcb.gov.in/v1.0/industry/data')}
ERROR_ENDPOINT_URL={config.get('error_endpoint_url', 'http://65.1.87.62/ocms/Cpcb/add_cpcberror')}
ERROR_SESSION_COOKIE={config.get('error_session_cookie', '')}
"""

    try:
        with open(env_file, 'w') as f:
            f.write(env_content)
        print(f"✅ Created {env_file}")
    except Exception as e:
        print(f"❌ Failed to create {env_file}: {e}")
        return False

    # Create sensors.json file
    print(f"📝 Creating {sensors_file}...")
    sensors_data = {
        'server_running': config.get('server_running', False),
        'sensors': config.get('sensors', [])
    }

    try:
        with open(sensors_file, 'w') as f:
            json.dump(sensors_data, f, indent=2)
        print(f"✅ Created {sensors_file}")
    except Exception as e:
        print(f"❌ Failed to create {sensors_file}: {e}")
        return False

    # Print migration summary
    print("\n" + "="*60)
    print("✨ Migration completed successfully!")
    print("="*60)
    print(f"\n📄 Files created:")
    print(f"   • {env_file} - Environment variables (static config)")
    print(f"   • {sensors_file} - Sensor configuration (editable via web UI)")
    print(f"\n💾 Backup created:")
    print(f"   • {backup_file}")

    print(f"\n⚠️  Important notes:")
    print(f"   • The old {config_file} has been backed up")
    print(f"   • Status fields (last_fetch_success, last_send_success, etc.) are now in-memory")
    print(f"   • They will reset on application restart")
    print(f"   • calibration_mode has been removed (always 15-min intervals)")
    print(f"   • Edit {env_file} manually and restart app to change environment variables")
    print(f"   • Edit sensors via web UI or modify {sensors_file} directly")

    print(f"\n🚀 Next steps:")
    print(f"   1. Install new dependency: pip install python-dotenv")
    print(f"   2. Review {env_file} and {sensors_file}")
    print(f"   3. Restart the application: python datalogger_app.py")
    print(f"   4. Access web UI: http://localhost:9999")
    print("="*60 + "\n")

    return True


if __name__ == '__main__':
    print("\n" + "="*60)
    print("🔄 Datalogger Configuration Migration Script")
    print("="*60)
    print("\nThis script will migrate config.json to:")
    print("  • .env (environment variables)")
    print("  • sensors.json (sensor configuration)")
    print()

    success = migrate_config()

    if not success:
        print("\n❌ Migration failed or cancelled.")
        exit(1)

    exit(0)
