from django.db import models

class HMSMI(models.Model):
    BillNumber = models.CharField(max_length=50)
    BillType = models.CharField(max_length=50)
    BillDate = models.DateTimeField()
    SubTestcode = models.CharField(max_length=50, blank=True, null=True)
    SubTestName = models.CharField(max_length=500, blank=True, null=True)
    SerialNumber = models.CharField(max_length=50, blank=True, null=True)
    mobilenumber = models.CharField(max_length=25)
    IPOPType = models.CharField(max_length=20) 
    IPOPNumber = models.CharField(max_length=50)
    PatientTitle = models.CharField(max_length=10, blank=True, null=True)  # e.g., Mr, Ms, Dr
    PatientName = models.CharField(max_length=100)
    PatientAge = models.IntegerField()
    Gender = models.CharField(max_length=10)   # e.g., Male / Female / Other
    RefDoctor = models.CharField(max_length=100)
    TestCode = models.CharField(max_length=50)
    TestName = models.CharField(max_length=100)

    created_date = models.DateTimeField(auto_now_add=True)  
    updated_date = models.DateTimeField(auto_now=True)      

    def __str__(self):
        return f"{self.BillNumber} - {self.PatientName}"


class TestResult(models.Model):
    billnumber = models.CharField(max_length=100)
    testcode = models.CharField(max_length=100)
    subtestcode = models.CharField(max_length=100)
    resultvalue = models.CharField(max_length=500)
    resultdate = models.CharField(max_length=50, null=True, blank=True)
    resulttime = models.CharField(max_length=50, null=True, blank=True)
    billtype = models.CharField(max_length=100, null=True, blank=True)
    serialnumber = models.CharField(max_length=100, null=True, blank=True)
    opnumber = models.CharField(max_length=100, null=True, blank=True)
    patientname = models.CharField(max_length=255, null=True, blank=True)
    patientage = models.CharField(max_length=50, null=True, blank=True)
    gender = models.CharField(max_length=50, null=True, blank=True)
    status = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"{self.billnumber} - {self.subtestcode}"


class MachineAutomationLog(models.Model):
    timestamp = models.DateTimeField(auto_now_add=True)
    bill_number = models.CharField(max_length=100, null=True, blank=True)
    test_code = models.CharField(max_length=100, null=True, blank=True)
    status = models.CharField(max_length=50) # SUCCESS, ERROR, INFO, SKIPPED
    message = models.TextField()
    response_data = models.TextField(null=True, blank=True) # To store API response or detailed error

    def __str__(self):
        return f"{self.timestamp} - {self.bill_number}: {self.message}"


class ManualEntryLog(models.Model):
    timestamp = models.DateTimeField(auto_now_add=True)
    bill_number = models.CharField(max_length=100)
    test_code = models.CharField(max_length=100, null=True, blank=True)
    status = models.CharField(max_length=50) # SUCCESS, ERROR, WARNING
    message = models.TextField()
    response_payload = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"{self.timestamp} - {self.bill_number}: {self.status}"


