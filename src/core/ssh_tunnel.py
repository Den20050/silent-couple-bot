"""SSH tunnel management for Redis and PostgreSQL connections."""

import subprocess
import time
import socket
import os
from typing import Optional
from pathlib import Path

from src.core.config import settings
from src.core.logger import get_logger

logger = get_logger(__name__)

# Try to load .env file if python-dotenv is available
try:
    from dotenv import load_dotenv
    # Load .env file to make variables available via os.getenv()
    load_dotenv()
except ImportError:
    # python-dotenv not installed, variables must be set in environment
    pass


def check_port_available(host: str, port: int, timeout: float = 1.0) -> bool:
    """Check if a port is available (can connect to it).
    
    Args:
        host: Host address
        port: Port number
        timeout: Connection timeout in seconds
        
    Returns:
        True if port is accessible, False otherwise
    """
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except Exception:
        return False


def check_redis_connection() -> bool:
    """Check if Redis is actually accessible by trying to connect.
    
    Uses synchronous Redis client to avoid event loop issues.
    
    Returns:
        True if Redis is accessible and responds to PING, False otherwise
    """
    try:
        import redis
        
        # Use synchronous Redis client for checking (avoids event loop issues)
        try:
            client = redis.Redis(
                host="127.0.0.1",
                port=6379,
                db=0,
                socket_connect_timeout=1.0,
                socket_timeout=1.0,
                decode_responses=True,
            )
            client.ping()
            client.close()
            return True
        except Exception:
            return False
    except ImportError:
        # redis package not available, fallback to port check
        logger.debug("redis package not available, using port check only")
        return check_port_available("127.0.0.1", 6379, timeout=0.5)
    except Exception as e:
        logger.debug(f"Redis connection check failed: {e}, using port check")
        # Fallback to port check
        return check_port_available("127.0.0.1", 6379, timeout=0.5)


def check_redis_accessible() -> bool:
    """Check if Redis is accessible on localhost:6379.
    
    Returns:
        True if Redis is accessible, False otherwise
    """
    # First check if port is open
    if not check_port_available("127.0.0.1", 6379, timeout=0.5):
        return False
    
    # Then try to actually connect to Redis
    return check_redis_connection()


def check_postgresql_connection(host: str = "127.0.0.1", port: int = 5432) -> bool:
    """Check if PostgreSQL port is accessible.
    
    Args:
        host: Host address (default: 127.0.0.1)
        port: Port number (default: 5432)
    
    Returns:
        True if PostgreSQL port is accessible, False otherwise
    
    Note:
        This function only checks port availability, not actual database connection.
        Full connection test would require database credentials and async context.
    """
    return check_port_available(host, port, timeout=1.0)


def check_if_local_postgresql(host: str = "127.0.0.1", port: int = 5432) -> bool:
    """Check if PostgreSQL on given host:port is local Windows PostgreSQL.
    
    Args:
        host: Host address (default: 127.0.0.1)
        port: Port number (default: 5432)
    
    Returns:
        True if it's local Windows PostgreSQL, False otherwise or if cannot determine
    """
    try:
        import asyncpg
        import asyncio
        
        # Try to connect and get version
        async def check():
            try:
                # Use test connection without database
                conn = await asyncpg.connect(
                    host=host,
                    port=port,
                    user="postgres",  # Try default user
                    password="",  # Empty password for test
                    database="postgres",
                    timeout=1.0,
                )
                version = await conn.fetchval("SELECT version()")
                await conn.close()
                
                # Check if it's Windows PostgreSQL
                if "windows" in version.lower() or "msvc" in version.lower():
                    return True
                return False
            except Exception:
                # If connection fails, we can't determine
                return False
        
        # Run async check
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If loop is running, we can't use it
                return False
        except RuntimeError:
            # No event loop, create new one
            pass
        
        return asyncio.run(check())
    except Exception:
        # If asyncpg is not available or other error, return False
        return False


def create_ssh_tunnel(
    ssh_host: str,
    ssh_user: str = "root",
    local_port: int = 6379,
    remote_port: int = 6379,
    ssh_port: int = 22,
    service_name: str = "service",
) -> Optional[subprocess.Popen]:
    """Create SSH tunnel for a service (Redis, PostgreSQL, etc.).
    
    Args:
        ssh_host: SSH server hostname or IP
        ssh_user: SSH username
        local_port: Local port to forward
        remote_port: Remote port to forward to
        ssh_port: SSH server port
        service_name: Name of the service (for logging)
        
    Returns:
        Popen process object if tunnel created successfully, None otherwise
    """
    try:
        # Check if port is already in use (tunnel might already exist)
        if check_port_available("127.0.0.1", local_port, timeout=0.5):
            # Port is open, verify it's the expected service
            if local_port == 6379:
                # Redis port - verify it's Redis
                if check_redis_connection():
                    logger.info(
                        f"Port {local_port} is already accessible and Redis responds, "
                        "assuming tunnel already exists"
                    )
                    return None
            elif local_port == 5432:
                # PostgreSQL port - verify it's PostgreSQL
                if check_postgresql_connection("127.0.0.1", 5432):
                    logger.info(
                        f"Port {local_port} is already accessible and PostgreSQL responds, "
                        "assuming tunnel already exists"
                    )
                    return None
            
            logger.warning(
                f"Port {local_port} is open but {service_name} doesn't respond, "
                "will try to create new tunnel"
            )
            # Port might be occupied by something else, we'll try anyway
        
        # Build SSH command
        ssh_cmd = [
            "ssh",
            "-N",  # No remote command execution
            "-L", f"{local_port}:127.0.0.1:{remote_port}",  # Local port forwarding
            "-o", "StrictHostKeyChecking=no",  # Auto-accept host key
            "-o", "UserKnownHostsFile=/dev/null",  # Don't save host key
            "-o", "LogLevel=ERROR",  # Suppress SSH output
            f"{ssh_user}@{ssh_host}",
            "-p", str(ssh_port),
        ]
        
        logger.info(
            f"Creating SSH tunnel for {service_name}: {ssh_user}@{ssh_host}:{ssh_port} -> "
            f"127.0.0.1:{local_port} (remote: {remote_port})"
        )
        
        # Start SSH tunnel in background
        process = subprocess.Popen(
            ssh_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.PIPE,
        )
        
        # Wait a bit to check if tunnel started successfully
        time.sleep(1)
        
        if process.poll() is not None:
            # Process exited immediately, something went wrong
            stdout, stderr = process.communicate()
            logger.error(
                f"SSH tunnel failed to start",
                stdout=stdout.decode() if stdout else None,
                stderr=stderr.decode() if stderr else None,
            )
            return None
        
        # Check if port is now accessible
        if check_port_available("127.0.0.1", local_port, timeout=2.0):
            logger.info(f"SSH tunnel for {service_name} created successfully")
            return process
        else:
            logger.warning(
                f"SSH tunnel process for {service_name} started but port is not accessible yet"
            )
            # Give it more time
            time.sleep(2)
            if check_port_available("127.0.0.1", local_port, timeout=2.0):
                logger.info(f"SSH tunnel for {service_name} is now accessible")
                return process
            else:
                logger.error(f"SSH tunnel port for {service_name} is still not accessible")
                process.terminate()
                return None
                
    except FileNotFoundError:
        logger.error(
            "SSH command not found. Please install OpenSSH client or "
            "create tunnel manually"
        )
        return None
    except Exception as e:
        logger.error(f"Failed to create SSH tunnel: {e}", exc_info=True)
        return None


def get_ssh_config_from_env(service: str = "REDIS") -> Optional[tuple[str, str, int]]:
    """Get SSH configuration from environment variables or settings.
    
    Args:
        service: Service name prefix ("REDIS" or "DATABASE")
    
    Checks for:
    - {SERVICE}_SSH_HOST (required)
    - {SERVICE}_SSH_USER (default: root)
    - {SERVICE}_SSH_PORT (default: 22)
    
    First tries to get from settings (pydantic), then falls back to os.getenv().
    
    Returns:
        Tuple of (host, user, port) if configured, None otherwise
    """
    # Try to get from settings first (pydantic-settings loads from .env)
    if service == "DATABASE":
        ssh_host = settings.database_ssh_host
        ssh_user = settings.database_ssh_user or "root"
        ssh_port = settings.database_ssh_port or 22
    elif service == "REDIS":
        ssh_host = settings.redis_ssh_host
        ssh_user = settings.redis_ssh_user or "root"
        ssh_port = settings.redis_ssh_port or 22
    else:
        # Fallback to os.getenv() for other services
        ssh_host = os.getenv(f"{service}_SSH_HOST")
        if not ssh_host:
            return None
        ssh_user = os.getenv(f"{service}_SSH_USER", "root")
        try:
            ssh_port = int(os.getenv(f"{service}_SSH_PORT", "22"))
        except (ValueError, TypeError):
            ssh_port = 22
    
    if not ssh_host:
        return None
    
    return (ssh_host, ssh_user, ssh_port)


def ensure_redis_tunnel() -> Optional[subprocess.Popen]:
    """Ensure Redis is accessible, creating SSH tunnel if needed.
    
    This function:
    1. Checks if Redis is already accessible on localhost:6379
    2. If not, tries to create SSH tunnel using environment variables
    3. Returns the tunnel process if created
    
    Returns:
        Popen process object if tunnel was created, None otherwise
    """
    # Check if Redis is already accessible
    # First check port availability (fast check)
    if not check_port_available("127.0.0.1", 6379, timeout=0.5):
        logger.debug("Port 6379 is not accessible, will try to create tunnel")
    else:
        # Port is open, try to verify it's actually Redis
        logger.debug("Port 6379 is open, verifying Redis connection...")
        try:
            if check_redis_connection():
                logger.debug("Redis is already accessible, no tunnel needed")
                return None
            else:
                logger.debug("Port 6379 is open but Redis connection failed, will try tunnel")
        except Exception as e:
            logger.debug(f"Redis connection check error: {e}, will try tunnel")
    
    # Try to get SSH config from environment
    ssh_config = get_ssh_config_from_env("REDIS")
    if not ssh_config:
        logger.debug(
            "REDIS_SSH_HOST not set, skipping SSH tunnel creation. "
            "Set REDIS_SSH_HOST in .env to enable automatic tunnel creation."
        )
        return None
    
    ssh_host, ssh_user, ssh_port = ssh_config
    
    # Create tunnel
    return create_ssh_tunnel(
        ssh_host=ssh_host,
        ssh_user=ssh_user,
        ssh_port=ssh_port,
        local_port=6379,
        remote_port=6379,
        service_name="Redis",
    )


def ensure_database_tunnel() -> Optional[subprocess.Popen]:
    """Ensure PostgreSQL is accessible, creating SSH tunnel if needed.
    
    This function:
    1. Checks if PostgreSQL is already accessible on localhost (via existing tunnel)
    2. If not, tries to create SSH tunnel using environment variables
    3. Returns the tunnel process if created
    
    Returns:
        Popen process object if tunnel was created, None otherwise
    """
    # Parse database URL to get local port (port on localhost)
    local_port = 5432  # default PostgreSQL port
    try:
        # Try to extract port from DATABASE_URL
        db_url = settings.database_url
        if "@" in db_url and ":" in db_url:
            # Format: postgresql+asyncpg://user:pass@host:port/db
            parts = db_url.split("@")
            if len(parts) > 1:
                host_part = parts[1].split("/")[0]
                if ":" in host_part:
                    _, port_str = host_part.rsplit(":", 1)
                    try:
                        local_port = int(port_str)
                    except ValueError:
                        pass
    except Exception:
        pass
    
    # Get remote port (port on server) - use DATABASE_REMOTE_PORT if set, otherwise use local_port
    remote_port = settings.database_remote_port if settings.database_remote_port else local_port
    
    # First, check if SSH config is available
    ssh_config = get_ssh_config_from_env("DATABASE")
    if not ssh_config:
        logger.debug(
            "DATABASE_SSH_HOST not set, skipping SSH tunnel creation. "
            "Set DATABASE_SSH_HOST in .env to enable automatic tunnel creation."
        )
        return None
    
    ssh_host, ssh_user, ssh_port = ssh_config
    
    # Check if PostgreSQL is already accessible (via existing tunnel)
    # First check port availability (fast check)
    if not check_port_available("127.0.0.1", local_port, timeout=0.5):
        logger.debug(f"Port {local_port} is not accessible, will create SSH tunnel")
    else:
        # Port is open, check if it's local Windows PostgreSQL
        logger.debug(f"Port {local_port} is open, checking if it's local PostgreSQL...")
        try:
            # If SSH config is set, we want to connect to server, not local PostgreSQL
            # Check if this is local Windows PostgreSQL
            is_local_windows = check_if_local_postgresql("127.0.0.1", local_port)
            if is_local_windows:
                logger.warning(
                    f"Local Windows PostgreSQL detected on port {local_port}. "
                    "Will create SSH tunnel to server instead."
                )
                # Continue to create tunnel
            else:
                # Port is open and it's not local Windows PostgreSQL
                # Assume it's either tunnel to server or server PostgreSQL
                logger.debug(
                    f"PostgreSQL is already accessible on localhost:{local_port}, "
                    "assuming tunnel already exists or server PostgreSQL"
                )
                return None
        except Exception as e:
            logger.debug(f"PostgreSQL check error: {e}, will try tunnel")
    
    # Create tunnel to server
    logger.info(
        f"Creating SSH tunnel for PostgreSQL: {ssh_user}@{ssh_host}:{ssh_port} -> "
        f"localhost:{local_port} (remote: {remote_port})"
    )
    return create_ssh_tunnel(
        ssh_host=ssh_host,
        ssh_user=ssh_user,
        ssh_port=ssh_port,
        local_port=local_port,
        remote_port=remote_port,
        service_name="PostgreSQL",
    )
