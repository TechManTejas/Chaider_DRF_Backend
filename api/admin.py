from django.contrib import admin
from .models import CSVFile, CSVFileVariable

# Register your models here.
@admin.register(CSVFile)
class CSVFileAdmin(admin.ModelAdmin):
    list_display = ['id', 'userid', 'name', 'description', 'file']


@admin.register(CSVFileVariable)
class CSVFileVariableAdmin(admin.ModelAdmin):
    list_display = ['id', 'preview', 'userid', 'name',
                    'description', 'filename', 'variables', 'filters',  'instances', 'stageData']
