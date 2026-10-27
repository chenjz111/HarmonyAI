"""Same-origin HTTPS H5 candidate; never mounted by the default application."""
from datetime import datetime,timezone
from typing import Literal
from fastapi import APIRouter,Depends,Request,Response
from starlette.middleware.cors import CORSMiddleware
from backend.app.schemas.v3.common import V3BaseModel
from backend.app.routers.v3.account_router import Credentials,LogoutRequest,PasswordChange,AccountRoute
from backend.app.routers.v3.transport import V3APIError,v3_api_error_handler,v3_success
from backend.app.services.v3.account_session_service import AccountDenied,AccountUnavailable
from backend.app.services.v3.account_browser_gate import BrowserContext,set_refresh_cookie
from backend.app.services.v3.auth_service import _resolve_principal,_decode_verified_claims

REFRESH='__Host-harmonyai-refresh'
CSRF='__Host-harmonyai-csrf'
PREAUTH='__Host-harmonyai-preauth'


class BootstrapRequest(V3BaseModel):
    action:Literal['login','bind']='login'


class EmptyRequest(V3BaseModel):pass


class BrowserAccountRoute(AccountRoute):
    def get_route_handler(self):
        original=super().get_route_handler()
        async def handler(request):
            try:response=await original(request)
            except V3APIError as error:response=await v3_api_error_handler(request,error)
            response.headers['Cache-Control']='no-store'
            response.headers['Pragma']='no-cache'
            response.headers['Vary']='Origin, Cookie, Authorization'
            return response
        return handler


def build_browser_account_router(*,factory,service_provider,browser_gate,browser_security_accepted=False):
    def context(request):
        return BrowserContext(origin=request.headers.get('origin',''),scheme=request.url.scheme,
            csrf_token=request.headers.get('x-csrf-token',''),preauth_cookie=request.cookies.get(PREAUTH,''))
    def gate(request:Request):
        origin=request.headers.get('origin','')
        if (browser_security_accepted is not True or not getattr(browser_gate,'preauth_ready',False) or request.url.scheme!='https'
            or origin not in browser_gate.origins or origin!=f'{request.url.scheme}://{request.url.netloc}'
            or request.headers.get('content-type','').split(';',1)[0].strip().lower()!='application/json'):
            raise V3APIError(503,'ACCOUNT_FEATURE_UNAVAILABLE','浏览器账号安全依赖尚未完成验收。')
        for middleware in request.app.user_middleware:
            if middleware.cls is CORSMiddleware:
                options=getattr(middleware,'kwargs',getattr(middleware,'options',{}))
                if ('*' in options.get('allow_origins',[]) or options.get('allow_origin_regex')
                    or options.get('allow_credentials') is not True
                    or set(options.get('allow_origins',[]))-browser_gate.origins):
                    raise V3APIError(503,'ACCOUNT_FEATURE_UNAVAILABLE','浏览器账号安全依赖尚未完成验收。')
        try:
            if service_provider().browser_gate is not browser_gate:raise AccountUnavailable()
        except Exception:raise V3APIError(503,'ACCOUNT_UNAVAILABLE','账号安全依赖不可用。') from None
    router=APIRouter(dependencies=[Depends(gate)],route_class=BrowserAccountRoute)
    def bearer(request):
        scheme,_,token=request.headers.get('authorization','').partition(' ')
        if scheme.lower()!='bearer' or not token.strip():raise V3APIError(401,'UNAUTHENTICATED','身份或凭据无效。')
        return token.strip()
    def invoke(method,**kwargs):
        try:
            service=service_provider()
            if service.browser_gate is not browser_gate:raise AccountUnavailable()
            return getattr(service,method)(factory,now=datetime.now(timezone.utc),**kwargs)
        except AccountDenied:raise V3APIError(401,'UNAUTHENTICATED','身份或凭据无效。') from None
        except ValueError:raise V3APIError(422,'ACCOUNT_INPUT_INVALID','请检查输入内容。') from None
        except Exception:raise V3APIError(503,'ACCOUNT_UNAVAILABLE','账号操作未能确认，请重新认证。') from None
    def output(tokens,response):
        now=datetime.now(timezone.utc)
        set_refresh_cookie(response,tokens.refresh_token,expires_at=tokens.refresh_expires_at,now=now)
        response.set_cookie(CSRF,tokens.csrf_token,max_age=int((tokens.refresh_expires_at-now).total_seconds()),
            expires=tokens.refresh_expires_at,path='/',secure=True,httponly=False,samesite='lax')
        response.delete_cookie(PREAUTH,path='/',secure=True,httponly=True,samesite='lax')
        return v3_success(dict(public_user_id=_decode_verified_claims(tokens.access_token)['sub'],
            access_token=tokens.access_token,token_type='Bearer',expires_at=tokens.access_expires_at))
    @router.post('/auth/browser/bootstrap')
    def bootstrap(body:BootstrapRequest,request:Request,response:Response):
        token=bearer(request) if body.action=='bind' else None
        try:
            if token:
                with factory() as db:
                    if _resolve_principal(token,db).auth_type!='guest':raise AccountDenied()
            challenge=browser_gate.preauth(action=body.action,binding_token=token,now=datetime.now(timezone.utc))
        except Exception:raise V3APIError(401,'UNAUTHENTICATED','身份或凭据无效。') from None
        response.set_cookie(PREAUTH,challenge,max_age=900,path='/',secure=True,httponly=True,samesite='lax')
        return v3_success(dict(csrf_token=challenge))
    @router.post('/auth/browser/register-bind',status_code=201)
    def bind(body:Credentials,request:Request,response:Response):
        return output(invoke('bind_access',access_token=bearer(request),username=body.username,password=body.password.get_secret_value(),
            platform='h5',browser_context=context(request)),response)
    @router.post('/auth/browser/login')
    def login(body:Credentials,request:Request,response:Response):
        if request.client is None:raise V3APIError(401,'UNAUTHENTICATED','身份或凭据无效。')
        return output(invoke('login',username=body.username,password=body.password.get_secret_value(),trusted_source=request.client.host,
            platform='h5',browser_context=context(request)),response)
    @router.post('/auth/browser/refresh')
    def refresh(body:EmptyRequest,request:Request,response:Response):
        return output(invoke('refresh',refresh_token=request.cookies.get(REFRESH),platform='h5',browser_context=context(request)),response)
    def clear_cookies(response):
        for name,http_only in ((REFRESH,True),(CSRF,False),(PREAUTH,True)):
            response.delete_cookie(name,path='/',secure=True,httponly=http_only,samesite='lax')
    @router.post('/auth/browser/signed-out')
    def signed_out(body:EmptyRequest,request:Request,response:Response):
        # A local UI marker is insufficient: any usable HttpOnly proof still
        # present must prevent Guest-return permission. This performs no revoke.
        invoke('confirm_browser_signed_out',refresh_token=request.cookies.get(REFRESH),browser_context=context(request))
        clear_cookies(response)
        return v3_success(dict(status='signed_out'))
    @router.post('/auth/browser/logout')
    def logout(body:LogoutRequest,request:Request,response:Response):
        invoke('logout_access',access_token=bearer(request),all_devices=body.all_devices,browser_context=context(request))
        clear_cookies(response)
        return v3_success(dict(status='logged_out'))
    @router.post('/auth/browser/password')
    def password(body:PasswordChange,request:Request,response:Response):
        invoke('change_password_access',access_token=bearer(request),current_password=body.current_password.get_secret_value(),
            new_password=body.new_password.get_secret_value(),browser_context=context(request))
        clear_cookies(response)
        return v3_success(dict(status='password_changed',reauthentication_required=True))
    return router


def build_reviewed_browser_account_router(*,factory,manifest_path,approved_manifest_sha256,browser_gate,browser_security_accepted=False):
    """Compose the existing service with the SAME independently pinned source.

    Never mounted by main; accepting an Origin alone is not platform approval.
    """
    service=None
    if browser_security_accepted is True:
        from backend.app.services.v3.account_password_source import load_reviewed_password_policy
        from backend.app.services.v3.account_session_service import AccountService
        try:
            policy=load_reviewed_password_policy(manifest_path,approved_manifest_sha256=approved_manifest_sha256)
            service=AccountService(password_policy=policy,browser_gate=browser_gate)
        except (ValueError,AccountUnavailable):pass
    return build_browser_account_router(factory=factory,service_provider=lambda:service,
        browser_gate=browser_gate,browser_security_accepted=browser_security_accepted)
