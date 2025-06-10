# ===========================================================================
# File: app/crud/crud_checkin.py (MODIFIKASI)
# ===========================================================================
from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import List
from datetime import datetime, timezone, timedelta # <-- Impor yang dibutuhkan

from app.crud.base import CRUDBase
from app.models.checkin import CheckinRecord
from app.models.base import PyObjectId
from pydantic import BaseModel as PydanticBaseModel # Placeholder

class CRUDCheckin(CRUDBase[CheckinRecord, PydanticBaseModel, PydanticBaseModel]):
    
    # --- FUNGSI BARU ---
    async def get_checkins_by_user_id_last_days(
        self, db: AsyncIOMotorDatabase, *, user_id: PyObjectId, days: int = 7
    ) -> List[CheckinRecord]:
        """
        Mengambil catatan check-in untuk user_id tertentu selama beberapa hari terakhir.
        """
        # Tentukan tanggal awal untuk query (hari ini - jumlah hari)
        start_date = datetime.now(timezone.utc) - timedelta(days=days)
        
        # Query ke database: cari record dengan userId yang cocok dan checkinAt lebih besar dari start_date
        cursor = self.get_collection(db).find({
            "userId": user_id,
            "checkinAt": {"$gte": start_date}
        }).sort("checkinAt", -1) # Urutkan dari yang terbaru
        
        records = await cursor.to_list(length=None)
        return [CheckinRecord.model_validate(record) for record in records]


crud_checkin = CRUDCheckin(CheckinRecord, "checkins")