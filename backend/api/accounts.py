from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database import get_db
from models.account import PlatformAccount
from pydantic import BaseModel

router = APIRouter(prefix="/api/accounts", tags=["Accounts"])


class AccountCreate(BaseModel):
    platform: str = "bilibili"
    account_name: str
    cookies: str | None = None
    daily_limit: int = 20


@router.post("")
async def create_account(body: AccountCreate, db: AsyncSession = Depends(get_db)):
    acc = PlatformAccount(**body.model_dump())
    db.add(acc)
    await db.commit()
    await db.refresh(acc)
    return {"id": acc.id}


@router.get("")
async def list_accounts(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(PlatformAccount))
    accounts = result.scalars().all()
    return {
        "items": [
            {
                "id": a.id,
                "platform": a.platform,
                "account_name": a.account_name,
                "is_active": a.is_active,
                "daily_limit": a.daily_limit,
                "used_today": a.used_today,
            }
            for a in accounts
        ]
    }


@router.delete("/{account_id}")
async def delete_account(account_id: int, db: AsyncSession = Depends(get_db)):
    acc = await db.get(PlatformAccount, account_id)
    if not acc:
        return {"error": "Account not found"}
    await db.delete(acc)
    await db.commit()
    return {"ok": True}
