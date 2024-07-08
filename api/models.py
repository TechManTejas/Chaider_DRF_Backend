from django.db import models
from django.contrib.auth.models import User

# Create your models here.
class CSVFile(models.Model):
    name = models.CharField(max_length=100, default='')
    file = models.FileField(upload_to='api/csv_file_uploaded')
    userid = models.IntegerField(default=0)
    description = models.TextField(default='No Description')

    def __str__(self):
        return self.name
        
class CSVFileVariable(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(default='No Description')
    filename = models.CharField(max_length=100)
    variables = models.JSONField()
    filters = models.JSONField(default=dict)
    userid = models.IntegerField(default=0)
    preview = models.ImageField(default='api/images/BlankStage.png', upload_to="api/images")
    instances = models.JSONField(default=dict)
    stageData = models.JSONField(default=dict)

    def __str__(self):
        return self.filename
