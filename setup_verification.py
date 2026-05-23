#!/usr/bin/env python3
"""
Quick setup script for AI Workflow Automation Sidecar.
Prepares environment and verifies all dependencies are installed.
"""
import os
import sys
import subprocess
import asyncio
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None


def load_environment_files():
    """Load environment variables from common repo locations."""
    if load_dotenv is None:
        return

    repo_env = Path('.env')
    backend_env = Path('backend/.env')

    if repo_env.exists():
        load_dotenv(dotenv_path=repo_env, override=False)

    if backend_env.exists():
        load_dotenv(dotenv_path=backend_env, override=False)


def check_python_version():
    """Check Python version."""
    if sys.version_info < (3, 9):
        print("❌ Python 3.9+ required")
        return False
    print(f"✅ Python {sys.version_info.major}.{sys.version_info.minor}")
    return True


def check_dependencies():
    """Check if required packages are installed."""
    required = {
        'fastapi': 'FastAPI',
        'sqlalchemy': 'SQLAlchemy',
        'pydantic': 'Pydantic',
        'httpx': 'httpx',
        'openai': 'OpenAI',
    }
    
    print("\n📦 Checking dependencies...")
    all_ok = True
    
    for package, name in required.items():
        try:
            __import__(package)
            print(f"✅ {name} installed")
        except ImportError:
            print(f"❌ {name} NOT installed")
            all_ok = False
    
    if not all_ok:
        print("\n📥 Install missing dependencies with:")
        print("   pip install -r backend/requirements.txt")
        return False
    
    return True


def check_environment_variables():
    """Check if required environment variables are set."""
    print("\n🔐 Checking environment variables...")
    
    required_vars = [
        'DATABASE_URL',
        'GOOGLE_CLIENT_ID',
        'GOOGLE_CLIENT_SECRET',
        'SECRET_KEY',
    ]
    
    ticket_vars = [
        'N8N_WEBHOOK_URL',
        'N8N_WEBHOOK_SECRET',
    ]
    
    missing = []
    for var in required_vars:
        if not os.environ.get(var):
            missing.append(var)
        else:
            print(f"✅ {var} set")
    
    for var in ticket_vars:
        if not os.environ.get(var):
            print(f"⚠️  {var} not set (optional for development)")
        else:
            print(f"✅ {var} set")
    
    if missing:
        print(f"\n❌ Missing required variables: {', '.join(missing)}")
        print("   Copy .env.example to .env and fill in required values")
        return False
    
    return True


def check_n8n():
    """Check if n8n is running."""
    print("\n🔄 Checking n8n...")
    try:
        import httpx
        response = httpx.get('http://localhost:5678/api/v1/workflows', timeout=3)
        if response.status_code == 200:
            print("✅ n8n is running on http://localhost:5678")
            return True
    except Exception:
        pass
    
    print("⚠️  n8n is not running on http://localhost:5678")
    print("   Start n8n with: npm start (from n8n installation)")
    print("   Or visit: https://docs.n8n.io/hosting/installation/docker/")
    return False


def check_database():
    """Check database connectivity."""
    print("\n🗄️  Checking database...")
    
    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        print("❌ DATABASE_URL not set")
        return False
    
    try:
        import asyncpg

        async def _probe_database(url: str):
            conn = await asyncpg.connect(url)
            try:
                await conn.execute("SELECT 1")
            finally:
                await conn.close()

        # asyncpg expects postgresql:// scheme.
        probe_url = db_url.replace('postgresql+asyncpg://', 'postgresql://', 1)
        asyncio.run(_probe_database(probe_url))
        print("✅ Database connection successful")
        return True
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False


def create_env_file():
    """Create .env file from .env.example if it doesn't exist."""
    env_path = Path('.env')
    example_path = Path('.env.example')
    
    if env_path.exists():
        print(f"\n✅ .env file already exists")
        return True
    
    if not example_path.exists():
        print(f"⚠️  .env.example not found")
        return False
    
    print(f"\n📝 Creating .env from .env.example...")
    with open(example_path) as src, open(env_path, 'w') as dst:
        dst.write(src.read())
    
    print(f"✅ .env created. Please fill in required values:")
    print(f"   nano .env")
    return True


def main():
    """Run all checks."""
    load_environment_files()

    print("=" * 60)
    print("🚀 AI Workflow Automation Sidecar - Setup Verification")
    print("=" * 60)
    
    checks = [
        ("Python version", check_python_version),
        ("Dependencies", check_dependencies),
        ("Environment variables", check_environment_variables),
        ("n8n", check_n8n),
        ("Database", check_database),
    ]
    
    results = {}
    for name, check_func in checks:
        try:
            results[name] = check_func()
        except Exception as e:
            print(f"❌ {name} check failed: {e}")
            results[name] = False
    
    print("\n" + "=" * 60)
    print("✅ SETUP SUMMARY")
    print("=" * 60)
    
    required_checks = ["Python version", "Dependencies", "Environment variables", "Database"]
    optional_checks = ["n8n"]
    
    all_required_ok = all(results.get(check, False) for check in required_checks)
    all_optional_ok = all(results.get(check, False) for check in optional_checks)
    
    print("\n📋 Required Checks:")
    for check in required_checks:
        status = "✅" if results.get(check) else "❌"
        print(f"  {status} {check}")
    
    print("\n📋 Optional Checks:")
    for check in optional_checks:
        status = "✅" if results.get(check) else "⚠️ "
        print(f"  {status} {check}")
    
    print("\n" + "=" * 60)
    
    if all_required_ok:
        print("✅ Setup verification PASSED!")
        print("\n🎉 You're ready to start the application:")
        print("   1. Backend:  python -m uvicorn app.main:app --reload --port 8000")
        print("   2. Frontend: npm run dev")
        print("   3. n8n:      Already running on http://localhost:5678")
        print("\n📖 Documentation: See WORKFLOW_AUTOMATION_GUIDE.md")
        return 0
    else:
        print("❌ Setup verification FAILED!")
        print("\n Please fix the issues above and run this script again.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
