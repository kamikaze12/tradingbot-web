"""
MARKET ASSETS UPDATER
Script untuk manual update market lists
Bisa dijalankan via cron job atau manual
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from market_assets_manager import MarketAssetsManager
import argparse
import schedule
import time

def manual_update():
    """Manual update semua market data"""
    print("🔄 Starting manual update of all market data...")
    
    manager = MarketAssetsManager(auto_update=False)
    results = manager.update_all_markets()
    
    print(f"\n✅ Update completed!")
    print(f"   Indonesian stocks: {len(results['indonesian_stocks']['symbols'])} symbols")
    print(f"   US stocks: {len(results['us_stocks']['symbols'])} symbols")
    print(f"   Forex pairs: {len(results['forex_pairs']['symbols'])} symbols")
    print(f"   Crypto symbols: {len(results['crypto_symbols']['symbols'])} symbols")
    print(f"   Last updated: {results['last_updated']}")
    
    return results

def scheduled_update():
    """Scheduled update (untuk cron job)"""
    print(f"⏰ Scheduled update at {time.strftime('%Y-%m-%d %H:%M:%S')}")
    manager = MarketAssetsManager(auto_update=False)
    manager.update_all_markets()

def update_specific_market(market_type: str):
    """Update specific market type"""
    print(f"🔄 Updating {market_type}...")
    
    manager = MarketAssetsManager(auto_update=False)
    
    if market_type == 'id':
        result = manager.update_id_stocks()
        manager.save_to_file(result, manager.id_stocks_file)
    elif market_type == 'us':
        result = manager.update_us_stocks()
        manager.save_to_file(result, manager.us_stocks_file)
    elif market_type == 'forex':
        result = manager.update_forex_pairs()
        manager.save_to_file(result, manager.forex_pairs_file)
    elif market_type == 'crypto':
        result = manager.update_crypto_symbols()
        manager.save_to_file(result, manager.crypto_symbols_file)
    else:
        print(f"❌ Unknown market type: {market_type}")
        return
    
    print(f"✅ {market_type} updated: {len(result.get('symbols', []))} symbols")

def show_stats():
    """Show current statistics"""
    manager = MarketAssetsManager(auto_update=False)
    stats = manager.get_statistics()
    
    print("\n📊 MARKET DATA STATISTICS")
    print("=" * 50)
    
    for market_type, data in stats.items():
        print(f"\n{market_type.replace('_', ' ').title()}:")
        print(f"  Count: {data['count']}")
        print(f"  Last updated: {data['last_updated']}")
        print(f"  Source: {data['source']}")
    
    print("\n" + "=" * 50)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Market Assets Updater")
    parser.add_argument('--update-all', action='store_true', help='Update all market data')
    parser.add_argument('--update', choices=['id', 'us', 'forex', 'crypto'], help='Update specific market')
    parser.add_argument('--stats', action='store_true', help='Show current statistics')
    parser.add_argument('--schedule', action='store_true', help='Run scheduled updates (weekly)')
    
    args = parser.parse_args()
    
    if args.update_all:
        manual_update()
    elif args.update:
        update_specific_market(args.update)
    elif args.stats:
        show_stats()
    elif args.schedule:
        # Schedule weekly update (Senin jam 8 pagi)
        schedule.every().monday.at("08:00").do(scheduled_update)
        
        print("📅 Scheduled updater started (weekly on Monday 08:00)")
        print("Press Ctrl+C to stop")
        
        while True:
            schedule.run_pending()
            time.sleep(60)
    else:
        # Default: update all jika data stale
        manager = MarketAssetsManager(auto_update=True)
        show_stats()
