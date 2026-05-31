from fastapi import APIRouter, HTTPException

from services.policy_service import get_policy_service

router = APIRouter(prefix="/members", tags=["members"])


@router.get("/{member_id}")
async def get_member(member_id: str):
    policy = get_policy_service()
    member = policy.get_member(member_id)
    if not member:
        raise HTTPException(404, f"Member '{member_id}' not found")
    return member


@router.get("/")
async def list_members():
    policy = get_policy_service()
    return {"members": policy.all_members()}