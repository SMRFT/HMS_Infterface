from django.db import models

# Create your models here.
from django.db import models


class HMSMI(models.Model):
    BillNumber = models.CharField(max_length=50, unique=True)
    BillType = models.CharField(max_length=50)
    BilIDate = models.DateField()
    subtestcode= models.CharField(max_length=50)
    subtestname= models.CharField(max_length=60)
    serialnumber= models.CharField(max_length=50)
    mobilenumber=models.IntegerField()
    IPOPType = models.CharField(max_length=20)   # e.g., IP / OP
    IPOPNumber = models.CharField(max_length=50)
    PatientTitle = models.CharField(max_length=10)  # e.g., Mr, Ms, Dr
    PatientName = models.CharField(max_length=100)
    PatientAge = models.IntegerField()
    Gender = models.CharField(max_length=10)   # e.g., Male / Female / Other
    RefDoctor = models.CharField(max_length=100)
    TestCode = models.CharField(max_length=50)
    TestName = models.CharField(max_length=100)

    created_at = models.DateTimeField(auto_now_add=True)  # optional
    updated_at = models.DateTimeField(auto_now=True)      # optional

    def __str__(self):
        return f"{self.BillNumber} - {self.PatientName}"


from django.db import models


class TestResult(models.Model):
    resultdate = models.DateField()                       # e.g., 2021-09-22
    resulttime = models.TimeField()                       # e.g., 05:06:40
    resultvalue = models.CharField(max_length=100)        # kept CharField in case it's not always numeric
    billnumber = models.CharField(max_length=50)
    billtype = models.CharField(max_length=20)
    testcode = models.CharField(max_length=50)
    subtestcode = models.CharField(max_length=50, blank=True, null=True)
    serialnumber = models.IntegerField()
    opnumber = models.CharField(max_length=50)
    patientname = models.CharField(max_length=100)
    patientage = models.IntegerField()
    gender = models.CharField(max_length=10, choices=[
        ("MALE", "Male"),
        ("FEMALE", "Female"),
        ("OTHER", "Other"),
    ])

    created_at = models.DateTimeField(auto_now_add=True)  # optional audit field
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.patientname} - {self.testcode} ({self.resultdate})"
