from .base import NotConfiguredAdapter

class EnableBankingAdapter(NotConfiguredAdapter):
    def __init__(self): super().__init__('Enable Banking')
