import jwt
from fastapi import HTTPException, Security
from fastapi.security import HTTPBearer

SECRET = "formify_secret"
security = HTTPBearer()

async def get_current_user(credentials = Security(security)):
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET, algorithms=["HS256"])
        # Student must ensure the JWT includes 'org_id' 
        # and create a dependency that scopes all SQL queries.
        return payload 
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid Session")