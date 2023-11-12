from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.sql_db_service import ReferralLinkEntity


def get_reflink_by_id(session: Session,
                      link_id: int) -> ReferralLinkEntity:
    result = session.scalars(select(ReferralLinkEntity).where(ReferralLinkEntity.id == link_id))
    return result.first()
