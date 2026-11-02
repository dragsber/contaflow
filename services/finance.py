from contaflow.store import Store

class FinanceService:
    """Application boundary for account, ledger and import operations."""
    def __init__(self, store=None):
        self.store = store or Store()

    def accounts(self):
        return self.store.accounts()

    def summary(self, account=None):
        return self.store.summary(account)

    def movements(self, account=None):
        return self.store.recent(account)

    def import_revolut(self, path, account):
        result = self.store.import_revolut_detailed(path, account)
        anomalies = self.store.reconcile_revolut_csv(path)
        return {**result, 'anomalies': anomalies}
