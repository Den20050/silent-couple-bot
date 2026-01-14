"""Test script to manually verify Robokassa signature calculation."""

import hashlib
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.core.config import Settings


def calculate_signature(
    merchant_login: str,
    out_sum: str,
    inv_id: str,
    password: str,
    shp_params: dict | None = None,
) -> str:
    """Calculate Robokassa signature manually.
    
    Args:
        merchant_login: Merchant login
        out_sum: Payment amount as string (e.g., "299.00")
        inv_id: Invoice ID
        password: Password #1
        shp_params: Shp_ parameters dict (will be sorted alphabetically)
        
    Returns:
        MD5 signature in uppercase
    """
    # Base signature string: MerchantLogin:OutSum:InvId:Password#1
    signature_string = f"{merchant_login}:{out_sum}:{inv_id}:{password}"
    
    # Add Shp_ parameters if provided (sorted alphabetically)
    if shp_params:
        sorted_shp = sorted(shp_params.items())
        for key, value in sorted_shp:
            signature_string += f":{key}={value}"
    
    print(f"\n{'='*80}")
    print("SIGNATURE STRING (for MD5 hashing):")
    print(f"{'='*80}")
    print(signature_string)
    print(f"{'='*80}")
    print(f"Length: {len(signature_string)} characters")
    print(f"Password length: {len(password)} characters")
    
    # Calculate MD5 hash
    signature = hashlib.md5(signature_string.encode()).hexdigest().upper()
    
    print(f"\n{'='*80}")
    print("CALCULATED SIGNATURE (MD5, UPPERCASE):")
    print(f"{'='*80}")
    print(signature)
    print(f"{'='*80}\n")
    
    return signature


def main():
    """Main function to test signature calculation."""
    print("\n" + "="*80)
    print("ROBOKASSA SIGNATURE CALCULATION TEST")
    print("="*80 + "\n")
    
    # Load settings
    try:
        settings = Settings()
    except Exception as e:
        print(f"ERROR: Failed to load settings: {e}")
        print("\nMake sure .env file exists and contains:")
        print("  ROBOKASSA_MERCHANT_LOGIN=...")
        print("  ROBOKASSA_PASSWORD_1=...")
        return
    
    # Test parameters (from your logs)
    merchant_login = settings.robokassa_merchant_login
    out_sum = "299.00"
    inv_id = "8404486023"  # Example from logs
    password = settings.robokassa_password_1.strip()
    
    # Shp_ parameters (from your logs)
    shp_params = {
        "Shp_currency": "RUB",
        "Shp_is_lifetime": "false",
        "Shp_pair_id": "2",
        "Shp_period_days": "30",
    }
    
    print("TEST PARAMETERS:")
    print(f"  MerchantLogin: {merchant_login}")
    print(f"  OutSum: {out_sum}")
    print(f"  InvId: {inv_id}")
    print(f"  Password: {'*' * len(password)} (length: {len(password)})")
    print(f"  Shp_ parameters: {shp_params}")
    print(f"  IsTest: {not settings.robokassa_is_production}")
    
    # Calculate signature
    signature = calculate_signature(
        merchant_login=merchant_login,
        out_sum=out_sum,
        inv_id=inv_id,
        password=password,
        shp_params=shp_params,
    )
    
    # Expected signature from logs
    expected_signature = "45EAC56F6518A1BDF776E50839A5C08A"
    
    print("\n" + "="*80)
    print("VERIFICATION:")
    print("="*80)
    print(f"Calculated:  {signature}")
    print(f"Expected:    {expected_signature}")
    print(f"Match:       {'✅ YES' if signature == expected_signature else '❌ NO'}")
    print("="*80 + "\n")
    
    # Instructions
    print("INSTRUCTIONS:")
    print("1. Copy the signature string above")
    print("2. Calculate MD5 hash (use online tool or: echo -n 'STRING' | md5sum)")
    print("3. Convert to UPPERCASE")
    print("4. Compare with expected signature")
    print("\nIf signatures match but you still get 500 error:")
    print("- Check that Password #1 in .env matches TEST password in Robokassa dashboard")
    print("- Check that MD5 algorithm is selected in Robokassa dashboard")
    print("- Check that IsTest=1 is included in URL for test mode")
    print("- Verify all parameters in URL match exactly")


if __name__ == "__main__":
    main()
