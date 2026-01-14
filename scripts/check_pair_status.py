"""Check pair status in database."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from src.db.base import async_session_maker
from src.db.models import Pair, User, Subscription
from src.core.ssh_tunnel import ensure_database_tunnel
from src.core.logger import configure_logging, get_logger
import subprocess
from typing import Optional
from datetime import date, timedelta
from src.core.constants import TRIAL_PERIOD_DAYS

logger = get_logger(__name__)


async def check_pair_status() -> None:
    """Check pair status."""
    configure_logging("INFO")
    
    logger.info("=" * 60)
    logger.info("Checking Pair Status")
    logger.info("=" * 60)
    logger.info("")
    
    tunnel_process: Optional[subprocess.Popen] = None
    
    try:
        logger.info("Creating SSH tunnel...")
        tunnel_process = ensure_database_tunnel()
        if tunnel_process:
            logger.info("✅ SSH tunnel created")
            import time
            time.sleep(2)
        else:
            logger.info("ℹ️  SSH tunnel already exists or not needed")
        logger.info("")
        
        async with async_session_maker() as session:
            # Get all pairs
            result = await session.execute(select(Pair))
            pairs = result.scalars().all()
            
            logger.info(f"Found {len(pairs)} pair(s)")
            logger.info("")
            
            for pair in pairs:
                # Get users
                user_a_result = await session.execute(
                    select(User).where(User.id == pair.uid_a)
                )
                user_a = user_a_result.scalar_one()
                
                user_b_result = await session.execute(
                    select(User).where(User.id == pair.uid_b)
                )
                user_b = user_b_result.scalar_one()
                
                # Get subscription
                from src.db.repositories.subscriptions import SubscriptionsRepository
                subs_repo = SubscriptionsRepository(session)
                subscription = await subs_repo.get_by_pair_id(pair.id)
                
                logger.info(f"Pair ID: {pair.id}")
                logger.info(f"  User A: {user_a.tg_id} (@{user_a.username or 'N/A'})")
                logger.info(f"  User B: {user_b.tg_id} (@{user_b.username or 'N/A'})")
                logger.info(f"  Status: {pair.status}")
                logger.info(f"  Mode: {pair.mode}")
                logger.info("")
                
                if subscription:
                    logger.info(f"  Subscription:")
                    logger.info(f"    Status: {subscription.status}")
                    logger.info(f"    Created: {subscription.created_at.date()}")
                    logger.info(f"    Period End: {subscription.period_end}")
                    logger.info(f"    Is Lifetime: {subscription.is_lifetime}")
                    
                    if pair.status == "trial":
                        subscription_start = subscription.created_at.date()
                        trial_end_date = subscription_start + timedelta(days=TRIAL_PERIOD_DAYS)
                        days_left = (trial_end_date - date.today()).days
                        logger.info(f"    Trial End Date: {trial_end_date}")
                        logger.info(f"    Days Left: {days_left}")
                        if days_left <= 0:
                            logger.warning(f"    ⚠️  Trial expired!")
                    elif pair.status == "active":
                        days_left = (subscription.period_end - date.today()).days
                        logger.info(f"    Days Left: {days_left}")
                        if days_left <= 0:
                            logger.warning(f"    ⚠️  Subscription expired!")
                    elif pair.status == "past_due":
                        logger.warning(f"    ⚠️  Pair is PAST_DUE - cards will NOT be sent!")
                else:
                    logger.warning(f"  ⚠️  No subscription found!")
                
                logger.info("")
                logger.info("-" * 60)
                logger.info("")
                
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if tunnel_process:
            logger.info("Closing SSH tunnel...")
            try:
                tunnel_process.terminate()
                tunnel_process.wait(timeout=3)
                logger.info("✅ SSH tunnel closed")
            except subprocess.TimeoutExpired:
                tunnel_process.kill()
                tunnel_process.wait()
            except Exception:
                pass


if __name__ == "__main__":
    asyncio.run(check_pair_status())
