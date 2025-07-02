from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from bson import ObjectId

class ObjectIdEncoderMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        if response.media_type == "application/json" and hasattr(response, "body"):
            # Ambil hasil JSON asli
            body = b"".join([chunk async for chunk in response.body_iterator])
            from json import loads, dumps
            data = loads(body)

            # Konversi ObjectId ke str
            encoded = jsonable_encoder(data, custom_encoder={ObjectId: str})
            return JSONResponse(content=encoded, status_code=response.status_code)
        return response
