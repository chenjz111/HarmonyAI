"""R1 native integration router factory. Deliberately NOT registered in main.

Default capability gate is closed. H5 remains unavailable pending verified
Origin/preauth-CSRF/cookie deployment; cookie/browser requests cannot select
native behavior. The caller must provide a reviewed blocklist-backed service.
"""
from datetime import datetime,timezone
from fastapi import APIRouter,Depends,Request
from fastapi.routing import APIRoute
from fastapi.exceptions import RequestValidationError
from pydantic import SecretStr,StrictBool,Field
from backend.app.schemas.v3.common import V3BaseModel
from backend.app.routers.v3.transport import V3APIError,v3_success
from backend.app.services.v3.account_session_service import AccountDenied,AccountUnavailable
from backend.app.services.v3.auth_service import _decode_verified_claims


class Credentials(V3BaseModel):
    username:str=Field(min_length=3,max_length=32)
    password:SecretStr
class RefreshRequest(V3BaseModel):
    refresh_token:SecretStr
class LogoutRequest(V3BaseModel):
    all_devices:StrictBool=False
class PasswordChange(V3BaseModel):
    current_password:SecretStr
    new_password:SecretStr


class AccountRoute(APIRoute):
    def get_route_handler(self):
        original=super().get_route_handler()
        async def safe_handler(request):
            try:return await original(request)
            except RequestValidationError:
                raise V3APIError(422,'ACCOUNT_INPUT_INVALID','请检查输入内容。') from None
        return safe_handler


def build_account_router(*,factory,service_provider,native_security_accepted=False):
    def gate(request:Request):
        if (native_security_accepted is not True or request.url.scheme!='https'
            or 'origin' in request.headers or 'cookie' in request.headers):
            raise V3APIError(503,'ACCOUNT_FEATURE_UNAVAILABLE','账号安全依赖尚未完成验收。')
    router=APIRouter(dependencies=[Depends(gate)],route_class=AccountRoute)
    def bearer(request):
        scheme,_,token=request.headers.get('authorization','').partition(' ')
        if scheme.lower()!='bearer' or not token.strip():raise V3APIError(401,'UNAUTHENTICATED','身份已失效。')
        return token.strip()
    def invoke(method,**kwargs):
        try:service=service_provider()
        except Exception:raise V3APIError(503,'ACCOUNT_UNAVAILABLE','账号安全依赖不可用。') from None
        try:return getattr(service,method)(factory,now=datetime.now(timezone.utc),**kwargs)
        except AccountDenied:raise V3APIError(401,'UNAUTHENTICATED','身份或凭据无效。') from None
        except ValueError:raise V3APIError(422,'ACCOUNT_INPUT_INVALID','请检查输入内容。') from None
        except AccountUnavailable:raise V3APIError(503,'ACCOUNT_UNAVAILABLE','账号操作未能确认，请重新认证。') from None
    def output(tokens):
        return v3_success(dict(public_user_id=_decode_verified_claims(tokens.access_token)['sub'],access_token=tokens.access_token,
            refresh_token=tokens.refresh_token,token_type='Bearer',expires_at=tokens.access_expires_at))
    @router.post('/auth/register-bind',status_code=201)
    def bind(body:Credentials,request:Request):
        return output(invoke('bind_access',access_token=bearer(request),username=body.username,password=body.password.get_secret_value(),platform='android'))
    @router.post('/auth/login')
    def login(body:Credentials,request:Request):
        if request.client is None:raise V3APIError(401,'UNAUTHENTICATED','身份或凭据无效。')
        return output(invoke('login',username=body.username,password=body.password.get_secret_value(),trusted_source=request.client.host,platform='android'))
    @router.post('/auth/refresh')
    def refresh(body:RefreshRequest):return output(invoke('refresh',refresh_token=body.refresh_token.get_secret_value(),platform='android'))
    @router.post('/auth/logout')
    def logout(body:LogoutRequest,request:Request):
        invoke('logout_access',access_token=bearer(request),all_devices=body.all_devices)
        return v3_success(dict(status='logged_out'))
    @router.post('/auth/password')
    def password(body:PasswordChange,request:Request):
        invoke('change_password_access',access_token=bearer(request),current_password=body.current_password.get_secret_value(),new_password=body.new_password.get_secret_value())
        return v3_success(dict(status='password_changed',reauthentication_required=True))
    return router
