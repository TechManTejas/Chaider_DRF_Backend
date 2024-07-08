from rest_framework import serializers
from .models import CSVFile, CSVFileVariable
from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username','email','password']
        # extra_kwargs = {'password': {'write_only': True, 'required': True}}

    def create(self, validated_data):
        user = User.objects.create_user(**validated_data)
        Token.objects.create(user=user)
        return user

class CSVFileSerializer(serializers.ModelSerializer):
    class Meta:
        model = CSVFile
        fields = ['id', 'userid', 'name', 'description', 'file']

class CSVFileVariableSerializer(serializers.ModelSerializer):
    class Meta:
        model = CSVFileVariable
        fields = ['id', 'preview', 'userid', 'name', 'description', 'filename', 'variables', 'filters', 'instances', 'stageData']
