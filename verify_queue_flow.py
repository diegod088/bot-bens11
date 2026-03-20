
import os
import sys
from database import init_database, add_pending_download, get_next_pending_download, update_download_status

def test_queue_flow():
    print("🧪 Testing Download Queue Flow...")
    
    # 1. Initialize
    init_database()
    
    # 2. Add item
    user_id = 123456789
    link = "https://t.me/test_channel/123"
    print(f"➕ Adding download link: {link} for user {user_id}")
    download_id = add_pending_download(user_id, link)
    print(f"✅ Added item with ID: {download_id}")
    
    # 3. Retrieve item
    print("🔍 Polling for next item...")
    item = get_next_pending_download()
    if item and item['id'] == download_id:
        print(f"✅ Successfully retrieved item: {item}")
    else:
        print(f"❌ Failed to retrieve item. Found: {item}")
        return False
        
    # 4. Update status to processing
    print("⏳ Updating status to 'processing'...")
    update_download_status(download_id, 'processing')
    
    # 5. Verify status changed (it shouldn't be 'pending' anymore)
    item_pending = get_next_pending_download()
    if not item_pending or item_pending['id'] != download_id:
        print("✅ Item is no longer in 'pending' status")
    else:
        print("❌ Item is still in 'pending' status!")
        return False
        
    # 6. Final status update
    print("🏁 Updating status to 'processed'...")
    update_download_status(download_id, 'processed')
    print("✅ Queue flow test PASSED")
    return True

if __name__ == "__main__":
    if test_queue_flow():
        sys.exit(0)
    else:
        sys.exit(1)
