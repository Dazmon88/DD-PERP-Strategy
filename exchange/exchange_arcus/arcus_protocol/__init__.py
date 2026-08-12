# Arcus protocol exports（对齐 popdex_protocol / ondoperp_protocol 结构）
from .perps_auth import (
    CREATE_API_KEY_TYPES,
    EIP712_CREATE_API_KEY_DOMAINS,
    ArcusAuth,
    canonical_json,
    timestamp_ns,
)
from .perp_http import ArcusPerpHTTP, REST_URLS
from .perps_wss import (
    PRIVATE_CHANNELS,
    PUBLIC_CHANNELS,
    ArcusAccountStream,
    ArcusMarketStream,
    ArcusPerpStream,
    WS_URLS,
)
from .orders import (
    OP_CANCEL,
    OP_MODIFY,
    OP_PLACE,
    OP_PLACE_UNTRIGGERED,
    SIDE,
    TIF,
    build_cancel_order_body,
    build_cancel_typed_payload,
    build_modify_typed_payload,
    build_place_order_body,
    build_place_typed_payload,
    default_good_til_time_us,
    make_client_id,
    normalize_side,
    normalize_tif,
    snap_price,
    snap_qty,
    to_engine_int,
)
from .account import (
    build_create_api_key_typed_data,
    create_api_key,
    generate_api_key_pair,
    sign_create_api_key,
)

__all__ = [
    # auth
    "ArcusAuth",
    "EIP712_CREATE_API_KEY_DOMAINS",
    "CREATE_API_KEY_TYPES",
    "canonical_json",
    "timestamp_ns",
    # http / ws
    "ArcusPerpHTTP",
    "REST_URLS",
    "ArcusPerpStream",
    "ArcusMarketStream",
    "ArcusAccountStream",
    "WS_URLS",
    "PUBLIC_CHANNELS",
    "PRIVATE_CHANNELS",
    # orders
    "OP_PLACE",
    "OP_CANCEL",
    "OP_MODIFY",
    "OP_PLACE_UNTRIGGERED",
    "SIDE",
    "TIF",
    "make_client_id",
    "normalize_side",
    "normalize_tif",
    "to_engine_int",
    "default_good_til_time_us",
    "build_place_typed_payload",
    "build_cancel_typed_payload",
    "build_modify_typed_payload",
    "build_place_order_body",
    "build_cancel_order_body",
    "snap_price",
    "snap_qty",
    # account
    "generate_api_key_pair",
    "build_create_api_key_typed_data",
    "sign_create_api_key",
    "create_api_key",
]
