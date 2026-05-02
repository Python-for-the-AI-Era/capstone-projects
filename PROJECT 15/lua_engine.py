# TASK: Implement this Lua script to ensure atomicity
BID_LUA_SCRIPT = """
local auction_id = KEYS[1]
local new_bid = tonumber(ARGV[1])
local bidder_id = ARGV[2]

local current_price = redis.call('get', auction_id)

if not current_price or new_bid > tonumber(current_price) then
    redis.call('set', auction_id, new_bid)
    -- TASK: Publish the update to a Redis Pub/Sub channel here
    return "ACCEPTED"
else
    return "REJECTED"
end
"""