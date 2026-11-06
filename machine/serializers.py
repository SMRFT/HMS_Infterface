from rest_framework import serializers
from bson import ObjectId
from .models import HMSMI, TestResult

class ObjectIdField(serializers.Field):
    def to_representation(self, value):
        if value is None:
            return None
        return str(value)

    def to_internal_value(self, data):
        if not data:
            return None
        if isinstance(data, ObjectId):
            return data
        try:
            return ObjectId(str(data))
        except Exception:
            raise serializers.ValidationError("Invalid ObjectId")

class HMSMISerializer(serializers.ModelSerializer):
    id = ObjectIdField(read_only=True, required=False)

    class Meta:
        model = HMSMI
        fields = '__all__'

class TestResultSerializer(serializers.ModelSerializer):
    id = ObjectIdField(read_only=True, required=False)

    class Meta:
        model = TestResult
        fields = '__all__'
