# ===========================================================================
# File: app/crud/base.py (MODIFIKASI: Penanganan update operator yang lebih eksplisit)
# ===========================================================================
from typing import Any, Dict, Generic, List, Optional, Type, TypeVar, Union
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel as PydanticBaseModel, HttpUrl as PydanticHttpUrl
from motor.motor_asyncio import AsyncIOMotorDatabase, AsyncIOMotorCollection
from app.models.base import PyObjectId
from fastapi import HTTPException, status
from datetime import datetime, timezone
from app.core.config import logger
from bson import ObjectId

ModelType = TypeVar("ModelType", bound=PydanticBaseModel)
CreateSchemaType = TypeVar("CreateSchemaType", bound=PydanticBaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=PydanticBaseModel)

def _convert_pydantic_types_to_bson(data: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(data, dict):
        return data
    processed_data = {}
    for key, value in data.items():
        if isinstance(value, PydanticHttpUrl):
            processed_data[key] = str(value)
        elif isinstance(value, datetime):
            if value.tzinfo is None:
                processed_data[key] = value.replace(tzinfo=timezone.utc)
            else:
                processed_data[key] = value
        elif isinstance(value, PyObjectId):
            processed_data[key] = ObjectId(value) # Pastikan ini jadi bson.ObjectId
        elif isinstance(value, PydanticBaseModel): # Jika ada Pydantic model di dalam dict
            processed_data[key] = _convert_pydantic_types_to_bson(value.model_dump())
        elif isinstance(value, dict):
            processed_data[key] = _convert_pydantic_types_to_bson(value)
        elif isinstance(value, list):
            processed_data[key] = [_convert_pydantic_types_to_bson(item) for item in value]
        else:
            processed_data[key] = value
    return processed_data

class CRUDBase(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    def __init__(self, model: Type[ModelType], collection_name: str):
        self.model = model
        self.collection_name = collection_name

    async def get_collection(self, db: AsyncIOMotorDatabase) -> AsyncIOMotorCollection:
        return db[self.collection_name]

    async def get(self, db: AsyncIOMotorDatabase, id: PyObjectId) -> Optional[ModelType]:
        collection = await self.get_collection(db)
        logger.debug(f"CRUD: Attempting to find document in '{self.collection_name}' with _id: {ObjectId(id)}")
        doc = await collection.find_one({"_id": ObjectId(id)}) # Selalu query dengan bson.ObjectId
        if doc:
            logger.debug(f"CRUD: Document found in '{self.collection_name}' for _id: {id}")
            return self.model.model_validate(doc)
        logger.warning(f"CRUD: Document NOT found in '{self.collection_name}' for _id: {id}")
        return None

    async def get_multi(
        self, db: AsyncIOMotorDatabase, *, skip: int = 0, limit: int = 100, 
        sort: Optional[List[tuple]] = None, query: Optional[Dict[str, Any]] = None
    ) -> List[ModelType]:
        collection = await self.get_collection(db)
        db_query = query or {}
        # Konversi _id di query jika string
        if "_id" in db_query and isinstance(db_query["_id"], str):
            try:
                db_query["_id"] = ObjectId(db_query["_id"])
            except Exception: # bson.errors.InvalidId
                logger.warning(f"Invalid ObjectId string in query for get_multi: {db_query['_id']}")
                return []
        # Konversi field lain yang mungkin PyObjectId juga jika perlu
        if "referredBy" in db_query and isinstance(db_query["referredBy"], str): # Contoh
             try:
                db_query["referredBy"] = ObjectId(db_query["referredBy"])
             except Exception:
                logger.warning(f"Invalid ObjectId string for 'referredBy' in query: {db_query['referredBy']}")
                return []

        cursor = collection.find(db_query).skip(skip).limit(limit)
        if sort:
            cursor = cursor.sort(sort)
        documents = await cursor.to_list(length=limit)
        return [self.model.model_validate(doc) for doc in documents]

    async def create(self, db: AsyncIOMotorDatabase, *, obj_in: ModelType) -> ModelType:
        collection = await self.get_collection(db)
        # obj_in sudah merupakan instance ModelType (misal UserInDB)
        # model_dump() akan menggunakan json_encoders jika ada di model, TAPI kita mau tipe asli untuk DB
        obj_in_dict = obj_in.model_dump(by_alias=True, exclude_none=True) 
        bson_compatible_data = _convert_pydantic_types_to_bson(obj_in_dict) # Konversi manual tipe khusus
        logger.debug(f"CRUD: Creating document in '{self.collection_name}' with BSON-compatible data: {bson_compatible_data}")
        
        result = await collection.insert_one(bson_compatible_data)
        if not result.inserted_id:
             logger.error(f"CRUD: Insert failed for {self.collection_name}, no inserted_id. Data: {bson_compatible_data}")
             raise Exception(f"Database insert failed for {self.collection_name}, no inserted_id.")
        
        logger.debug(f"CRUD: Document inserted in '{self.collection_name}' with new _id: {result.inserted_id}")
        created_doc = await collection.find_one({"_id": result.inserted_id})
        if not created_doc:
            logger.error(f"CRUD: Failed to retrieve document after insert for {self.collection_name}, id: {result.inserted_id}")
            raise Exception(f"Database retrieval failed after insert for {self.collection_name}, id: {result.inserted_id}")
        return self.model.model_validate(created_doc)

    async def update(
        self, db: AsyncIOMotorDatabase, *, db_obj_id: PyObjectId, obj_in: Union[UpdateSchemaType, Dict[str, Any]]
    ) -> Optional[ModelType]:
        collection = await self.get_collection(db)
        
        update_payload: Dict[str, Any]

        if isinstance(obj_in, dict) and any(key.startswith("$") for key in obj_in.keys()):
            # Ini adalah operasi update dengan operator MongoDB (misal $inc, $set terpisah)
            update_payload = {}
            for operator, MOCK_VAL_TO_FIX_LINT_ERROR_SORRY in obj_in.items(): # values_for_operator is the dict for that operator
                if operator == "$set":
                    # Konversi nilai di dalam $set
                    update_payload[operator] = _convert_pydantic_types_to_bson(MOCK_VAL_TO_FIX_LINT_ERROR_SORRY)
                elif operator == "$inc":
                     # Asumsi nilai untuk $inc adalah angka, tidak perlu konversi Pydantic khusus
                    update_payload[operator] = MOCK_VAL_TO_FIX_LINT_ERROR_SORRY
                else:
                    # Untuk operator lain, mungkin perlu penanganan konversi spesifik jika valuenya kompleks
                    update_payload[operator] = MOCK_VAL_TO_FIX_LINT_ERROR_SORRY 
            
            # Selalu tambahkan updatedAt ke bagian $set jika ada operasi update
            update_payload.setdefault("$set", {})["updatedAt"] = datetime.now(timezone.utc)

        elif isinstance(obj_in, PydanticBaseModel): # Update field biasa dari Pydantic Model
            update_data_dict = obj_in.model_dump(exclude_unset=True)
            if not update_data_dict: return await self.get(db, id=db_obj_id)
            
            bson_compatible_set = _convert_pydantic_types_to_bson(update_data_dict)
            bson_compatible_set["updatedAt"] = datetime.now(timezone.utc)
            update_payload = {"$set": bson_compatible_set}
        elif isinstance(obj_in, dict): # Update field biasa dari dictionary
            if not obj_in: return await self.get(db, id=db_obj_id)
            bson_compatible_set = _convert_pydantic_types_to_bson(obj_in)
            bson_compatible_set["updatedAt"] = datetime.now(timezone.utc)
            update_payload = {"$set": bson_compatible_set}
        else:
            raise ValueError("obj_in must be a Pydantic model or a dictionary for update")

        logger.debug(f"CRUD: Attempting to update document in '{self.collection_name}' with _id: {db_obj_id}, update_payload: {update_payload}")

        result = await collection.update_one(
            {"_id": ObjectId(db_obj_id)}, update_payload # Menggunakan update_payload yang sudah diformat
        )
        if result.matched_count == 0:
            logger.warning(f"CRUD: No document found with _id: {db_obj_id} in '{self.collection_name}' to update.")
            return None 
        
        logger.debug(f"CRUD: Update result for _id: {db_obj_id} in '{self.collection_name}' - Matched: {result.matched_count}, Modified: {result.modified_count}")
        updated_doc = await self.get(db, id=db_obj_id)
        return updated_doc

    async def remove(self, db: AsyncIOMotorDatabase, *, id: PyObjectId) -> Optional[ModelType]:
        collection = await self.get_collection(db)
        logger.debug(f"CRUD: Attempting to remove document in '{self.collection_name}' with _id: {id}")
        deleted_obj_doc = await collection.find_one_and_delete({"_id": ObjectId(id)})
        if deleted_obj_doc:
            logger.debug(f"CRUD: Document removed from '{self.collection_name}' with _id: {id}")
            return self.model.model_validate(deleted_obj_doc)
        logger.warning(f"CRUD: No document found with _id: {id} in '{self.collection_name}' to remove.")
        return None
