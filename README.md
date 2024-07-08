# Chaider Backend

### To start server run command 'python manage.py runserver' 

### In Django Admin http://127.0.0.1:8000/admin/ Username:- SUPERUSER Password: SUPERUSER

### Upload csv files at http://127.0.0.1:8000/chaidercsv/ 

### Get and post at http://127.0.0.1:8000/visualisation/

### .csv files are stored in api/csv_file_uploaded folder

post data in this format to http://localhost:8000/visualisation/ 

## Post format for forcesplit
{
  "data": {
    "csvid": 149,
    "operation": "forcesplit",
    "yVar": "survived",
    "varsTillNode": ["male",3.0],
    "xVariablesTillNode": ["sex","pclass","embarked"]
  }
}

## Response format for forcesplit
{
  "nodes": [
    {
      "nodeName": "S",
      "total": 366,
      "nodeContent": {
        "1.0": 53,
        "0.0": 313
      }
    },
    {
      "nodeName": "C",
      "total": 70,
      "nodeContent": {
        "1.0": 15,
        "0.0": 55
      }
    },
    {
      "nodeName": "Q",
      "total": 57,
      "nodeContent": {
        "1.0": 7,
        "0.0": 50
      }
    }
  ]
}

## NODE CLASSIFICATION VIDE RESPONSE FORMAT
{
  'nodeType': "VALUE"
  'nodeName': 'name1', 
  'nodeCategory': 'name', 
  'total': 1, 
  'nodeContent': {1.0: 1, 0.0: 0}
  'Data' : 'name1',
}

{
  'nodeType': "PACKED"
  'nodeName': nodeCategory + "s" / "es", 
  'nodeCategory': 'name', 
  'total': 100, 
  'nodeContent': {1.0: 100, 0.0: 1}
  'Data' : ['name1', 'name2', ... , 'name100'],
}

{
  'nodeType': "RANGED"
  'nodeName': nodeData[0] +"-"+ nodeData[1], 
  'nodeCategory': 'age', 
  'total': 50, 
  'nodeContent': {1.0: 40, 0.0: 10}
  'Data' : [25,75],
}



