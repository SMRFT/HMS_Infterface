from rest_framework import serializers
from bson import ObjectId

class ObjectIdField(serializers.Field):
    def to_representation(self, value):
        return str(value)
    def to_internal_value(self, data):
        return ObjectId(data)

from .models import HMSMI
class HMSMISerializer(serializers.ModelSerializer):
    class Meta:
        model = HMSMI
        fields = '__all__'

from .models import TestResult
class TestResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = TestResult
        fields = '__all__'
