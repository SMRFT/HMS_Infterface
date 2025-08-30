from rest_framework import serializers
from bson import ObjectId

class ObjectIdField(serializers.Field):
    def to_representation(self, value):
        return str(value)
    def to_internal_value(self, data):
        return ObjectId(data)


from rest_framework import serializers
from .models import HMSMI

class HMSMISerializer(serializers.ModelSerializer):
    id = serializers.CharField(read_only=True)  # Override the ObjectId field
    class Meta:
        model = HMSMI
        fields = '__all__'



from rest_framework import serializers
from .models import TestResult

class TestResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = HMSMI
        fields = '__all__'
