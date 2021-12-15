import logging

log = logging.getLogger('trevorspray.looters.base')

class Looter:

    def __init__(self, sprayer, credential):

        self.sprayer = sprayer
        self.credential = credential
        self.loot_dir = self.sprayer.trevor.home / 'loot'
        self.loot_dir.mkdir(exist_ok=True)
        self.looters = [getattr(self, func) for func in dir(self) if callable(getattr(self, func)) and func.startswith("looter_")]


    def run(self):
        log.info(f'Running loot module: {self.__class__.__name__}')
        for func in self.looters:
            func()