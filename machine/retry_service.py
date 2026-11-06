import os
from datetime import datetime, timedelta
import logging
from pymongo import MongoClient, ReturnDocument

logger = logging.getLogger("hmsmi")

_client = None

def get_mongo_db():
    """Returns a shared MongoDB database instance to avoid connection leaks."""
    global _client
    if _client is None:
        mongo_url = os.getenv("GLOBAL_DB_HOST")
        _client = MongoClient(mongo_url, maxPoolSize=50, socketTimeoutMS=30000)
    return _client.Diagnostics


def get_retry_queue_collection():
    db = get_mongo_db()
    col = db.machine_retry_queue
    # Create indexes for fast lookup if not present
    try:
        col.create_index([("status", 1), ("next_retry_time", 1)])
        col.create_index([("barcode", 1)], unique=False)
        col.create_index([("bill_number", 1)], unique=False)
    except Exception as e:
        logger.warning(f"Could not ensure index on machine_retry_queue: {e}")
    return col


def calculate_next_retry(retry_count):
    """
    Exponential backoff delays (in minutes):
    Attempt 1: 1 min (race condition / sync)
    Attempt 2: 5 min (waiting for technician)
    Attempt 3: 15 min
    Attempt 4: 30 min
    Attempt 5: 60 min
    """
    delays = [1, 5, 15, 30, 60]
    idx = min(max(0, retry_count - 1), len(delays) - 1)
    return datetime.now() + timedelta(minutes=delays[idx])


def enqueue_for_approval(barcode, bill_number=None, patient_name=None, bill_type=None, details=None):
    """
    Queues a record whose test results exist on the machine but approve_time is not yet recorded.
    Checks back periodically until approved (up to 24 hours).
    """
    if not barcode:
        return None

    col = get_retry_queue_collection()
    now = datetime.now()
    next_check = now + timedelta(minutes=3)  # check again in 3 minutes

    existing = col.find_one({"barcode": str(barcode), "status": {"$in": ["WAITING_APPROVAL", "PENDING_RETRY"]}})
    if existing:
        # Don't update if it was checked very recently
        col.update_one(
            {"_id": existing["_id"]},
            {"$set": {
                "updated_at": now,
                "bill_number": bill_number or existing.get("bill_number"),
                "patient_name": patient_name or existing.get("patient_name"),
                "details": details or existing.get("details"),
            }}
        )
        return existing["_id"]

    doc = {
        "barcode": str(barcode),
        "bill_number": str(bill_number) if bill_number else None,
        "bill_type": str(bill_type) if bill_type else None,
        "patient_name": str(patient_name) if patient_name else None,
        "status": "WAITING_APPROVAL",
        "reason": "RESULT_NOT_APPROVED",
        "retry_count": 0,
        "max_retries": 50,  # Allow periodic checking for up to ~12-24 hours
        "next_retry_time": next_check,
        "last_error": "Waiting for technician or doctor approval (approve_time is null)",
        "details": details,
        "created_at": now,
        "updated_at": now
    }
    res = col.insert_one(doc)
    return res.inserted_id


def enqueue_for_retry(barcode, bill_number=None, reason="API_ERROR", error_msg="", patient_name=None, bill_type=None, max_retries=5):
    """
    Queues a record for retry after an API failure, network error, or missing record.
    Uses exponential backoff.
    """
    if not barcode:
        return None

    col = get_retry_queue_collection()
    now = datetime.now()

    existing = col.find_one({"barcode": str(barcode), "status": {"$in": ["PENDING_RETRY", "WAITING_APPROVAL"]}})
    if existing:
        new_count = existing.get("retry_count", 0) + 1
        if new_count >= existing.get("max_retries", max_retries):
            new_status = "FAILED_PERMANENT"
            next_time = now + timedelta(days=365)
        else:
            new_status = "PENDING_RETRY"
            next_time = calculate_next_retry(new_count)

        col.update_one(
            {"_id": existing["_id"]},
            {"$set": {
                "status": new_status,
                "reason": reason,
                "retry_count": new_count,
                "next_retry_time": next_time,
                "last_error": str(error_msg),
                "updated_at": now,
                "bill_number": bill_number or existing.get("bill_number"),
                "patient_name": patient_name or existing.get("patient_name")
            }}
        )
        return existing["_id"]

    next_time = calculate_next_retry(1)
    doc = {
        "barcode": str(barcode),
        "bill_number": str(bill_number) if bill_number else None,
        "bill_type": str(bill_type) if bill_type else None,
        "patient_name": str(patient_name) if patient_name else None,
        "status": "PENDING_RETRY",
        "reason": reason,
        "retry_count": 1,
        "max_retries": max_retries,
        "next_retry_time": next_time,
        "last_error": str(error_msg),
        "created_at": now,
        "updated_at": now
    }
    res = col.insert_one(doc)
    return res.inserted_id


def mark_resolved(barcode, bill_number=None, message="Sent successfully"):
    """Marks queue item as resolved once results are successfully posted to HMS."""
    col = get_retry_queue_collection()
    now = datetime.now()
    query = {"$or": []}
    if barcode:
        query["$or"].append({"barcode": str(barcode)})
    if bill_number:
        query["$or"].append({"bill_number": str(bill_number)})

    if not query["$or"]:
        return

    col.update_many(
        {"$and": [query, {"status": {"$in": ["WAITING_APPROVAL", "PENDING_RETRY", "FAILED_PERMANENT"]}}]},
        {"$set": {
            "status": "RESOLVED",
            "last_error": str(message),
            "updated_at": now
        }}
    )


def get_due_items(limit=25):
    """Fetches items whose retry or approval check time has arrived."""
    col = get_retry_queue_collection()
    now = datetime.now()
    cursor = col.find({
        "status": {"$in": ["WAITING_APPROVAL", "PENDING_RETRY"]},
        "next_retry_time": {"$lte": now}
    }).sort("next_retry_time", 1).limit(limit)
    return list(cursor)


def force_retry_all():
    """Forces all pending, waiting, or failed items to retry immediately."""
    col = get_retry_queue_collection()
    now = datetime.now()
    res = col.update_many(
        {"status": {"$in": ["WAITING_APPROVAL", "PENDING_RETRY", "FAILED_PERMANENT"]}},
        {"$set": {
            "status": "PENDING_RETRY",
            "next_retry_time": now,
            "updated_at": now
        }}
    )
    return res.modified_count


def force_retry_single(identifier):
    """Forces a single bill or barcode to retry immediately."""
    col = get_retry_queue_collection()
    now = datetime.now()
    clean_id = str(identifier).strip()
    res = col.update_many(
        {
            "$or": [{"barcode": clean_id}, {"bill_number": clean_id}],
            "status": {"$in": ["WAITING_APPROVAL", "PENDING_RETRY", "FAILED_PERMANENT"]}
        },
        {"$set": {
            "status": "PENDING_RETRY",
            "next_retry_time": now,
            "updated_at": now
        }}
    )
    return res.modified_count


def get_queue_summary():
    """Returns aggregated summary counts for the dashboard."""
    col = get_retry_queue_collection()
    pipeline = [
        {"$group": {"_id": "$status", "count": {"$sum": 1}}}
    ]
    counts = {"WAITING_APPROVAL": 0, "PENDING_RETRY": 0, "FAILED_PERMANENT": 0, "RESOLVED": 0}
    try:
        for item in col.aggregate(pipeline):
            status = item.get("_id")
            if status in counts:
                counts[status] = item.get("count", 0)
    except Exception as e:
        logger.error(f"Error fetching queue summary: {e}")
    return counts


def get_recent_queue_items(limit=30, status_filter=None):
    """Fetches recent queue items with formatted fields for UI presentation."""
    col = get_retry_queue_collection()
    query = {}
    if status_filter and status_filter != "ALL":
        query["status"] = status_filter

    items = list(col.find(query).sort("updated_at", -1).limit(limit))
    for it in items:
        it["_id"] = str(it["_id"])
        if it.get("next_retry_time"):
            it["next_retry_time_str"] = it["next_retry_time"].strftime("%d/%m/%Y %H:%M:%S")
        if it.get("updated_at"):
            it["updated_at_str"] = it["updated_at"].strftime("%d/%m/%Y %H:%M:%S")
        if it.get("created_at"):
            it["created_at_str"] = it["created_at"].strftime("%d/%m/%Y %H:%M:%S")
    return items

