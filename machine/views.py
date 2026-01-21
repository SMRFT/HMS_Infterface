from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from .serializers import HMSMISerializer
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status
import os
import json
import requests
from datetime import datetime
from pymongo import MongoClient
from .models import TestResult
from pyauth.auth import HasRoleAndDataPermission
from django.views.decorators.csrf import csrf_exempt


@csrf_exempt
@api_view(['POST'])
@permission_classes([HasRoleAndDataPermission])
def create_hmsmi(request):
    try:
        serializer = HMSMISerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({
                'success': True,
                'data': serializer.data,
                'message': 'HMSMI data created successfully.'
            }, status=status.HTTP_200_OK)
        else:
            return Response({
                'success': False,
                'errors': serializer.errors,
                'message': 'Validation failed.'
            }, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({
            'success': False,
            'errors': str(e),
            'message': 'An unexpected error occurred.'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



def save_test_result(machine, test_code, result_value,approve_time):
    
    # STRICTLY process ONLY IP patients
    if str(machine.get("IPOPType")).upper() != "IP":
        return {"STATUS": 0, "MESSAGE": "SKIPPED_NON_IP"}

    result_data = {
        "resultdate": approve_time.strftime("%d/%m/%Y") if approve_time else None,
        "resulttime": approve_time.strftime("%H:%M:%S") if approve_time else None,
        "resultvalue": str(result_value),
        "billnumber": machine.get("BillNumber"),
        "billtype": machine.get("BillType"),
        "testcode": test_code,
        "subtestcode": machine.get("SubTestcode"),
        "serialnumber": machine.get("SerialNumber"),
        "opnumber": machine.get("IPOPNumber") or machine.get("OPNumber"),
        "patientname": machine.get("PatientName"),
        "patientage": machine.get("PatientAge"),
        "gender": machine.get("Gender")
    }

    # Check for existing record
    existing_obj = TestResult.objects.filter(
        billnumber=machine.get("BillNumber"),
        testcode=test_code,
        subtestcode=machine.get("SubTestcode")
    ).first()

    if existing_obj:
        # If record exists and has a status, it's fully processed.
        if existing_obj.status:
            return {"STATUS": 0, "ERROR": "RESULT_ALREADY_ADDED"}
        
        # If record exists but status is null/empty, we reuse it and try to send data again.
        test_result_obj = existing_obj
    else:
        # Create new record
        test_result_obj = TestResult.objects.create(**result_data)

    # Since we already checked for IP above, we can just proceed with sending
    try:
        response = requests.post(
            "http://156.67.110.232:8019/lab-api/save-lab-result-data/",
            data=result_data,
            headers={"Authorization": f"Token {os.getenv('HMS_API_KEY')}"}
        )
        if response.status_code == 200:
            test_result_obj.status = response.text
            test_result_obj.save()
    except Exception:
        pass

    return {"STATUS": 1}

def process_lab_result(bill_number):
    mongo_url = os.getenv("GLOBAL_DB_HOST")
    client = MongoClient(mongo_url)
    db = client.Diagnostics
    machine_col = db.machine_hmsmi
    core_value_col = db.core_testvalue
    core_detail_col = db.core_testdetails

    # 1. Normalize Bill Number (remove /)
    normalized_bill = bill_number.replace("/", "")

    # 2. Fetch core_testvalue using barcode
    core_values = list(core_value_col.find({"barcode": normalized_bill}))
    if not core_values:
        return {"error": "Core test value not found", "status_code": 404}

    # 3. Fetch HMS Machine Records
    machine_records = list(machine_col.find({"BillNumber": bill_number}))
    
    # Fallback: validation for missing slash in bill number (e.g. 2526014369 -> 2526/014369)
    if not machine_records and len(bill_number) == 10 and bill_number.isdigit():
        formatted_bill = f"{bill_number[:4]}/{bill_number[4:]}"
        machine_records = list(machine_col.find({"BillNumber": formatted_bill}))
        
    if not machine_records:
        return {"error": f"Machine HMSMI records not found for bill {bill_number}", "status_code": 404}

    # 4. Parse and Aggregate testdetails from ALL matching core_testvalue documents
    all_testdetails = []
    for cv in core_values:
        try:
            details = json.loads(cv["testdetails"])
            if isinstance(details, list):
                all_testdetails.extend(details)
        except (TypeError, json.JSONDecodeError):
            continue # Skip malformed JSON but keep processing others

    if not all_testdetails:
         return {"error": "No valid testdetails found in core values", "status_code": 500}

    processed_count = 0
    errors = []
    
    # Track which machine records are satisfied to avoid creating duplicates if we re-run
    # Dictionary to map 'SubTestcode' -> machine_record
    machine_map = {str(m.get("SubTestcode")): m for m in machine_records if m.get("SubTestcode")}

    # 5. Iterate through ALL aggregated test results
    for test in all_testdetails:
        test_id = test.get("test_id")
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
                    "value": p.get("value"),
                    "approve_time": approve_time_dt
                })
        else:
            # Flat result (Single value)
            result_items.append({
                "test_code": test.get("test_code"),
                "value": test.get("value"),
                "approve_time": approve_time_dt
            })

        # Process each result item against the master
        for item in result_items:
            result_test_code = item["test_code"]
            result_value = item["value"]
            approve_time = item["approve_time"]

            
            if not result_test_code or result_value is None or approve_time is None:
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
                if str(p.get("test_code")) == str(result_test_code):
                    sub_code = p.get("hms_subtestcode")
                    if sub_code and str(sub_code) != "0":
                        potential_hms_codes.add(str(sub_code))

                # Match result to master parameter by hms_subtestcode
                if str(p.get("hms_subtestcode")) == str(result_test_code):
                    potential_hms_codes.add(str(result_test_code))

            # B. Main Test Code Match 
            # Note: Only apply main test code if this result item actually "belongs" to the main test
            # If we are processing a sub-parameter, does it fulfill the main test request?
            # Typically yes, if the machine requested the Group Code, any constituent part is relevant.
            # But usually we save the SPECIFIC result. 
            # If the user asks for "Electrolytes" (Group), they get 4 results.
            # We check if the BILL requests the Group Code.
            main_code = test_master.get("hms_testcode")
            if main_code and str(main_code) != "0":
                 potential_hms_codes.add(str(main_code))

            # C. Direct Match (Legacy/Fallback)
            master_test_code = test_master.get("test_code")
            if master_test_code and result_test_code and str(master_test_code) == str(result_test_code):
                 sub_code = test_master.get("hms_subtestcode")
                 if sub_code and str(sub_code) != "0":
                     potential_hms_codes.add(str(sub_code))

            # If we have no candidates, skip
            if not potential_hms_codes:
                continue

            # 7. Iterate through candidates and save for each one found in the bill
            match_found = False
            for hms_code in potential_hms_codes:
                machine_record = machine_map.get(str(hms_code))
                if machine_record:
                    # 8. Save Result
                    # User requested 'hsmtestcode' (hms_testcode) to be saved as testcode
                    hms_main_testcode = test_master.get("hms_testcode")
                    
                    save_resp = save_test_result(
                        machine=machine_record,
                        test_code=hms_main_testcode, 
                        result_value=result_value,
                        approve_time=approve_time
                    )
                    if save_resp.get("STATUS") == 1:
                        processed_count += 1
                    match_found = True
            
            if not match_found:
                pass

    if processed_count > 0:
        return {
            "status": "success",
            "processed": processed_count,
            "message": "Results posted successfully"
        }
    
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