import io
import ast
from statistics import stdev
from django.shortcuts import render
from .models import CSVFile, CSVFileVariable
from .serializers import CSVFileSerializer, CSVFileVariableSerializer, UserSerializer
from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.parsers import JSONParser
import pandas as pd
import numpy as np
from pandas.api.types import is_numeric_dtype
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.models import User
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny
from operator import itemgetter
import random
import logging
from .iv_calculator import *

logger = logging.getLogger('django')
# def index(request):
#     return render(request, "index.html")

# Create your views here.
class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    authentication_classes = []
    permission_classes = [AllowAny]


class CustomObtainAuthToken(ObtainAuthToken):
    def post(self, request, *args, **kwargs):
        response = super(CustomObtainAuthToken, self).post(
            request, *args, **kwargs)
        token = Token.objects.get(key=response.data['token'])
        return Response({'token': token.key, 'id': token.user_id})


class CSVFileModelViewset(viewsets.ModelViewSet):
    queryset = CSVFile.objects.all()
    serializer_class = CSVFileSerializer

    def get_queryset(self):
        return CSVFile.objects.filter(userid=self.request.user.id)

    @csrf_exempt
    def create(self, request, *args, **kwargs):
        serializer = CSVFileSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()

            jsonData = getColumns(str(serializer.data['file'][1:]))
            jsonData['userid'] = serializer.data['userid']
            jsonData['name'] = serializer.data['name']
            jsonData['description'] = serializer.data['description']
            jsonData['filters'] = {
                "Main":{
                    "variables":{}
                }
            }
            jsonData['instances'] = {"names":["Main"]}
            jsonData['stageData'] = {"Main":{}}

            varSerializer = CSVFileVariableSerializer(data=jsonData)
            if varSerializer.is_valid():
                varSerializer.save()
                
                jsonData['id'] = varSerializer.data['id']

                return Response(jsonData)

            return Response(varSerializer.errors)

        return Response(serializer.errors)


class CSVFileVariableModelViewset(viewsets.ModelViewSet):
    queryset = CSVFileVariable.objects.all()
    serializer_class = CSVFileVariableSerializer

    def get_queryset(self):
        return CSVFileVariable.objects.filter(userid=self.request.user.id)

    @csrf_exempt
    def post(self, request, *args, **kwargs):
        json_data = request.body
        stream = io.BytesIO(json_data)
        pythonData = JSONParser().parse(stream)

        if "firstsplit" in pythonData["data"]:
            data = selectYvar(pythonData)
            return data

        operation = pythonData["data"]["operation"]

        if operation == "forcesplit":
            data = forceSplit(pythonData)
        elif operation == "findsplit":
            data = findSplit(pythonData)
        elif operation == "nextsplit":
            data = nextSplit(pythonData)
        elif operation == "prevsplit":
            data = prevSplit(pythonData)
        elif operation == "treegrow":
            data = treeGrow(pythonData)
        elif operation == "deletesubnodes":
            data = deleteSubnodes(pythonData)
        else:
            data = {"error": "Unknown operation"}

        return data


def selectYvar(pythonData):
    var = pythonData["data"]["yVar"]
    csvid = pythonData["data"]["csvid"]
    instance = CSVFileVariable.objects.get(id=csvid)
    serializer = CSVFileVariableSerializer(instance)
    filename = serializer.data["filename"]
    df = pd.read_csv('media/api/csv_file_uploaded/'+filename)

    uniqueVal_Count = dict(df[var].value_counts())
    total = sum([uniqueVal_Count[key] for key in uniqueVal_Count])

    return Response(
        {
            "nodeType": "VALUE",
            "nodeName": str(var),
            "nodeCategory": str(var),
            "total": total,
            "nodeContent": uniqueVal_Count,
            "nodeData": str(var)
        }
    )


def forceSplit(pythonData):
    yVar = pythonData["data"]["yVar"]
    csvid = pythonData["data"]["csvid"]
    xVariables = pythonData["data"]["xVariablesTillNode"]
    varsTillCurrentNode = pythonData["data"]["varsTillNode"]
    nodeTypesTillNode = pythonData["data"]["nodeTypesTillNode"]
    nodeDataTillNode = pythonData["data"]["nodeDataTillNode"]

    print(xVariables)
    print(varsTillCurrentNode)
    print(nodeTypesTillNode)
    print(nodeDataTillNode)

    for var in varsTillCurrentNode:
        try:
            varsTillCurrentNode[varsTillCurrentNode.index(var)] = float(var)
        except ValueError:
            pass

    instance = CSVFileVariable.objects.get(id=csvid)
    serializer = CSVFileVariableSerializer(instance)
    filename = serializer.data["filename"]

    df = pd.read_csv('media/api/csv_file_uploaded/'+filename)
    filtereddf = []
    filtereddf.extend(xVariables)
    filtereddf.append(yVar)
    df = df[list(set(filtereddf))]

    yVarUniqueElement = [y for y in list(df[yVar].unique()) if str(y) != 'nan']
    xVar = xVariables[-1]
    responseToReturn = []

    # GET DESIRED DATA SET
    # ['3.0', 'female', 'names'] varsTillNode
    # ['pclass', 'sex', 'name'] xVariablesTillNode
    # ['VALUE', 'VALUE', 'PACKED'] nodeTypesTillNode
    # ['3.0', 'female', Array(105)] nodeDataTillNode

    print(df)
    for i in range(len(xVariables)-1):
        if nodeTypesTillNode[i] == "VALUE":
            df = df[(df[xVariables[i]] == varsTillCurrentNode[i])]
        elif nodeTypesTillNode[i] == "PACKED":
            df = df[df[xVariables[i]].isin(nodeDataTillNode[i])]
        elif nodeTypesTillNode[i] == "RANGED":
            df = df[df[xVariables[i]] > nodeDataTillNode[i][0]]
            df = df[df[xVariables[i]] <= nodeDataTillNode[i][1]]
    print(df)

    # AFTER WE HAVE DATASET
    caridinality = len(pd.unique(df[xVar]))
    if ((caridinality > 10) and (is_numeric_dtype(df[xVar]))):

        df[xVar] = df[xVar].astype(float)
        # CONTINUOUS VARIABLE
        df = df[[xVar, yVar]]

        iv, woe = iv_woe(
            data=df, target=yVar, yVarUniqueElement=yVarUniqueElement, bins=10, show_woe=False)
        variable = list(dict(woe)['Variable'])
        bins = list(dict(woe)['Cutoff'])
        total = list(dict(woe)['N'])
        events = list(dict(woe)['Events'])
        non_events = list(dict(woe)['Non-Events'])

        yVarValue = [val for val in yVarUniqueElement]

        for v in range(len(bins)):
            nodeName = str(bins[v])
            Data = []
            if nodeName == 'nan':
                Data = ['nan']
            elif "," in nodeName:
                Data = [
                    float(nodeName[1:nodeName.index(',')]),
                    float(nodeName[nodeName.index(',')+2:nodeName.index(']')])
                ]
            else:
                Data = nodeName

            if variable[v] == xVar:
                nodeData = {
                    "nodeType": "RANGED" if not (Data == nodeName) else "VALUE",
                    "nodeName": nodeName,
                    "nodeCategory": xVar,
                    "total": total[v],
                    "nodeContent": {str(yVarValue[0]): events[v], str(yVarValue[1]): non_events[v]},
                    "nodeData": Data
                }
                responseToReturn.append(nodeData)

    else:
        # CATEGORICAL VARIABLE
        uniqueVal_Count = dict(df[str(xVar)].value_counts())
        for nodeName in uniqueVal_Count:
            nodeData = {
                "nodeType": "VALUE",
                "nodeName": str(nodeName),
                "nodeCategory": xVar,
                "total": uniqueVal_Count[nodeName],
                "nodeContent": {},
                "nodeData": str(nodeName)
            }
            for val in yVarUniqueElement:
                tempdf = df[(df[xVar] == nodeName) & (df[yVar] == val)]
                nodeData["nodeContent"][str(val)] = tempdf[yVar].count()
            responseToReturn.append(nodeData)

        # CLUB SIMILAR NODES AND MAKE A PACKED NODE
        totals_per_node = [node['total'] for node in responseToReturn]
        standardDeviationOrCustomThreshold = stdev(totals_per_node) if len(totals_per_node) > 1 else sum(totals_per_node)/100
        newResponseToReturn = []
        packedNode = {
            "nodeType": "",
            'nodeName': '',
            'nodeCategory': '',
            'total': 0,
            'nodeContent': {},
            "nodeData": []
        }

        print(responseToReturn[0]['nodeContent'])

        for key in dict(responseToReturn[0]['nodeContent']):
            packedNode['nodeContent'][key] = 0

        binAsPacked = 0
        if (len(xVariables)==1):
            binAsPacked = 1
        elif(standardDeviationOrCustomThreshold == 0.0) and (xVariables[-1] != xVariables[-2]):
            binAsPacked = 1
        elif(standardDeviationOrCustomThreshold > 0.0):
            binAsPacked = 1
        # elif(xVariables[-1] != xVariables[-2]):
        #     binAsPacked = 1
        # elif(xVariables[-1] == xVariables[-2]) and (nodeTypesTillNode[-1] != "PACKED"):
        #     binAsPacked = 1

        print(responseToReturn)

        i = 0
        if(binAsPacked):
            while(i<len(responseToReturn)):
                if ((responseToReturn[i]["total"] <= standardDeviationOrCustomThreshold) or standardDeviationOrCustomThreshold == 0.0):
                    packedNode['nodeData'].append(responseToReturn[i]['nodeName'])
                    packedNode['nodeCategory'] = responseToReturn[i]['nodeCategory']
                    packedNode['total'] += responseToReturn[i]['total']
                    for key in responseToReturn[i]["nodeContent"]:
                        packedNode['nodeContent'][key] += responseToReturn[i]["nodeContent"][key]
                    del(responseToReturn[responseToReturn.index(responseToReturn[i])])
                    i-=1
                i+=1

        print(packedNode)

        packedNode['nodeData'].sort()
        for val in packedNode['nodeData']:
            try:
                packedNode['nodeData'][packedNode['nodeData'].index(val)] = float(val)
            except ValueError:
                pass

        if(len(packedNode['nodeData']) > 1):
            packedNode['nodeName'] = packedNode['nodeCategory']+"s"
            packedNode['nodeType'] = "PACKED"
        elif packedNode['total']:
            packedNode['nodeName'] = str(packedNode['nodeData'][0])
            packedNode['nodeData'] = str(packedNode['nodeData'][0])
            packedNode['nodeType'] = "VALUE"

        newResponseToReturn.extend(responseToReturn)
        if packedNode['total']:
            newResponseToReturn.append(packedNode)
        responseToReturn = newResponseToReturn

    responseToReturn = sorted(responseToReturn, key=itemgetter('nodeName'))
    data = {
        "nodes": responseToReturn,
        "values": {
            "pValue": round(random.uniform(0, 10), 3),
            "zScore": round(random.uniform(0, 10), 3),
            "chiSquare": round(random.uniform(0, 10), 3),
            "rSquare": round(random.uniform(0, 10), 3),
            "adjRSquare": round(random.uniform(0, 10), 3),
            "gini": round(random.uniform(0, 10), 3),
        }}
    return Response(data)


def findSplit(pythonData):
    yVar = pythonData["data"]["yVar"]
    csvid = pythonData["data"]["csvid"]
    xVariables = pythonData["data"]["xVariablesTillNode"]
    varsTillCurrentNode = pythonData["data"]["varsTillNode"]
    nodeTypesTillNode = pythonData["data"]["nodeTypesTillNode"]
    nodeDataTillNode = pythonData["data"]["nodeDataTillNode"]
    
    # for var in varsTillCurrentNode:
    #     try:
    #         varsTillCurrentNode[varsTillCurrentNode.index(var)] = float(var)
    #     except ValueError:
    #         pass

    print(xVariables)
    print(varsTillCurrentNode)
    print(nodeTypesTillNode)
    print(nodeDataTillNode)

    instance = CSVFileVariable.objects.get(id=csvid)
    serializer = CSVFileVariableSerializer(instance)
    filename = serializer.data["filename"]

    df = pd.read_csv('media/api/csv_file_uploaded/'+filename)
    print(df)
    for i in range(len(xVariables)):
        if nodeTypesTillNode[i] == "VALUE":
            df = df[(df[xVariables[i]] == varsTillCurrentNode[i])]
        elif nodeTypesTillNode[i] == "PACKED":
            df = df[df[xVariables[i]].isin(nodeDataTillNode[i])]
        elif nodeTypesTillNode[i] == "RANGED":
            df = df[df[xVariables[i]] > nodeDataTillNode[i][0]]
            df = df[df[xVariables[i]] <= nodeDataTillNode[i][1]]
    print(df)
            
    list_of_column_names_cardinalities = dict(df.apply(pd.Series.nunique))

    yVarUniqueElement = [y for y in list(df[yVar].unique()) if str(y) != 'nan']
    # xVar = xVariables[-1]
    responseToReturn = []

    filtereddf = []
    filtereddf.extend(xVariables)
    new_df_cold = []
    for key, val in list_of_column_names_cardinalities.items():
        if key not in filtereddf:
            new_df_cold.append(key)

    df = df[list(set(new_df_cold))]
    # print(new_df_cold)
    
    vars = []
    final_iv, IV = data_vars(df, df[yVar])
    IV = IV.sort_values('IV')
    for var in IV['VAR_NAME']:
        vars.append(var)
    
    xVar = vars[-1]

    responseToReturn = []
    # AFTER WE HAVE DATASET
    caridinality = len(pd.unique(df[xVar]))
    if ((caridinality > 10) and (is_numeric_dtype(df[xVar]))):

        df[xVar] = df[xVar].astype(float)
        # CONTINUOUS VARIABLE
        df = df[[xVar, yVar]]

        iv, woe = iv_woe(
            data=df, target=yVar, yVarUniqueElement=yVarUniqueElement, bins=10, show_woe=False)
        variable = list(dict(woe)['Variable'])
        bins = list(dict(woe)['Cutoff'])
        total = list(dict(woe)['N'])
        events = list(dict(woe)['Events'])
        non_events = list(dict(woe)['Non-Events'])

        yVarValue = [val for val in yVarUniqueElement]

        for v in range(len(bins)):
            nodeName = str(bins[v])
            Data = []
            if nodeName == 'nan':
                Data = ['nan']
            elif "," in nodeName:
                Data = [
                    float(nodeName[1:nodeName.index(',')]),
                    float(nodeName[nodeName.index(',')+2:nodeName.index(']')])
                ]
            else:
                Data = nodeName

            if variable[v] == xVar:
                nodeData = {
                    "nodeType": "RANGED" if not (Data == nodeName) else "VALUE",
                    "nodeName": nodeName,
                    "nodeCategory": xVar,
                    "total": total[v],
                    "nodeContent": {str(yVarValue[0]): events[v], str(yVarValue[1]): non_events[v]},
                    "nodeData": Data
                }
                responseToReturn.append(nodeData)

    else:
        # CATEGORICAL VARIABLE
        uniqueVal_Count = dict(df[str(xVar)].value_counts())
        for nodeName in uniqueVal_Count:
            nodeData = {
                "nodeType": "VALUE",
                "nodeName": str(nodeName),
                "nodeCategory": xVar,
                "total": uniqueVal_Count[nodeName],
                "nodeContent": {},
                "nodeData": str(nodeName)
            }
            for val in yVarUniqueElement:
                tempdf = df[(df[xVar] == nodeName) & (df[yVar] == val)]
                nodeData["nodeContent"][str(val)] = tempdf[yVar].count()
            responseToReturn.append(nodeData)

        # CLUB SIMILAR NODES AND MAKE A PACKED NODE
        totals_per_node = [node['total'] for node in responseToReturn]
        standardDeviationOrCustomThreshold = stdev(totals_per_node) if len(
            totals_per_node) > 1 else sum(totals_per_node)/100
        newResponseToReturn = []
        packedNode = {
            "nodeType": "",
            'nodeName': '',
            'nodeCategory': '',
            'total': 0,
            'nodeContent': {},
            "nodeData": []
        }

        for key in dict(ast.literal_eval(str(responseToReturn[0]['nodeContent']))):
            packedNode['nodeContent'][key] = 0

        binAsPacked = 0
        if (len(xVariables) == 1):
            binAsPacked = 1
        elif(standardDeviationOrCustomThreshold == 0.0) and (xVariables[-1] != xVariables[-2]):
            binAsPacked = 1
        elif(standardDeviationOrCustomThreshold > 0.0):
            binAsPacked = 1
        # elif(xVariables[-1] != xVariables[-2]):
        #     binAsPacked = 1
        # elif(xVariables[-1] == xVariables[-2]) and (nodeTypesTillNode[-1] != "PACKED"):
        #     binAsPacked = 1

        print(responseToReturn)

        i = 0
        if(binAsPacked):
            while(i < len(responseToReturn)):
                if ((responseToReturn[i]["total"] <= standardDeviationOrCustomThreshold) or standardDeviationOrCustomThreshold == 0.0):
                    packedNode['nodeData'].append(
                        responseToReturn[i]['nodeName'])
                    packedNode['nodeCategory'] = responseToReturn[i]['nodeCategory']
                    packedNode['total'] += responseToReturn[i]['total']
                    for key in responseToReturn[i]["nodeContent"]:
                        packedNode['nodeContent'][key] += responseToReturn[i]["nodeContent"][key]
                    del(responseToReturn[responseToReturn.index(
                        responseToReturn[i])])
                    i -= 1
                i += 1

        print(packedNode)

        packedNode['nodeData'].sort()
        for val in packedNode['nodeData']:
            try:
                packedNode['nodeData'][packedNode['nodeData'].index(
                    val)] = float(val)
            except ValueError:
                pass

        if(len(packedNode['nodeData']) > 1):
            packedNode['nodeName'] = packedNode['nodeCategory']+"s"
            packedNode['nodeType'] = "PACKED"
        elif packedNode['total']:
            packedNode['nodeName'] = str(packedNode['nodeData'][0])
            packedNode['nodeData'] = str(packedNode['nodeData'][0])
            packedNode['nodeType'] = "VALUE"

        newResponseToReturn.extend(responseToReturn)
        if packedNode['total']:
            newResponseToReturn.append(packedNode)
        responseToReturn = newResponseToReturn

    responseToReturn = sorted(responseToReturn, key=itemgetter('nodeName'))
    data = {
        "nodes": responseToReturn,
        "values": {
            "pValue": round(random.uniform(0, 10), 3),
            "zScore": round(random.uniform(0, 10), 3),
            "chiSquare": round(random.uniform(0, 10), 3),
            "rSquare": round(random.uniform(0, 10), 3),
            "adjRSquare": round(random.uniform(0, 10), 3),
            "gini": round(random.uniform(0, 10), 3),
        }}
    return Response(data)


def nextSplit(pythonData):
    yVar = pythonData["data"]["yVar"]
    csvid = pythonData["data"]["csvid"]
    xVariables = pythonData["data"]["xVariablesTillNode"]
    varsTillCurrentNode = pythonData["data"]["varsTillNode"]
    nodeTypesTillNode = pythonData["data"]["nodeTypesTillNode"]
    nodeDataTillNode = pythonData["data"]["nodeDataTillNode"]
    childrenCategory = pythonData["data"]["childrenCategory"]

    # for var in varsTillCurrentNode:
    #     try:
    #         varsTillCurrentNode[varsTillCurrentNode.index(var)] = float(var)
    #     except ValueError:
    #         pass

    print(xVariables)
    print(varsTillCurrentNode)
    print(nodeTypesTillNode)
    print(nodeDataTillNode)

    instance = CSVFileVariable.objects.get(id=csvid)
    serializer = CSVFileVariableSerializer(instance)
    filename = serializer.data["filename"]

    df = pd.read_csv('media/api/csv_file_uploaded/'+filename)
    print(df)
    print("NEXT")
    for i in range(len(xVariables)):
        if nodeTypesTillNode[i] == "VALUE":
            df = df[(df[xVariables[i]] == varsTillCurrentNode[i])]
        elif nodeTypesTillNode[i] == "PACKED":
            df = df[df[xVariables[i]].isin(nodeDataTillNode[i])]
        elif nodeTypesTillNode[i] == "RANGED":
            df = df[df[xVariables[i]] > nodeDataTillNode[i][0]]
            df = df[df[xVariables[i]] <= nodeDataTillNode[i][1]]
    print(df)

    list_of_column_names_cardinalities = dict(df.apply(pd.Series.nunique))

    yVarUniqueElement = [y for y in list(df[yVar].unique()) if str(y) != 'nan']
    # xVar = xVariables[-1]
    responseToReturn = []

    filtereddf = []
    filtereddf.extend(xVariables)
    new_df_cold = []
    for key, val in list_of_column_names_cardinalities.items():
        if key not in filtereddf:
            new_df_cold.append(key)

    df = df[list(set(new_df_cold))]
    # print(new_df_cold)

    vars = []
    final_iv, IV = data_vars(df, df[yVar])
    IV = IV.sort_values('IV')
    for var in IV['VAR_NAME']:
        vars.append(var)

    xVar = vars[-1]
    while(xVar != childrenCategory):
        xVar = vars[vars.index(xVar)-1]
    xVar = vars[vars.index(xVar)-1]
    print(xVar)

    responseToReturn = []
    # AFTER WE HAVE DATASET
    caridinality = len(pd.unique(df[xVar]))
    if ((caridinality > 10) and (is_numeric_dtype(df[xVar]))):

        df[xVar] = df[xVar].astype(float)
        # CONTINUOUS VARIABLE
        df = df[[xVar, yVar]]

        iv, woe = iv_woe(
            data=df, target=yVar, yVarUniqueElement=yVarUniqueElement, bins=10, show_woe=False)
        variable = list(dict(woe)['Variable'])
        bins = list(dict(woe)['Cutoff'])
        total = list(dict(woe)['N'])
        events = list(dict(woe)['Events'])
        non_events = list(dict(woe)['Non-Events'])

        yVarValue = [val for val in yVarUniqueElement]

        for v in range(len(bins)):
            nodeName = str(bins[v])
            Data = []
            if nodeName == 'nan':
                Data = ['nan']
            elif "," in nodeName:
                Data = [
                    float(nodeName[1:nodeName.index(',')]),
                    float(nodeName[nodeName.index(',')+2:nodeName.index(']')])
                ]
            else:
                Data = nodeName

            if variable[v] == xVar:
                nodeData = {
                    "nodeType": "RANGED" if not (Data == nodeName) else "VALUE",
                    "nodeName": nodeName,
                    "nodeCategory": xVar,
                    "total": total[v],
                    "nodeContent": {str(yVarValue[0]): events[v], str(yVarValue[1]): non_events[v]},
                    "nodeData": Data
                }
                responseToReturn.append(nodeData)

    else:
        # CATEGORICAL VARIABLE
        uniqueVal_Count = dict(df[str(xVar)].value_counts())
        for nodeName in uniqueVal_Count:
            nodeData = {
                "nodeType": "VALUE",
                "nodeName": str(nodeName),
                "nodeCategory": xVar,
                "total": uniqueVal_Count[nodeName],
                "nodeContent": {},
                "nodeData": str(nodeName)
            }
            for val in yVarUniqueElement:
                tempdf = df[(df[xVar] == nodeName) & (df[yVar] == val)]
                nodeData["nodeContent"][str(val)] = tempdf[yVar].count()
            responseToReturn.append(nodeData)

        # CLUB SIMILAR NODES AND MAKE A PACKED NODE
        totals_per_node = [node['total'] for node in responseToReturn]
        standardDeviationOrCustomThreshold = stdev(totals_per_node) if len(
            totals_per_node) > 1 else sum(totals_per_node)/100
        newResponseToReturn = []
        packedNode = {
            "nodeType": "",
            'nodeName': '',
            'nodeCategory': '',
            'total': 0,
            'nodeContent': {},
            "nodeData": []
        }

        for key in dict(ast.literal_eval(str(responseToReturn[0]['nodeContent']))):
            packedNode['nodeContent'][key] = 0

        binAsPacked = 0
        if (len(xVariables) == 1):
            binAsPacked = 1
        elif(standardDeviationOrCustomThreshold == 0.0) and (xVariables[-1] != xVariables[-2]):
            binAsPacked = 1
        elif(standardDeviationOrCustomThreshold > 0.0):
            binAsPacked = 1
        # elif(xVariables[-1] != xVariables[-2]):
        #     binAsPacked = 1
        # elif(xVariables[-1] == xVariables[-2]) and (nodeTypesTillNode[-1] != "PACKED"):
        #     binAsPacked = 1

        print(responseToReturn)

        i = 0
        if(binAsPacked):
            while(i < len(responseToReturn)):
                if ((responseToReturn[i]["total"] <= standardDeviationOrCustomThreshold) or standardDeviationOrCustomThreshold == 0.0):
                    packedNode['nodeData'].append(
                        responseToReturn[i]['nodeName'])
                    packedNode['nodeCategory'] = responseToReturn[i]['nodeCategory']
                    packedNode['total'] += responseToReturn[i]['total']
                    for key in responseToReturn[i]["nodeContent"]:
                        packedNode['nodeContent'][key] += responseToReturn[i]["nodeContent"][key]
                    del(responseToReturn[responseToReturn.index(
                        responseToReturn[i])])
                    i -= 1
                i += 1

        print(packedNode)

        packedNode['nodeData'].sort()
        for val in packedNode['nodeData']:
            try:
                packedNode['nodeData'][packedNode['nodeData'].index(
                    val)] = float(val)
            except ValueError:
                pass

        if(len(packedNode['nodeData']) > 1):
            packedNode['nodeName'] = packedNode['nodeCategory']+"s"
            packedNode['nodeType'] = "PACKED"
        elif packedNode['total']:
            packedNode['nodeName'] = str(packedNode['nodeData'][0])
            packedNode['nodeData'] = str(packedNode['nodeData'][0])
            packedNode['nodeType'] = "VALUE"

        newResponseToReturn.extend(responseToReturn)
        if packedNode['total']:
            newResponseToReturn.append(packedNode)
        responseToReturn = newResponseToReturn

    responseToReturn = sorted(responseToReturn, key=itemgetter('nodeName'))
    data = {
        "nodes": responseToReturn,
        "values": {
            "pValue": round(random.uniform(0, 10), 3),
            "zScore": round(random.uniform(0, 10), 3),
            "chiSquare": round(random.uniform(0, 10), 3),
            "rSquare": round(random.uniform(0, 10), 3),
            "adjRSquare": round(random.uniform(0, 10), 3),
            "gini": round(random.uniform(0, 10), 3),
        }}
    return Response(data)


def prevSplit(pythonData):
    yVar = pythonData["data"]["yVar"]
    csvid = pythonData["data"]["csvid"]
    xVariables = pythonData["data"]["xVariablesTillNode"]
    varsTillCurrentNode = pythonData["data"]["varsTillNode"]
    nodeTypesTillNode = pythonData["data"]["nodeTypesTillNode"]
    nodeDataTillNode = pythonData["data"]["nodeDataTillNode"]
    childrenCategory = pythonData["data"]["childrenCategory"]

    # for var in varsTillCurrentNode:
    #     try:
    #         varsTillCurrentNode[varsTillCurrentNode.index(var)] = float(var)
    #     except ValueError:
    #         pass

    print(xVariables)
    print(varsTillCurrentNode)
    print(nodeTypesTillNode)
    print(nodeDataTillNode)

    instance = CSVFileVariable.objects.get(id=csvid)
    serializer = CSVFileVariableSerializer(instance)
    filename = serializer.data["filename"]

    df = pd.read_csv('media/api/csv_file_uploaded/'+filename)
    print(df)
    print("NEXT")
    for i in range(len(xVariables)):
        if nodeTypesTillNode[i] == "VALUE":
            df = df[(df[xVariables[i]] == varsTillCurrentNode[i])]
        elif nodeTypesTillNode[i] == "PACKED":
            df = df[df[xVariables[i]].isin(nodeDataTillNode[i])]
        elif nodeTypesTillNode[i] == "RANGED":
            df = df[df[xVariables[i]] > nodeDataTillNode[i][0]]
            df = df[df[xVariables[i]] <= nodeDataTillNode[i][1]]
    print(df)

    list_of_column_names_cardinalities = dict(df.apply(pd.Series.nunique))

    yVarUniqueElement = [y for y in list(df[yVar].unique()) if str(y) != 'nan']
    # xVar = xVariables[-1]
    responseToReturn = []

    filtereddf = []
    filtereddf.extend(xVariables)
    new_df_cold = []
    for key, val in list_of_column_names_cardinalities.items():
        if key not in filtereddf:
            new_df_cold.append(key)

    df = df[list(set(new_df_cold))]
    # print(new_df_cold)

    vars = []
    final_iv, IV = data_vars(df, df[yVar])
    IV = IV.sort_values('IV')
    for var in IV['VAR_NAME']:
        vars.append(var)

    xVar = vars[-1]
    while(xVar != childrenCategory):
        xVar = vars[vars.index(xVar)-1]
    xVar = vars[vars.index(xVar)+1]
    print(xVar)

    responseToReturn = []
    # AFTER WE HAVE DATASET
    caridinality = len(pd.unique(df[xVar]))
    if ((caridinality > 10) and (is_numeric_dtype(df[xVar]))):

        df[xVar] = df[xVar].astype(float)
        # CONTINUOUS VARIABLE
        df = df[[xVar, yVar]]

        iv, woe = iv_woe(
            data=df, target=yVar, yVarUniqueElement=yVarUniqueElement, bins=10, show_woe=False)
        variable = list(dict(woe)['Variable'])
        bins = list(dict(woe)['Cutoff'])
        total = list(dict(woe)['N'])
        events = list(dict(woe)['Events'])
        non_events = list(dict(woe)['Non-Events'])

        yVarValue = [val for val in yVarUniqueElement]

        for v in range(len(bins)):
            nodeName = str(bins[v])
            Data = []
            if nodeName == 'nan':
                Data = ['nan']
            elif "," in nodeName:
                Data = [
                    float(nodeName[1:nodeName.index(',')]),
                    float(nodeName[nodeName.index(',')+2:nodeName.index(']')])
                ]
            else:
                Data = nodeName

            if variable[v] == xVar:
                nodeData = {
                    "nodeType": "RANGED" if not (Data == nodeName) else "VALUE",
                    "nodeName": nodeName,
                    "nodeCategory": xVar,
                    "total": total[v],
                    "nodeContent": {str(yVarValue[0]): events[v], str(yVarValue[1]): non_events[v]},
                    "nodeData": Data
                }
                responseToReturn.append(nodeData)

    else:
        # CATEGORICAL VARIABLE
        uniqueVal_Count = dict(df[str(xVar)].value_counts())
        for nodeName in uniqueVal_Count:
            nodeData = {
                "nodeType": "VALUE",
                "nodeName": str(nodeName),
                "nodeCategory": xVar,
                "total": uniqueVal_Count[nodeName],
                "nodeContent": {},
                "nodeData": str(nodeName)
            }
            for val in yVarUniqueElement:
                tempdf = df[(df[xVar] == nodeName) & (df[yVar] == val)]
                nodeData["nodeContent"][str(val)] = tempdf[yVar].count()
            responseToReturn.append(nodeData)

        # CLUB SIMILAR NODES AND MAKE A PACKED NODE
        totals_per_node = [node['total'] for node in responseToReturn]
        standardDeviationOrCustomThreshold = stdev(totals_per_node) if len(
            totals_per_node) > 1 else sum(totals_per_node)/100
        newResponseToReturn = []
        packedNode = {
            "nodeType": "",
            'nodeName': '',
            'nodeCategory': '',
            'total': 0,
            'nodeContent': {},
            "nodeData": []
        }

        for key in dict(ast.literal_eval(str(responseToReturn[0]['nodeContent']))):
            packedNode['nodeContent'][key] = 0

        binAsPacked = 0
        if (len(xVariables) == 1):
            binAsPacked = 1
        elif(standardDeviationOrCustomThreshold == 0.0) and (xVariables[-1] != xVariables[-2]):
            binAsPacked = 1
        elif(standardDeviationOrCustomThreshold > 0.0):
            binAsPacked = 1
        # elif(xVariables[-1] != xVariables[-2]):
        #     binAsPacked = 1
        # elif(xVariables[-1] == xVariables[-2]) and (nodeTypesTillNode[-1] != "PACKED"):
        #     binAsPacked = 1

        print(responseToReturn)

        i = 0
        if(binAsPacked):
            while(i < len(responseToReturn)):
                if ((responseToReturn[i]["total"] <= standardDeviationOrCustomThreshold) or standardDeviationOrCustomThreshold == 0.0):
                    packedNode['nodeData'].append(
                        responseToReturn[i]['nodeName'])
                    packedNode['nodeCategory'] = responseToReturn[i]['nodeCategory']
                    packedNode['total'] += responseToReturn[i]['total']
                    for key in responseToReturn[i]["nodeContent"]:
                        packedNode['nodeContent'][key] += responseToReturn[i]["nodeContent"][key]
                    del(responseToReturn[responseToReturn.index(
                        responseToReturn[i])])
                    i -= 1
                i += 1

        print(packedNode)

        packedNode['nodeData'].sort()
        for val in packedNode['nodeData']:
            try:
                packedNode['nodeData'][packedNode['nodeData'].index(
                    val)] = float(val)
            except ValueError:
                pass

        if(len(packedNode['nodeData']) > 1):
            packedNode['nodeName'] = packedNode['nodeCategory']+"s"
            packedNode['nodeType'] = "PACKED"
        elif packedNode['total']:
            packedNode['nodeName'] = str(packedNode['nodeData'][0])
            packedNode['nodeData'] = str(packedNode['nodeData'][0])
            packedNode['nodeType'] = "VALUE"

        newResponseToReturn.extend(responseToReturn)
        if packedNode['total']:
            newResponseToReturn.append(packedNode)
        responseToReturn = newResponseToReturn

    responseToReturn = sorted(responseToReturn, key=itemgetter('nodeName'))
    data = {
        "nodes": responseToReturn,
        "values": {
            "pValue": round(random.uniform(0, 10), 3),
            "zScore": round(random.uniform(0, 10), 3),
            "chiSquare": round(random.uniform(0, 10), 3),
            "rSquare": round(random.uniform(0, 10), 3),
            "adjRSquare": round(random.uniform(0, 10), 3),
            "gini": round(random.uniform(0, 10), 3),
        }}
    return Response(data)

def treeGrow(pythonData):
    return Response(pythonData)


def deleteSubnodes(pythonData):
    return Response(pythonData)


def getColumns(filename):
    df = pd.read_csv(filename)
    list_of_column_names_cardinalities = dict(df.apply(pd.Series.nunique))

    for key in list_of_column_names_cardinalities:
        list_of_column_names_cardinalities[key] = int(
            list_of_column_names_cardinalities[key])

    data = {"filename": filename.split('/')[-1],
            "variables": list_of_column_names_cardinalities}
    return data


def iv_woe(data, target, yVarUniqueElement, bins=10, show_woe=False):
    # Empty Dataframe
    newDF, woeDF = pd.DataFrame(), pd.DataFrame()

    # Extract Column Names
    cols = data.columns

    # Run WOE and IV on all the independent variables
    for ivars in cols[~cols.isin([target])]:
        if (data[ivars].dtype.kind in 'bifc') and (len(np.unique(data[ivars])) > 10):
            binned_x = pd.qcut(data[ivars], bins,  duplicates='drop')
            d0 = pd.DataFrame({'x': binned_x, 'y': data[target]})
        else:
            d0 = pd.DataFrame({'x': data[ivars], 'y': data[target]})

        d0 = d0.astype({"x": str})
        d = d0.groupby("x", as_index=False, dropna=False).agg(
            {"y": ["count", "sum"]})
        d.columns = ['Cutoff', 'N', 'Events']
        d['% of Events'] = np.maximum(d['Events'], 0.5) / d['Events'].sum()
        d['Non-Events'] = d['N'] - d['Events']
        d['% of Non-Events'] = np.maximum(d['Non-Events'],0.5) / d['Non-Events'].sum()
        d['WoE'] = np.log(d['% of Non-Events']/d['% of Events'])
        d['IV'] = d['WoE'] * (d['% of Non-Events']-d['% of Events'])
        d.insert(loc=0, column='Variable', value=ivars)
        # print("Information value of " + ivars +
        #     " is " + str(round(d['IV'].sum(), 6)))
        temp = pd.DataFrame({"Variable": [ivars], "IV": [
                            d['IV'].sum()]}, columns=["Variable", "IV"])
        newDF = pd.concat([newDF, temp], axis=0)
        woeDF = pd.concat([woeDF, d], axis=0)

        # Show WOE Table
        # if show_woe == True:
        #     print(d)
    return newDF, woeDF

