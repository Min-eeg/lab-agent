from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.schemas.user import UserResponse
from app.schemas.auth import LoginRequest, LoginResponse, RegisterRequest
from app.utils.password import verify_password,hash_password
from app.utils.jwt import create_access_token
from app.common.exceptions import BusinessException

def login(data: LoginRequest, db: Session):
    user=db.query(User).filter(User.username == data.username).first()
    if not user or not verify_password(data.password, user.password):
        raise BusinessException(message="用户名或密码错误")
        
        
    if user.status != 1:
        raise BusinessException(message="用户已被禁用")
            
    token = create_access_token(user.id)    
    return LoginResponse(token=token, user=UserResponse.model_validate(user))

def register(data: RegisterRequest, db: Session):
    user=db.query(User).filter(User.username == data.username).first()
    if user:
        raise BusinessException(message="用户已存在")
    user_model = User(
        username=data.username, 
        password=hash_password(data.password),
        name=data.name or data.username,
        role="student",
        status=1
    )
    db.add(user_model)
    db.commit()
    db.refresh(user_model)