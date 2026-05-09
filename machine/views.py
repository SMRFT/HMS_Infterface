from django.shortcuts import render
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status
from .serializers import HMSMISerializer
import os
import json
import requests
from datetime import datetime
from pymongo import MongoClient
from .models import TestResult, MachineAutomationLog, ManualEntryLog
from pyauth.auth import HasRolePermission
from django.views.decorators.csrf import csrf_exempt
import logging

logger = logging.getLogger("hmsmi")


def log_result_action(bill_number, test_code, status, message, response_data=None, is_manual=False):
    """Helper to log actions to the appropriate database tables."""
    # Always log to the automation log for overall visibility
    MachineAutomationLog.objects.create(
        bill_number=bill_number,
        test_code=test_code,
        status=status,
        message=message,
        response_data=json.dumps(response_data) if response_data and not isinstance(response_data, str) else response_data
    )
    
    # If manual, also log to the manual entry log
    if is_manual:
        ManualEntryLog.objects.create(
            bill_number=bill_number,
            test_code=test_code,
            status=status,
            message=message,
            response_payload=json.dumps(response_data) if response_data and not isinstance(response_data, str) else response_data
        )


@csrf_exempt
@api_view(['POST'])
# @permission_classes([HasRolePermission])
def create_hmsmi(request):
    logger.info("create_hmsmi API called")
    logger.info("Request Method: %s", request.method)
    logger.info("Request User: %s", getattr(request.user, "username", "Anonymous"))
    logger.info("Request Data: %s", request.data)

    try:
        serializer = HMSMISerializer(data=request.data)

        if serializer.is_valid():
            serializer.save()
            
            # Auto-process the bill after receiving data
            bill_number = request.data.get('BillNumber')
            bill_type = request.data.get('BillType')
            if bill_number:
                process_lab_result(bill_number, is_manual=False, bill_type=bill_type)

            response_data = {
                'success': True,
                'data': serializer.data,
                'message': 'Bill data received and processing initiated.'
            }
            return Response(response_data, status=status.HTTP_200_OK)

        else:
            response_data = {
                'success': False,
                'errors': serializer.errors,
                'message': 'Validation failed.'
            }

            # Log validation error
            logger.warning("create_hmsmi VALIDATION FAILED: %s", response_data)
            return Response(response_data, status=status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        response_data = {
            'success': False,
            'errors': str(e),
            'message': 'An unexpected error occurred.'
        }

        # Log exception with stack trace
        logger.error("create_hmsmi EXCEPTION occurred", exc_info=True)
        return Response(response_data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def save_test_result(machine, test_code, sub_test_code, result_value, approve_time, is_manual=False):
    
    # STRICTLY process ONLY IP patients for automatic automation, allow manual overrides
    if not is_manual and str(machine.get("IPOPType")).upper() != "IP":
        log_result_action(
            bill_number=machine.get("BillNumber"),
            test_code=test_code,
            status="SKIPPED",
            message=f"Skipped non-IP patient: {machine.get('IPOPType')}",
            is_manual=is_manual
        )
        return {"STATUS": 0, "MESSAGE": "SKIPPED_NON_IP"}

    result_data = {
        "resultdate": approve_time.strftime("%d/%m/%Y") if approve_time else None,
        "resulttime": approve_time.strftime("%H:%M:%S") if approve_time else None,
        "resultvalue": str(result_value),
        "billnumber": machine.get("BillNumber"),
        "billtype": machine.get("BillType"),
        "testcode": test_code,
        "subtestcode": sub_test_code, # Use the passed sub_test_code
        "serialnumber": machine.get("SerialNumber"),
        "opnumber": machine.get("IPOPNumber") or machine.get("OPNumber"),
        "patientname": machine.get("PatientName"),
        "patientage": machine.get("PatientAge"),
        "gender": machine.get("Gender")
    }

    # Check for existing record in TestResult model
    existing_obj = TestResult.objects.filter(
        billnumber=machine.get("BillNumber"),
        testcode=test_code,
        subtestcode=sub_test_code
    ).first()

    if existing_obj:
        if existing_obj.status and "SUCCESS" in str(existing_obj.status).upper():
            return {"STATUS": 0, "ERROR": "RESULT_ALREADY_ADDED"}
        test_result_obj = existing_obj
        # Update existing object fields
        for key, value in result_data.items():
            setattr(test_result_obj, key, value)
        test_result_obj.save()
    else:
        test_result_obj = TestResult.objects.create(**result_data)

    try:
        # 1. Update the HMS API
        response = requests.post(
            "http://156.67.110.232:8019/lab-api/save-lab-result-data/",
            data=result_data,
            headers={"Authorization": f"Token {os.getenv('HMS_API_KEY')}"}
        )

        log_status = "SUCCESS" if response.status_code == 200 else "ERROR"
        log_result_action(
            bill_number=machine.get("BillNumber"),
            test_code=test_code,
            status=log_status,
            message=f"API Response Code: {response.status_code}",
            response_data=response.text,
            is_manual=is_manual
        )

        if response.status_code == 200:
            test_result_obj.status = response.text
            test_result_obj.save()
            
            # 2. ALSO update the local machine_hmsmi collection in MongoDB
            try:
                client = MongoClient(os.getenv("GLOBAL_DB_HOST"))
                db = client['Diagnostics']
                machine_col = db['machine_hmsmi']
                
                # Update based on the original machine record's ID to be precise
                machine_col.update_one(
                    {"_id": machine.get("_id")},
                    {"$set": {
                        "resultvalue": str(result_value),
                        "resultdate": result_data["resultdate"],
                        "resulttime": result_data["resulttime"],
                        "testcode": test_code,
                        "subtestcode": sub_test_code,
                        "status": '{"STATUS":1}'
                    }}
                )
                client.close()
            except Exception as mongo_err:
                logger.error(f"Failed to update machine_hmsmi: {str(mongo_err)}")
                
            return {"STATUS": 1, "MESSAGE": "SUCCESS"}
        else:
            return {"STATUS": 0, "ERROR": "API_ERROR", "DETAILS": response.text}

    except Exception as e:
        log_result_action(
            bill_number=machine.get("BillNumber"),
            test_code=test_code,
            status="EXCEPTION",
            message=str(e),
            is_manual=is_manual
        )
        return {"STATUS": 0, "ERROR": str(e)}

def process_lab_result(bill_number, is_manual=False, bill_type=None, test_code_filter=None):
    mongo_url = os.getenv("GLOBAL_DB_HOST")
    client = MongoClient(mongo_url)
    db = client.Diagnostics
    machine_col = db.machine_hmsmi
    core_value_col = db.core_testvalue
    core_detail_col = db.core_testdetails

    # 1. Fetch HMS Machine Records (to get BillType if needed)
    query = {"BillNumber": bill_number}
    if bill_type and str(bill_type).lower() != "null":
        query["BillType"] = str(bill_type)
    machine_records = list(machine_col.find(query))
    
    # Fallback: validation for missing slash in bill number (e.g. 2526014369 -> 2526/014369)
    if not machine_records and len(bill_number) == 10 and bill_number.isdigit():
        formatted_bill = f"{bill_number[:4]}/{bill_number[4:]}"
        machine_records = list(machine_col.find({"BillNumber": formatted_bill}))
        
    # Fallback: validation for 12-digit bill number including BillType (e.g. 252624014369 -> 2526/014369 and BillType: 24)
    if not machine_records and len(bill_number) == 12 and bill_number.isdigit():
        formatted_bill = f"{bill_number[:4]}/{bill_number[6:]}"
        bill_type_from_input = bill_number[4:6]
        machine_records = list(machine_col.find({"BillNumber": formatted_bill, "BillType": bill_type_from_input}))
        
    if not machine_records:
        log_result_action(
            bill_number=bill_number,
            test_code=None,
            status="ERROR",
            message="Machine HMSMI records not found",
            is_manual=is_manual
        )
        return {"error": f"Machine HMSMI records not found for bill {bill_number}", "status_code": 404}

    # 2. Get BillType from machine records for barcode fallback
    primary_machine_rec = machine_records[0]
    bill_type = primary_machine_rec.get("BillType")

    # 3. Fetch core_testvalue using barcode
    normalized_bill = bill_number.replace("/", "")
    core_values = list(core_value_col.find({"barcode": normalized_bill}))
    
    # Fallback: Check if core_testvalue barcode includes BillType (e.g. 2526 + 24 + 014369)
    if not core_values and bill_type and len(normalized_bill) == 10:
        extended_barcode = f"{normalized_bill[:4]}{bill_type}{normalized_bill[4:]}"
        core_values = list(core_value_col.find({"barcode": extended_barcode}))

    if not core_values:
        log_result_action(
            bill_number=bill_number,
            test_code=None,
            status="ERROR",
            message="Core test value not found in MongoDB (Checked both normal and extended barcodes)",
            is_manual=is_manual
        )
        return {"error": "Core test value not found", "status_code": 404}

    # 4. Parse and Aggregate testdetails from ALL matching core_testvalue documents
    all_testdetails = []
    for cv in core_values:
        try:
            details = json.loads(cv["testdetails"])
            if isinstance(details, list):
                # Filter by test_code if provided
                if test_code_filter:
                    # Robust filtering: check multiple possible identifying fields
                    details = [
                        t for t in details 
                        if str(t.get('test_code') or t.get('testname') or t.get('name') or t.get('test_id')) == str(test_code_filter)
                    ]
                all_testdetails.extend(details)
        except (TypeError, json.JSONDecodeError):
            continue # Skip malformed JSON but keep processing others

    if not all_testdetails:
        log_result_action(
            bill_number=bill_number,
            test_code=None,
            status="ERROR",
            message="No valid testdetails found in core values",
            is_manual=is_manual
        )
        return {"error": "No valid testdetails found in core values", "status_code": 500}

    processed_count = 0
    errors = []
    
    # 5. Build machine_map: map potential identifiers to machine records
    machine_map = {}
    for m in machine_records:
        st_code = str(m.get("SubTestcode") or "").strip()
        t_code = str(m.get("TestCode") or "").strip()
        st_name = str(m.get("SubTestName") or "").strip()
        
        if st_code: machine_map[st_code] = m
        if t_code: machine_map[t_code] = m
        if st_name: machine_map[st_name] = m # Fallback to name match if codes fail


    # 5. Iterate through ALL aggregated test results
    for test in all_testdetails:
        # Try to get test_id from multiple possible locations
        test_id = test.get("test_id") or test.get("id")
        if not test_id:
            continue

        # Fetch test master once for the group
        test_master = core_detail_col.find_one({
            "test_id": test_id,
            "is_active": True
        })

        if not test_master:
            errors.append(f"Master not found for test_id: {test_id}")
            continue

        # Prepare list of result items to process from this test entry
        result_items = []

        # Parse approve_time
        approve_time_str = test.get("approve_time")
        approve_time_dt = None
        if approve_time_str and approve_time_str != "null":
            for fmt in ("%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M:%S", "%Y-%m-%d %H:%M", "%d/%m/%Y %H:%M"):
                try:
                    approve_time_dt = datetime.strptime(approve_time_str, fmt)
                    break
                except ValueError:
                    continue

        if "parameters" in test and isinstance(test["parameters"], list) and test["parameters"]:
            # Nested parameters in result (e.g. from Analyzer)
            for p in test["parameters"]:
                result_items.append({
                    "test_code": p.get("test_code"),
                    "test_name": p.get("test_name") or p.get("name") or p.get("testname"),
                    "value": p.get("value") or p.get("result"),
                    "approve_time": approve_time_dt
                })
        else:
            # Flat result (Single value)
            result_items.append({
                "test_code": test.get("test_code"),
                "test_name": test.get("test_name") or test.get("testname") or test.get("name"),
                "value": test.get("value") or test.get("result"),
                "approve_time": approve_time_dt
            })

        # Process each result item against the master
        for item in result_items:
            result_test_code = item["test_code"]
            result_test_name = item["test_name"]
            result_value = item["value"]
            approve_time = item["approve_time"]

            if (not result_test_code and not result_test_name) or result_value is None or approve_time is None:
                if approve_time is None and (result_test_code or result_test_name):
                     log_result_action(
                        bill_number=bill_number,
                        test_code=result_test_code or result_test_name,
                        status="SKIPPED",
                        message="Result not approved (approve_time is null)",
                        is_manual=is_manual
                    )
                continue

            # Collect all HMS subtestcodes this result could potentially fulfill
            potential_hms_codes = set()

            # A. Parameter Match
            master_params = test_master.get("parameters", [])
            if isinstance(master_params, dict):
                # Flatten dict to list
                flat_params = []
                for dev, p_list in master_params.items():
                    flat_params.extend(p_list)
                master_params = flat_params
            
            for p in master_params:
                # Match result to master parameter by test_code
                if str(p.get("test_code") or p.get("test_name") or p.get("name")) == str(result_test_code):
                    sub_code = p.get("hms_subtestcode")
                    if sub_code and str(sub_code) != "0":
                        potential_hms_codes.add(str(sub_code))

                # Match result to master parameter by hms_subtestcode
                if str(p.get("hms_subtestcode")) == str(result_test_code):
                    potential_hms_codes.add(str(result_test_code))

            # B. Main Test Code Match 
            main_code = test_master.get("hms_testcode")
            if main_code and str(main_code) != "0":
                 potential_hms_codes.add(str(main_code))

            # C. Direct Match (Legacy/Fallback)
            master_test_code = test_master.get("test_code")
            if master_test_code and result_test_code and str(master_test_code) == str(result_test_code):
                 sub_code = test_master.get("hms_subtestcode")
                 if sub_code and str(sub_code) != "0":
                     potential_hms_codes.add(str(sub_code))

            # D. Direct Match from Analyzer Code (Fallback)
            if result_test_code:
                potential_hms_codes.add(str(result_test_code))
            
            # E. Name Match (Fallback)
            if result_test_name:
                potential_hms_codes.add(str(result_test_name))
            
            # If we have no candidates, skip
            if not potential_hms_codes:
                continue

            # 7. Iterate through candidates and save for each one found in the bill
            match_found = False
            for hms_code in potential_hms_codes:
                machine_record = machine_map.get(str(hms_code))
                if machine_record:
                    # 8. Save Result
                    hms_main_testcode = test_master.get("hms_testcode")
                    
                    # Try to find the specific sub-code from master if we matched a parameter
                    final_sub_code = machine_record.get("SubTestcode")
                    for p in master_params:
                        if str(p.get("hms_subtestcode")) == str(hms_code):
                            final_sub_code = hms_code
                            break

                    save_resp = save_test_result(
                        machine=machine_record,
                        test_code=hms_main_testcode, 
                        sub_test_code=final_sub_code, # Pass specifically
                        result_value=result_value,
                        approve_time=approve_time,
                        is_manual=is_manual
                    )
                    if save_resp.get("STATUS") == 1:
                        processed_count += 1
                        match_found = True
            
            if not match_found:
                errors.append(f"No matching machine record for test {result_test_code} (Checked codes: {potential_hms_codes})")

    if processed_count > 0:
        log_result_action(
            bill_number=bill_number,
            test_code=None,
            status="SUCCESS",
            message=f"Successfully posted {processed_count} results",
            is_manual=is_manual
        )
        return {
            "status": "success",
            "processed": processed_count,
            "message": "Results posted successfully"
        }
    
    log_result_action(
        bill_number=bill_number,
        test_code=None,
        status="WARNING",
        message="No new results matched or saved",
        response_data={"debug_errors": errors},
        is_manual=is_manual
    )
    return {
        "status": "partial_success",
        "processed": 0,
        "message": "No new results matched or saved.",
        "debug_errors": errors
    }


@api_view(['POST', 'GET'])
def post_test_results(request, bill_number):
    result = process_lab_result(bill_number)
    
    if "error" in result:
        # Map internal status codes to DRF status codes
        code = result.get("status_code", status.HTTP_400_BAD_REQUEST)
        if code == 404:
            drf_status = status.HTTP_404_NOT_FOUND
        elif code == 500:
            drf_status = status.HTTP_500_INTERNAL_SERVER_ERROR
        else:
            drf_status = status.HTTP_400_BAD_REQUEST
            
        return Response(result, status=drf_status)
        

    return Response(result, status=status.HTTP_200_OK)


@api_view(['GET'])
def manual_entry_page(request):
    # Fetch recent manual logs
    logs = ManualEntryLog.objects.all().order_by('-timestamp')[:50]
    return render(request, 'manual_entry.html', {'logs': logs})

@api_view(['POST'])
def send_manual_result(request):
    bill_number = request.data.get('bill_number')
    bill_type = request.data.get('bill_type')
    test_code = request.data.get('test_code') # Optional specific test
    if not bill_number:
        return Response({"error": "Bill number is required"}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        # Process the result with optional filters
        result = process_lab_result(bill_number, is_manual=True, bill_type=bill_type, test_code_filter=test_code)
        return Response(result, status=status.HTTP_200_OK)
        
    except Exception as e:
        log_result_action(
            bill_number=bill_number,
            test_code=None,
            status="ERROR",
            message=f"Manual Processing Exception: {str(e)}",
            is_manual=True
        )
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def search_machine_records(request):
    query = request.GET.get('q', '')
    if len(query) < 2:
        return Response([], status=status.HTTP_200_OK)
    
    try:
        mongo_url = os.getenv("GLOBAL_DB_HOST")
        client = MongoClient(mongo_url)
        db = client.Diagnostics
        col = db.machine_hmsmi
        
        # Search by BillNumber, IPOPNumber, or PatientName
        search_filter = {
            "$or": [
                {"BillNumber": {"$regex": query, "$options": "i"}},
                {"IPOPNumber": {"$regex": query, "$options": "i"}},
                {"PatientName": {"$regex": query, "$options": "i"}}
            ]
        }
        
        # Aggregate to get unique BillNumber + BillType combinations
        pipeline = [
            {"$match": search_filter},
            {"$group": {
                "_id": {
                    "BillNumber": "$BillNumber",
                    "BillType": "$BillType"
                },
                "BillNumber": {"$first": "$BillNumber"},
                "BillType": {"$first": "$BillType"},
                "PatientName": {"$first": "$PatientName"},
                "IPOPNumber": {"$first": "$IPOPNumber"}
            }},
            {"$limit": 10}
        ]
        
        results = list(col.aggregate(pipeline))
        
        formatted = []
        for r in results:
            formatted.append({
                "bill_number": r.get("BillNumber"),
                "bill_type": r.get("BillType"),
                "patient_name": r.get("PatientName"),
                "op_number": r.get("IPOPNumber")
            })
            
        return Response(formatted, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)




@api_view(['POST'])
def fetch_test_data(request):
    bill_number = request.data.get('bill_number')
    bill_type = request.data.get('bill_type')
    
    if not bill_number:
        return Response({"error": "Bill number is required"}, status=status.HTTP_400_BAD_REQUEST)
        
    try:
        mongo_url = os.getenv("GLOBAL_DB_HOST")
        client = MongoClient(mongo_url)
        db = client.Diagnostics
        machine_col = db.machine_hmsmi
        core_value_col = db.core_testvalue
        
        # 1. Normalize and handle 12-digit Barcodes
        barcode_query = bill_number.replace("/", "")
        actual_bill = bill_number
        actual_type = bill_type

        if len(barcode_query) == 12 and barcode_query.isdigit():
            actual_bill = f"{barcode_query[:4]}/{barcode_query[6:]}"
            actual_type = barcode_query[4:6]
            if not bill_type or str(bill_type).lower() == "null":
                bill_type = actual_type
        
        # Use parsed bill number for machine lookup
        query = {"BillNumber": actual_bill}
        if bill_type and str(bill_type).lower() != "null":
            query["BillType"] = str(bill_type)
        
        machine_rec = machine_col.find_one(query)
        final_bill_type = bill_type or (machine_rec.get("BillType") if machine_rec else None)
        
        # 2. Search for results in core_testvalue using the original barcode
        core_values = list(core_value_col.find({"barcode": barcode_query}))
        
        # Fallback for extended barcode
        if not core_values and final_bill_type and len(barcode_query) == 10:
            extended_barcode = f"{barcode_query[:4]}{final_bill_type}{barcode_query[4:]}"
            core_values = list(core_value_col.find({"barcode": extended_barcode}))
            
        # 3. Extract test details
        all_tests = []
        for cv in core_values:
            try:
                details = json.loads(cv.get("testdetails", "[]"))
                if isinstance(details, list):
                    all_tests.extend(details)
            except:
                continue
                
        return Response({
            "patient_name": machine_rec.get("PatientName") if machine_rec else "Unknown",
            "bill_number": bill_number,
            "bill_type": final_bill_type,
            "tests": all_tests
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
