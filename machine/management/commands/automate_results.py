from django.core.management.base import BaseCommand
from machine.views import process_lab_result
from machine.models import MachineAutomationLog
from pymongo import MongoClient
import os
import time
from datetime import datetime, timedelta

class Command(BaseCommand):
    help = 'Automatically process lab results from MongoDB by polling for new test values'

    def handle(self, *args, **options):
        mongo_url = os.getenv("GLOBAL_DB_HOST")
        if not mongo_url:
            self.stdout.write(self.style.ERROR("GLOBAL_DB_HOST not set"))
            return

        client = MongoClient(mongo_url)
        db = client.Diagnostics
        # Connect to core_testvalue to detect NEW results (Logic: Trigger on Result Arrival)
        col = db.core_testvalue
        
        # Start checking from 1 hour ago (catch up on recent interruptions)
        last_check_time = datetime.now() - timedelta(hours=300)
        self.stdout.write(f"Starting automation loop. Monitoring core_testvalue for new results since {last_check_time}")

        while True:
            try:
                # Find documents created or modified after last_check_time
                # This ensures we pick up any new result or update to an existing result
                query = {
                    "$or": [
                        {"created_date": {"$gt": last_check_time}},
                        {"lastmodified_date": {"$gt": last_check_time}}
                    ]
                }
                
                # Fetch recent records, sorted by time to process in order
                cursor = col.find(query).sort("created_date", 1)
                
                # Capture the time BEFORE processing to use as the next start time
                # logical overlap prevents missing items that occur during valid processing time
                next_check_time = datetime.now() 
                
                processed_barcodes = set()
                count = 0
                
                for doc in cursor:
                    barcode = doc.get("barcode")
                    
                    if not barcode or barcode in processed_barcodes:
                        continue
                        
                    processed_barcodes.add(barcode)
                    
                    result = process_lab_result(barcode)
                    
                    if result.get("status") == "success":
                        self.stdout.write(self.style.SUCCESS(f"Successfully processed {barcode}: {result.get('processed')} items"))
                    
                    count += 1
                
                if count > 0:
                    # self.stdout.write(f"Processed {count} unique barcodes.")
                    pass
                
                last_check_time = next_check_time
                
                # Sleep briefly to avoid hammering the DB
                time.sleep(5)
                
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error in automation loop: {str(e)}"))
                try:
                    MachineAutomationLog.objects.create(
                        status="CRITICAL",
                        message=f"Automation Loop Error: {str(e)}"
                    )
                except:
                    pass
                time.sleep(5)
