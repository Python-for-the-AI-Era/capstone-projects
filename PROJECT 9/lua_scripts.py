# TASK: Write a Lua script that:
# 1. Cleans up timestamps older than (current_time - window)
# 2. Counts the remaining elements
# 3. If count < limit, adds the current timestamp
# 4. Returns [is_allowed, remaining_count, reset_time]

SLIDING_WINDOW_LUA = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])

-- Your Lua logic goes here --
"""