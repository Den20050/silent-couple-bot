User A → /start → W1 → Choose "chat mode"  
User A → adds bot to common chat with User B  
User A → /link → W11 → Save common_chat_id  
Cron (07:30) → W3 → Send Mini App button to both users  
User A taps → Mini App opens → User A taps "Send to chat"  
Mini App Server → Telegram API → Send pic to common_chat_id  
User B sees pic in personal chat → Replies naturally