-- Check daily state for pairs 6 and 9
SELECT pair_id, day, morning_initiator, morning_sent_at, morning_responded_at 
FROM daily_state 
WHERE pair_id IN (6, 9) AND day >= '2026-03-24' 
ORDER BY day DESC, pair_id;

-- Check if there are any logs for user activities
SELECT pair_id, day, morning_initiator, evening_initiator 
FROM daily_state 
WHERE pair_id IN (6, 9) 
ORDER BY day DESC 
LIMIT 10;
