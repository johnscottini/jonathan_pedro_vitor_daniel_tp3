from pydantic import BaseModel, Field


class Token(BaseModel):
    access_token: str = Field(..., description="JWT a enviar como `Authorization: Bearer <token>`")
    token_type: str = Field(default="bearer", description="Sempre `bearer`", examples=["bearer"])
