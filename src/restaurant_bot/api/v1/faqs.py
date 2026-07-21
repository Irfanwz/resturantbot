import uuid
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from restaurant_bot.db.engine import get_db
from restaurant_bot.db.models.conversation import FAQ
from restaurant_bot.auth.permissions import CurrentUser, require_owner

router = APIRouter(prefix="/restaurants/{restaurant_id}/faqs", tags=["faqs"])


class FAQCreate(BaseModel):
    question: str = Field(..., min_length=1)
    answer: str = Field(..., min_length=1)
    keywords: str = ""  # comma-separated keywords for better matching
    sort_order: int = 0


class FAQUpdate(BaseModel):
    question: str | None = None
    answer: str | None = None
    keywords: str | None = None
    sort_order: int | None = None
    is_active: bool | None = None


class FAQResponse(BaseModel):
    id: uuid.UUID
    question: str
    answer: str
    sort_order: int
    is_active: bool

    model_config = {"from_attributes": True}


@router.get("", response_model=list[FAQResponse])
async def list_faqs(
    restaurant_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_owner),
):
    result = await db.execute(
        select(FAQ)
        .where(FAQ.restaurant_id == restaurant_id)
        .order_by(FAQ.sort_order)
    )
    return [FAQResponse.model_validate(f) for f in result.scalars().all()]


@router.post("", response_model=FAQResponse)
async def create_faq(
    restaurant_id: uuid.UUID,
    req: FAQCreate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_owner),
):
    faq = FAQ(
        restaurant_id=restaurant_id,
        question=req.question,
        answer=req.answer,
        sort_order=req.sort_order,
    )
    db.add(faq)
    await db.flush()
    return FAQResponse.model_validate(faq)


@router.patch("/{faq_id}", response_model=FAQResponse)
async def update_faq(
    restaurant_id: uuid.UUID,
    faq_id: uuid.UUID,
    req: FAQUpdate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_owner),
):
    result = await db.execute(
        select(FAQ).where(FAQ.id == faq_id, FAQ.restaurant_id == restaurant_id)
    )
    faq = result.scalar_one_or_none()
    if not faq:
        raise HTTPException(status_code=404, detail="FAQ not found")
    for key, value in req.model_dump(exclude_none=True).items():
        setattr(faq, key, value)
    await db.flush()
    return FAQResponse.model_validate(faq)


@router.delete("/{faq_id}")
async def delete_faq(
    restaurant_id: uuid.UUID,
    faq_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_owner),
):
    result = await db.execute(
        select(FAQ).where(FAQ.id == faq_id, FAQ.restaurant_id == restaurant_id)
    )
    faq = result.scalar_one_or_none()
    if not faq:
        raise HTTPException(status_code=404, detail="FAQ not found")
    await db.delete(faq)
    await db.flush()
    return {"message": "FAQ deleted"}
