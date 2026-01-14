"""Script to check and optionally stop local PostgreSQL service."""

import subprocess
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.config import settings
from src.core.logger import configure_logging, get_logger

logger = get_logger(__name__)


def check_postgresql_services() -> list[str]:
    """Check for running PostgreSQL services on Windows."""
    try:
        # Get all services and filter PostgreSQL
        result = subprocess.run(
            ["sc", "query", "type=", "service", "state=", "all"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        
        services = []
        
        # Try PowerShell Get-Service command first (more reliable)
        try:
            ps_result = subprocess.run(
                [
                    "powershell",
                    "-Command",
                    "Get-Service | Where-Object {$_.Name -like '*postgresql*'} | Select-Object -ExpandProperty Name"
                ],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if ps_result.returncode == 0 and ps_result.stdout.strip():
                services = [s.strip() for s in ps_result.stdout.strip().split("\n") if s.strip()]
                if services:
                    return services
        except Exception:
            pass
        
        # Fallback to sc query parsing
        current_service = None
        for line in result.stdout.split("\n"):
            line = line.strip()
            # Look for SERVICE_NAME line
            if line.startswith("SERVICE_NAME:"):
                service_name = line.replace("SERVICE_NAME:", "").strip()
                if "postgresql" in service_name.lower():
                    if service_name not in services:
                        services.append(service_name)
        
        return services
    except Exception as e:
        logger.error(f"Error checking services: {e}")
        return []


def get_service_status(service_name: str) -> str:
    """Get status of a Windows service."""
    try:
        result = subprocess.run(
            ["sc", "query", service_name],
            capture_output=True,
            text=True,
            timeout=5,
        )
        
        for line in result.stdout.split("\n"):
            if "STATE" in line:
                return line.strip()
        
        return "Unknown"
    except Exception as e:
        logger.error(f"Error getting service status: {e}")
        return "Error"


def stop_service(service_name: str) -> bool:
    """Stop a Windows service."""
    try:
        result = subprocess.run(
            ["sc", "stop", service_name],
            capture_output=True,
            text=True,
            timeout=30,
        )
        
        if result.returncode == 0:
            return True
        else:
            logger.error(f"Failed to stop service: {result.stderr}")
            return False
    except Exception as e:
        logger.error(f"Error stopping service: {e}")
        return False


def main():
    """Main function."""
    configure_logging("INFO")
    
    # Parse database URL to get port
    db_url = settings.database_url
    db_port = 5433  # default
    if "@" in db_url and ":" in db_url:
        parts = db_url.split("@")
        if len(parts) > 1:
            host_part = parts[1].split("/")[0]
            if ":" in host_part:
                _, port_str = host_part.rsplit(":", 1)
                try:
                    db_port = int(port_str)
                except ValueError:
                    pass
    
    logger.info("=" * 60)
    logger.info("Checking Local PostgreSQL Services")
    logger.info("=" * 60)
    logger.info(f"Database URL port: {db_port}")
    logger.info("")
    
    # Check for PostgreSQL services
    services = check_postgresql_services()
    
    if not services:
        logger.info("No PostgreSQL services found")
        logger.info("")
        logger.info("✅ No local PostgreSQL is running")
        logger.info("SSH tunnel should be created automatically")
        return
    
    logger.info(f"Found {len(services)} PostgreSQL service(s):")
    logger.info("")
    
    running_services = []
    for service in services:
        status = get_service_status(service)
        logger.info(f"  Service: {service}")
        logger.info(f"  Status: {status}")
        
        if "RUNNING" in status:
            running_services.append(service)
        logger.info("")
    
    if not running_services:
        logger.info("✅ No PostgreSQL services are running")
        logger.info("SSH tunnel should be created automatically")
        return
    
    logger.warning("⚠️  WARNING: Local PostgreSQL is running!")
    logger.warning("")
    logger.warning("This prevents SSH tunnel from being created automatically.")
    logger.warning("")
    logger.info("Options:")
    logger.info("")
    logger.info("Option 1: Stop local PostgreSQL (if not needed)")
    logger.info("  Run as Administrator:")
    logger.info(f"    Stop-Service {running_services[0]}")
    logger.info("")
    logger.info("Option 2: Use different local port for server connection")
    logger.info("  In .env file, change:")
    logger.info(f"    DATABASE_URL=postgresql+asyncpg://bot_user:password@localhost:5432/silent_couple_bot")
    logger.info("    DATABASE_REMOTE_PORT=5433  # Port on server")
    logger.info("")
    logger.info("Option 3: Change local PostgreSQL port")
    logger.info("  Edit postgresql.conf and change port to something else (e.g., 5434)")
    logger.info("")


if __name__ == "__main__":
    main()

