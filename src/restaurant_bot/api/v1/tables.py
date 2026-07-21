import uuid
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from restaurant_bot.db.engine import get_db
from restaurant_bot.db.models.reservation import Table
from restaurant_bot.auth.permissions import CurrentUser, require_owner, require_staff
from restaurant_bot.schemas.reservation import TableResponse

router = APIRouter(prefix="/restaurants/{restaurant_id}/tables", tags=["tables"])


class TableCreate(BaseModel):
    table_number: str = Field(..., min_length=1, max_length=20)
    capacity: int = Field(..., ge=1, le=100)


class TableUpdate(BaseModel):
    table_number: str | None = None
    capacity: int | None = None
    is_active: bool | None = None


@router.get("", response_model=list[TableResponse])
async def list_tables(
    restaurant_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_staff),
):
    result = await db.execute(
        select(Table)
        .where(Table.restaurant_id == restaurant_id)
        .order_by(Table.table_number)
    )
    tables = result.scalars().all()
    return [TableResponse.model_validate(t) for t in tables]


@router.post("", response_model=TableResponse)
async def create_table(
    restaurant_id: uuid.UUID,
    req: TableCreate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_owner),
):
    table = Table(
        restaurant_id=restaurant_id,
        table_number=req.table_number,
        capacity=req.capacity,
    )
    db.add(table)
    await db.flush()
    return TableResponse.model_validate(table)


@router.patch("/{table_id}", response_model=TableResponse)
async def update_table(
    restaurant_id: uuid.UUID,
    table_id: uuid.UUID,
    req: TableUpdate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_owner),
):
    result = await db.execute(
        select(Table).where(Table.id == table_id, Table.restaurant_id == restaurant_id)
    )
    table = result.scalar_one_or_none()
    if not table:
        raise HTTPException(status_code=404, detail="Table not found")

    if req.table_number is not None:
        table.table_number = req.table_number
    if req.capacity is not None:
        table.capacity = req.capacity
    if req.is_active is not None:
        table.is_active = req.is_active
    await db.flush()
    return TableResponse.model_validate(table)


@router.delete("/{table_id}")
async def delete_table(
    restaurant_id: uuid.UUID,
    table_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_owner),
):
    result = await db.execute(
        select(Table).where(Table.id == table_id, Table.restaurant_id == restaurant_id)
    )
    table = result.scalar_one_or_none()
    if not table:
        raise HTTPException(status_code=404, detail="Table not found")
    await db.delete(table)
    await db.flush()
    return {"message": f"Table {table.table_number} deleted"}
