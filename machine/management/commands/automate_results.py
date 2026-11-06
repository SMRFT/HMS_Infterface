from django.core.management.base import BaseCommand
from machine.views import process_lab_result, parse_approve_time
from machine.models import MachineAutomationLog
from machine import retry_service
import os
import json
import time
from datetime import datetime, timedelta

class Command(BaseCommand):
    help = 'Automatically process lab results from MongoDB and manage retry queue for approved results & API failures'

    def handle(self, *args, **options):
        # Startup connection guard
        self.stdout.write("Initializing MongoDB connection...")
        while True:
            try:
                db = retry_service.get_mongo_db()
                db.command("ping")
                break
            except Exception as conn_err:
                self.stdout.write(self.style.WARNING(
                    f"Waiting for MongoDB connection ({conn_err}). Retrying in 5 seconds..."
                ))
                time.sleep(5)

        col = db.core_testvalue

        # Start checking recent records
        last_check_time = datetime.now() - timedelta(hours=24)
        last_retry_poll_time = datetime.now() - timedelta(seconds=60)

        self.stdout.write(self.style.SUCCESS(
            f"Starting automation loop (Track 1: New Results | Track 2: Approval & Error Retry Queue). "
            f"Monitoring core_testvalue since {last_check_time}"
        ))

        while True:
            try:
                now = datetime.now()

                # ==========================================
                # Track 1: Process New / Modified Results
                # ==========================================
                query = {
                    "$or": [
                        {"created_date": {"$gt": last_check_time}},
                        {"lastmodified_date": {"$gt": last_check_time}}
                    ]
                }

                cursor = col.find(query).sort("created_date", 1)
                next_check_time = datetime.now()

                processed_barcodes = set()
                new_count = 0

                for doc in cursor:
                    barcode = doc.get("barcode")
                    if not barcode or barcode in processed_barcodes:
                        continue

                    processed_barcodes.add(barcode)
                    result = process_lab_result(barcode, is_manual=False)

                    if result.get("status") == "success":
                        self.stdout.write(self.style.SUCCESS(
                            f"[New] Successfully processed {barcode}: {result.get('processed')} items"
                        ))
                    new_count += 1

                last_check_time = next_check_time

                # ==========================================
                # Track 2: Poll Retry Queue (Approvals & Errors)
                # ==========================================
                # Run retry check every 15 seconds
                if (now - last_retry_poll_time).total_seconds() >= 15:
                    last_retry_poll_time = now
                    due_items = retry_service.get_due_items(limit=25)

                    for item in due_items:
                        item_id = item.get("_id")
                        barcode = item.get("barcode")
                        bill_number = item.get("bill_number")
                        bill_type = item.get("bill_type")
                        queue_status = item.get("status")

                        if not barcode and not bill_number:
                            continue

                        ident = barcode or bill_number

                        if queue_status == "WAITING_APPROVAL":
                            # Check if the result has now been approved in core_testvalue
                            normalized = ident.replace("/", "")
                            core_docs = list(col.find({"barcode": normalized}))
                            if not core_docs and bill_type and len(normalized) == 10:
                                ext = f"{normalized[:4]}{bill_type}{normalized[4:]}"
                                core_docs = list(col.find({"barcode": ext}))

                            is_now_approved = False
                            for cd in core_docs:
                                try:
                                    tds = json.loads(cd.get("testdetails", "[]"))
                                    for t in tds:
                                        if parse_approve_time(t.get("approve_time")):
                                            is_now_approved = True
                                            break
                                except Exception:
                                    continue
                                if is_now_approved:
                                    break

                            if is_now_approved:
                                self.stdout.write(self.style.NOTICE(
                                    f"[Queue: Approved!] Barcode {ident} is now approved. Dispatching to HMS..."
                                ))
                                res = process_lab_result(ident, is_manual=False, bill_type=bill_type)
                                if res.get("status") == "success":
                                    self.stdout.write(self.style.SUCCESS(
                                        f"[Queue] Dispatched approved results for {ident}: {res.get('processed')} items"
                                    ))
                                    retry_service.mark_resolved(ident, bill_number, "Approved and dispatched successfully")
                                else:
                                    retry_service.enqueue_for_retry(
                                        barcode=ident,
                                        bill_number=bill_number,
                                        reason="API_ERROR",
                                        error_msg="Approved but failed to post to HMS API",
                                        bill_type=bill_type
                                    )
                            else:
                                # Still waiting for approval, schedule next check in 3 minutes
                                retry_service.enqueue_for_approval(
                                    barcode=ident,
                                    bill_number=bill_number,
                                    bill_type=bill_type,
                                    patient_name=item.get("patient_name")
                                )

                        elif queue_status == "PENDING_RETRY":
                            self.stdout.write(self.style.WARNING(
                                f"[Queue: Retry] Retrying transmission for {ident} (Attempt {item.get('retry_count', 1)})..."
                            ))
                            res = process_lab_result(ident, is_manual=False, bill_type=bill_type)
                            if res.get("status") == "success":
                                self.stdout.write(self.style.SUCCESS(
                                    f"[Queue] Successfully resolved {ident}: {res.get('processed')} items"
                                ))
                                retry_service.mark_resolved(ident, bill_number, f"Retry succeeded: {res.get('processed')} items")
                            else:
                                retry_service.enqueue_for_retry(
                                    barcode=ident,
                                    bill_number=bill_number,
                                    reason=item.get("reason", "API_ERROR"),
                                    error_msg=str(res.get("debug_errors") or res.get("error") or "Retry attempt failed"),
                                    bill_type=bill_type
                                )

                # Sleep briefly
                time.sleep(5)

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error in automation loop: {str(e)}"))
                try:
                    MachineAutomationLog.objects.create(
                        status="CRITICAL",
                        message=f"Automation Loop Error: {str(e)}"
                    )
                except Exception:
                    pass
                time.sleep(5)
