class NotConfiguredAdapter:
    """Safe placeholder for an integration that has not been configured."""
    def __init__(self, name):
        self.name = name

    def status(self):
        return {'configured': False, 'name': self.name}
