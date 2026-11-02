from .base import NotConfiguredAdapter

class GoogleSheetsAdapter(NotConfiguredAdapter):
    def __init__(self): super().__init__('Google Sheets')
