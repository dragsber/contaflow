from adapters.revolut import read_rows


class RevolutCSVAdapter:
    name = "Revolut CSV EUR/CHF"

    def read(self, payload):
        return read_rows(payload)


class PendingStatementAdapter:
    def __init__(self, name):
        self.name = name

    def read(self, payload):
        raise NotImplementedError(
            f"Adattatore {self.name} predisposto. Servono esempi reali e collaudo del formato."
        )


BPER_EUR = PendingStatementAdapter("BPER EUR")
PDF = PendingStatementAdapter("PDF bancario")
XLSX = PendingStatementAdapter("XLSX bancario")
