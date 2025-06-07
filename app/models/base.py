# ===========================================================================
# File: app/models/base.py
# ===========================================================================
from bson import ObjectId as BsonObjectId
from pydantic import GetJsonSchemaHandler
from pydantic_core import core_schema
from typing import Any, Dict

class PyObjectId(BsonObjectId):
    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, handler: GetJsonSchemaHandler
    ) -> core_schema.CoreSchema:
        def validate_from_str(value: str) -> BsonObjectId:
            if not BsonObjectId.is_valid(value):
                raise ValueError(f"Invalid ObjectId string: {value}")
            return BsonObjectId(value)

        from_str_schema = core_schema.chain_schema(
            [
                core_schema.str_schema(),
                core_schema.no_info_plain_validator_function(validate_from_str),
            ]
        )
        # Memvalidasi jika input sudah merupakan instance BsonObjectId
        is_instance_schema = core_schema.is_instance_schema(BsonObjectId)
        
        # Menggabungkan skema: bisa string atau instance BsonObjectId
        combined_schema = core_schema.union_schema(
            [is_instance_schema, from_str_schema],
            serialization=core_schema.to_string_ser_schema(), # Selalu serialisasi ke string
        )
        return combined_schema

    @classmethod
    def __get_pydantic_json_schema__(
        cls, schema: core_schema.CoreSchema, handler: GetJsonSchemaHandler
    ) -> Dict[str, Any]:
        json_schema = handler(schema)
        json_schema.update(type="string", example="507f1f77bcf86cd799439011") # Contoh untuk OpenAPI
        return json_schema