from langchain_community.chat_message_histories import RedisChatMessageHistory

def get_chat_history(session_id: str):
    return RedisChatMessageHistory(
        session_id=session_id,
        url="redis://localhost:6379/0",
        ttl=86400  # 24 hours in seconds
    )