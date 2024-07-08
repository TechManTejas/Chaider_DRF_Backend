from api.serializers import CSVFileVariable
from api.serializers import CSVFileVariableSerializer
from rest_framework import viewsets
import io
from django.views.decorators.csrf import csrf_exempt
from rest_framework.response import Response
from rest_framework.parsers import JSONParser
import pandas as pd
from collections import OrderedDict
# Create your views here.


class GraphDataModelViewset(viewsets.ModelViewSet):
    queryset = CSVFileVariable.objects.all()
    serializer_class = CSVFileVariableSerializer

    @csrf_exempt
    def create(self, request, *args, **kwargs):
        json_data = request.body
        stream = io.BytesIO(json_data)
        pythonData = JSONParser().parse(stream)
        
        csvid = pythonData["csvid"]
        variable = pythonData["variable"]

        instance = CSVFileVariable.objects.get(id=csvid)
        serializer = CSVFileVariableSerializer(instance)
        filename = serializer.data["filename"]

        df = pd.read_csv('media/api/csv_file_uploaded/'+filename)
        uniqueVal_Count = dict(df[str(variable)].value_counts())
        
        uniqueVal_Count_sorted = sorted(uniqueVal_Count.keys())
        new_uniqueVal_Count = {}
        for key in uniqueVal_Count_sorted:
            new_uniqueVal_Count[key] = uniqueVal_Count[key]
                        
        return Response(new_uniqueVal_Count)

