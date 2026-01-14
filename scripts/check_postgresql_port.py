"""Script to check which port local PostgreSQL is listening on."""

import subprocess
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.logger import configure_logging, get_logger

logger = get_logger(__name__)


def check_postgresql_port() -> list[int]:
    """Check which ports PostgreSQL is listening on."""
    ports = []
    
    try:
        # Check using netstat
        result = subprocess.run(
            ["netstat", "-an"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        
        for line in result.stdout.split("\n"):
            if "LISTENING" in line and "127.0.0.1" in line:
                # Extract port
                parts = line.split()
                if len(parts) >= 2:
                    addr = parts[1]
                    if ":" in addr:
                        _, port_str = addr.rsplit(":", 1)
                        try:
                            port = int(port_str)
                            # Check if it's likely PostgreSQL port (5432-5439)
                            if 5432 <= port <= 5439:
                                ports.append(port)
                        except ValueError:
                            pass
    except Exception as e:
        logger.debug(f"Error checking netstat: {e}")
    
    # Also try PowerShell
    try:
        ps_result = subprocess.run(
            [
                "powershell",
                "-Command",
                "Get-NetTCPConnection | Where-Object {$_.LocalAddress -eq '127.0.0.1' -and $_.State -eq 'Listen' -and $_.LocalPort -ge 5432 -and $_.LocalPort -le 5439} | Select-Object -ExpandProperty LocalPort | Sort-Object -Unique"
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if ps_result.returncode == 0 and ps_result.stdout.strip():
            ps_ports = [int(p.strip()) for p in ps_result.stdout.strip().split("\n") if p.strip().isdigit()]
            for port in ps_ports:
                if port not in ports:
                    ports.append(port)
    except Exception:
        pass
    
    return sorted(ports)


def main():
    """Main function."""
    configure_logging("INFO")
    
    logger.info("=" * 60)
    logger.info("Checking Local PostgreSQL Ports")
    logger.info("=" * 60)
    logger.info("")
    
    ports = check_postgresql_port()
    
    if not ports:
        logger.info("✅ No PostgreSQL ports found listening on localhost")
        logger.info("SSH tunnel should be created automatically")
    else:
        logger.warning(f"⚠️  Found PostgreSQL listening on port(s): {', '.join(map(str, ports))}")
        logger.warning("")
        logger.warning("If your DATABASE_URL uses one of these ports, SSH tunnel won't be created.")
        logger.warning("")
        logger.info("Solutions:")
        logger.info("")
        logger.info("1. Stop local PostgreSQL:")
        logger.info("   Stop-Service postgresql-x64-18")
        logger.info("")
        logger.info("2. Use different port in DATABASE_URL:")
        if 5432 in ports:
            logger.info("   DATABASE_URL=postgresql+asyncpg://bot_user:password@localhost:5433/silent_couple_bot")
            logger.info("   DATABASE_REMOTE_PORT=5432  # Port on server")
        else:
            logger.info("   DATABASE_URL=postgresql+asyncpg://bot_user:password@localhost:5432/silent_couple_bot")
        logger.info("")


if __name__ == "__main__":
    main()

