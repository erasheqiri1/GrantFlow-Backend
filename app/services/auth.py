import jwt
import bcrypt
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.core.config import settings
from app.models.public.models import (
    User, Tenant, Role, UserRole, PasswordResetToken,
    EmailVerificationToken, TenantStatus, UserProfile, ApplicantProfile, RefreshToken
)
from app.schemas.auth import (
    RegisterRequest, RegisterOrgRequest, LoginRequest,
    ForgotPasswordRequest, ResetPasswordRequest,
    InviteAcceptRequest, TokenResponse,
)


class AuthService:
    """Shërbimi për autentikim dhe autorizim."""

    def __init__(self, db: Session):
        self.db = db

    # ── Helpers statike ───────────────────────

    @staticmethod
    def hash_password(password: str) -> str:
        return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    @staticmethod
    def verify_password(password: str, hashed: str) -> bool:
        return bcrypt.checkpw(password.encode(), hashed.encode())

    @staticmethod
    def create_token(user_id: str, role: str, tenant_slug: str | None) -> str:
        payload = {
            "user_id":     str(user_id),
            "role":        role,
            "tenant_slug": tenant_slug,
            "exp":         datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        }
        return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")

    @staticmethod
    def _hash_token(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()

    def create_refresh_token(self, user_id: str, role: str, tenant_slug: str | None) -> str:
        token_value = secrets.token_urlsafe(64)
        self.db.add(RefreshToken(
            token_hash=self._hash_token(token_value),
            user_id=user_id,
            tenant_slug=tenant_slug,
            role=role,
            expires_at=datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        ))
        return token_value

    def revoke_refresh_token(self, token_value: str) -> None:
        token_hash = self._hash_token(token_value)
        db_token = self.db.query(RefreshToken).filter(RefreshToken.token_hash == token_hash).first()
        if db_token:
            db_token.is_revoked = True
            self.db.commit()

    def refresh_access_token(self, refresh_token_value: str) -> TokenResponse:
        token_hash = self._hash_token(refresh_token_value)
        db_token = self.db.query(RefreshToken).filter(
            RefreshToken.token_hash == token_hash,
            RefreshToken.is_revoked == False,
        ).first()

        if not db_token:
            raise HTTPException(status_code=401, detail="Refresh token i pavlefshëm")

        if db_token.expires_at < datetime.now(timezone.utc):
            db_token.is_revoked = True
            self.db.commit()
            raise HTTPException(status_code=401, detail="Refresh token ka skaduar. Kyçu përsëri.")

        user = self.db.query(User).filter(User.id == db_token.user_id).first()
        if not user or not user.is_active:
            raise HTTPException(status_code=401, detail="Llogaria është joaktive")

        db_token.is_revoked    = True
        new_access_token  = self.create_token(db_token.user_id, db_token.role, db_token.tenant_slug)
        new_refresh_token = self.create_refresh_token(str(db_token.user_id), db_token.role, db_token.tenant_slug)
        self.db.commit()
        return TokenResponse(
            access_token=new_access_token,
            refresh_token=new_refresh_token,
            role=db_token.role,
            user_id=str(db_token.user_id),
            tenant_slug=db_token.tenant_slug,
        )

    # ── Register ──────────────────────────────

    def register_user(self, data: RegisterRequest) -> dict:
        existing = self.db.query(User).filter(User.email == data.email).first()
        if existing:
            raise HTTPException(status_code=409, detail="Email ekziston tashmë")

        try:
            user = User(
                email=data.email,
                password_hash=self.hash_password(data.password),
                first_name=data.first_name,
                last_name=data.last_name,
                is_active=False,
                email_verified=False,
            )
            self.db.add(user)
            self.db.flush()

            role = self.db.query(Role).filter(Role.name == "APPLICANT").first()
            self.db.add(UserRole(user_id=user.id, role_id=role.id, tenant_id=None))
            self.db.add(UserProfile(user_id=user.id))
            self.db.add(ApplicantProfile(user_id=user.id))

            token_value = secrets.token_urlsafe(32)
            self.db.add(EmailVerificationToken(
                user_id=user.id,
                token=token_value,
                expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
            ))
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise HTTPException(status_code=500, detail="Gabim gjatë regjistrimit")

        verify_link = f"{settings.FRONTEND_URL}/verify-email?token={token_value}"
        try:
            from app.tasks.email import send_verification_email
            send_verification_email.delay(data.email, verify_link, f"{data.first_name} {data.last_name}")
        except Exception:
            pass

        return {"message": "Llogaria u krijua. Kontrollo emailin tënd dhe kliko linkun për të aktivizuar llogarinë."}

    def register_org(self, data: RegisterOrgRequest) -> dict:
        if self.db.query(Tenant).filter(Tenant.slug == data.org_slug).first():
            raise HTTPException(status_code=409, detail="Ky slug ekziston tashmë")
        if self.db.query(User).filter(User.email == data.email).first():
            raise HTTPException(status_code=409, detail="Email ekziston tashmë")

        try:
            tenant = Tenant(
                slug=data.org_slug, name=data.org_name, email=data.email,
                nipt=data.nipt, is_active=False, status=TenantStatus.PENDING,
            )
            self.db.add(tenant)
            self.db.flush()

            user = User(
                email=data.email,
                password_hash=self.hash_password(data.password),
                first_name=data.first_name,
                last_name=data.last_name,
                is_active=False,
                email_verified=False,
            )
            self.db.add(user)
            self.db.flush()

            role = self.db.query(Role).filter(Role.name == "ORG_ADMIN").first()
            self.db.add(UserRole(user_id=user.id, role_id=role.id, tenant_id=tenant.id))

            token_value = secrets.token_urlsafe(32)
            self.db.add(EmailVerificationToken(
                user_id=user.id,
                token=token_value,
                expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
            ))
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise HTTPException(status_code=500, detail="Gabim gjatë regjistrimit të organizatës")

        verify_link = f"{settings.FRONTEND_URL}/verify-email?token={token_value}"
        full_name   = f"{data.first_name} {data.last_name}"
        print(f"[ORG REGISTER] dergon email te: {data.email}")
        try:
            from app.tasks.email import send_verification_email
            result = send_verification_email.delay(data.email, verify_link, full_name)
            print(f"[ORG REGISTER] task u enqueue-ua: {result.id}")
        except Exception as e:
            print(f"[ORG REGISTER] GABIM me email: {e}")

        return {"message": "Organizata u regjistrua. Kontrollo emailin tënd për të konfirmuar adresën."}

    def verify_email(self, token: str) -> dict:
        verification = self.db.query(EmailVerificationToken).filter(
            EmailVerificationToken.token == token
        ).first()

        if not verification:
            raise HTTPException(status_code=400, detail="Token i pavlefshëm")

        if verification.expires_at < datetime.now(timezone.utc):
            self.db.delete(verification)
            self.db.commit()
            raise HTTPException(status_code=400, detail="Token ka skaduar. Regjistrohu përsëri.")

        user = self.db.query(User).filter(User.id == verification.user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="Përdoruesi nuk u gjet")

        user.email_verified = True
        user.is_active = True
        self.db.delete(verification)
        self.db.commit()

        user_role = self.db.query(UserRole).filter(UserRole.user_id == user.id).first()
        role_obj  = self.db.query(Role).filter(Role.id == user_role.role_id).first() if user_role else None
        if role_obj and role_obj.name == "ORG_ADMIN":
            return {"message": "Email u konfirmua! Prisni aprovimin nga administratori para se të kyçeni."}
        return {"message": "Email u konfirmua me sukses. Tani mund të kyçeni."}

    # ── Login ─────────────────────────────────

    def login_user(self, data: LoginRequest) -> TokenResponse:
        user = self.db.query(User).filter(User.email == data.email).first()
        if not user or not self.verify_password(data.password, user.password_hash):
            raise HTTPException(status_code=401, detail="Email ose fjalëkalim i gabuar")

        if not user.is_active:
            if not user.email_verified:
                raise HTTPException(status_code=403, detail="Konfirmo emailin tënd para se të kyçesh")
            raise HTTPException(status_code=403, detail="Llogaria është joaktive")

        tenant_slug_for_token = data.tenant_slug

        if data.tenant_slug:
            tenant = self.db.query(Tenant).filter(Tenant.slug == data.tenant_slug).first()
            if not tenant:
                raise HTTPException(status_code=404, detail="Organizata nuk u gjet")
            if tenant.status != TenantStatus.ACTIVE:
                raise HTTPException(status_code=403, detail="Organizata nuk është aprovuar ende")

            user_role = self.db.query(UserRole).filter(
                UserRole.user_id == user.id, UserRole.tenant_id == tenant.id
            ).first()
            if not user_role:
                user_role = self.db.query(UserRole).filter(
                    UserRole.user_id == user.id, UserRole.tenant_id == None
                ).first()
        else:
            user_role = self.db.query(UserRole).filter(
                UserRole.user_id == user.id, UserRole.tenant_id == None
            ).first()

            if not user_role:
                tenant_roles = (
                    self.db.query(UserRole)
                    .filter(UserRole.user_id == user.id, UserRole.tenant_id != None)
                    .all()
                )
                if len(tenant_roles) == 1:
                    user_role = tenant_roles[0]
                    tenant = self.db.query(Tenant).filter(Tenant.id == user_role.tenant_id).first()
                    if tenant:
                        if tenant.status != TenantStatus.ACTIVE:
                            raise HTTPException(status_code=403, detail="Organizata nuk është aprovuar ende")
                        tenant_slug_for_token = tenant.slug
                elif len(tenant_roles) > 1:
                    slugs = []
                    for tr in tenant_roles:
                        t = self.db.query(Tenant).filter(Tenant.id == tr.tenant_id).first()
                        if t:
                            slugs.append(t.slug)
                    raise HTTPException(
                        status_code=400,
                        detail=f"Keni akses në shumë organizata. Specifikoni slug-un: {', '.join(slugs)}"
                    )

        if not user_role:
            raise HTTPException(status_code=403, detail="Nuk ke akses")

        role_name     = self.db.query(Role).filter(Role.id == user_role.role_id).first().name
        access_token  = self.create_token(user.id, role_name, tenant_slug_for_token)
        refresh_token = self.create_refresh_token(str(user.id), role_name, tenant_slug_for_token)
        self.db.commit()
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            role=role_name,
            user_id=str(user.id),
            tenant_slug=tenant_slug_for_token,
        )

    # ── Forgot / Reset Password ───────────────

    def forgot_password(self, data: ForgotPasswordRequest) -> dict:
        user = self.db.query(User).filter(User.email == data.email).first()
        if not user:
            return {"message": "Nëse email ekziston, do të marrësh udhëzime."}

        self.db.query(PasswordResetToken).filter(PasswordResetToken.user_id == user.id).delete()
        token = secrets.token_urlsafe(32)
        self.db.add(PasswordResetToken(
            user_id=user.id,
            token=token,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        ))
        self.db.commit()

        reset_link = f"{settings.FRONTEND_URL}/reset-password?token={token}"
        try:
            from app.tasks.email import send_reset_password_email
            send_reset_password_email.delay(user.email, reset_link)
        except Exception:
            pass

        return {"message": "Nëse email ekziston, do të marrësh udhëzime."}

    def reset_password(self, data: ResetPasswordRequest) -> dict:
        reset_token = self.db.query(PasswordResetToken).filter(
            PasswordResetToken.token == data.token
        ).first()

        if not reset_token:
            raise HTTPException(status_code=400, detail="Token i pavlefshëm")

        if reset_token.expires_at < datetime.now(timezone.utc):
            self.db.delete(reset_token)
            self.db.commit()
            raise HTTPException(status_code=400, detail="Token ka skaduar")

        user = self.db.query(User).filter(User.id == reset_token.user_id).first()
        user.password_hash = self.hash_password(data.new_password)
        self.db.delete(reset_token)
        self.db.commit()
        return {"message": "Fjalëkalimi u ndryshua me sukses"}

    # ── Accept Invite ─────────────────────────

    def accept_invite(self, data: InviteAcceptRequest) -> TokenResponse:
        try:
            payload      = jwt.decode(data.token, settings.SECRET_KEY, algorithms=["HS256"])
            tenant_slug  = payload.get("tenant_slug")
            invite_email = payload.get("email")
            invite_role  = payload.get("role")
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=400, detail="Ftesa ka skaduar")
        except jwt.InvalidTokenError:
            raise HTTPException(status_code=400, detail="Token i pavlefshëm")

        tenant = None
        if tenant_slug:
            tenant = self.db.query(Tenant).filter(Tenant.slug == tenant_slug).first()
            if not tenant:
                raise HTTPException(status_code=404, detail="Organizata nuk u gjet")

        if self.db.query(User).filter(User.email == invite_email).first():
            raise HTTPException(status_code=400, detail="Email ekziston tashmë")

        try:
            user = User(
                email=invite_email,
                password_hash=self.hash_password(data.password),
                first_name=data.first_name,
                last_name=data.last_name,
                is_active=True,
            )
            self.db.add(user)
            self.db.flush()

            role = self.db.query(Role).filter(Role.name == invite_role).first()
            self.db.add(UserRole(
                user_id=user.id,
                role_id=role.id,
                tenant_id=tenant.id if tenant else None,
            ))
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise HTTPException(status_code=500, detail="Gabim gjatë aktivizimit të ftesës")

        access_token  = self.create_token(user.id, invite_role, tenant_slug)
        refresh_token = self.create_refresh_token(str(user.id), invite_role, tenant_slug)
        self.db.commit()
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            role=invite_role,
            user_id=str(user.id),
            tenant_slug=tenant_slug,
        )


# Alias-et për testet — eksportojnë static methods si funksione të lira
hash_password   = AuthService.hash_password
verify_password = AuthService.verify_password
create_token    = AuthService.create_token
