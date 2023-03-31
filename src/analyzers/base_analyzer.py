class BaseAnalyzer:
    def __init__(self):
        pass
    def is_message_interesting(self, message):
        raise NotImplementedError

    def collect_statistics(self):
        raise NotImplementedError